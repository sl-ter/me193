"""
Paddle backends. Each one gives the game gyro samples (for swing detection)
and takes haptic cues. Same interface, so pong.py doesn't care which:

    start()            connect / spin up threads
    poll()             -> [(t, |gyro|, (gx, gy, gz)), ...] new samples since last call
    haptic(kind, strength=1.0)
                       "start" | "hit" | "sweet" | "miss" | "tick" (never blocks);
                       strength 0..1 scales the tick
    on_key(key)        keyboard input from the OpenCV window
    stop()

LegoPaddle      the LEGO Education Double Motor: built-in IMU over Bluetooth,
                haptics from an off-center LEGO weight on one motor output
KeyboardPaddle  no hardware: space = flat swing, z / x = swing twisting
                left / right (spin). For testing the game.

Haptics are two layers on the same weighted motor, driven with raw duty
cycle (motor_run_for_time is speed-regulated and barely moves in a short
pulse). What the motor can do, measured with haptic_lab.py on 10/12:
  - the firmware ramps power up and down at ~100% per 200 ms, whatever
    motor_set_acceleration says, and commands land ~60 ms after sending.
    So a "kick then reverse" can't reverse: the reverse just ramps power
    back down. What you feel is how far the weight swings.
  - Sam's ratings: 40% for 60 ms = "very slight, I like it" (the rumble);
    100% for 150 ms = clear (contact); ~250-300 ms = solid; 400 ms = strong,
    too much for gameplay but fine for a start signal.

  "tick"         approach rumble: light pulse, a little stronger as the ball
                 gets closer. pong.py sends them faster as it approaches.
                 Dropped if anything else is waiting, so they never delay
                 the contact pulse.
  "hit"          contact: full power, about half a turn of the weight.
  "sweet"        sweet-spot contact: longer, so more solid, plus an azure light.
  "miss"         three medium pulses alternating direction ("no-no-no"), red light.
  "start"        one strong pulse, beep, green light.
"""

import math
import queue
import random
import threading
import time

from swing import gyro_magnitude

# Haptic tuning (ms and % duty). Tune by feel: check_paddle.py --haptics-only
# Power ramps slowly, so pulse length sets the strength more than duty does.
TICK_DUTY = 45                      # approach rumble
TICK_MS_FAR, TICK_MS_NEAR = 75, 100 # rumble pulse: ~17 deg far -> ~35 deg about to arrive
HIT_MS, SWEET_MS = 200, 300         # contact at full power: ~140 deg / ~300 deg of swing
MISS_MS, MISS_GAP_MS, MISS_DUTY = 140, 160, 75   # x3, alternating direction
START_MS = 400


class LegoPaddle:
    name = "LEGO Double Motor"

    def __init__(self, card_serial=None, card_color=None, haptic_motor="left",
                 notify_ms=20, haptics=True):
        self.card_serial = card_serial
        self.card_color = card_color          # e.g. "red"; None = any card
        self.haptic_motor = haptic_motor      # which output has the weight on it
        self.notify_ms = notify_ms            # IMU notification interval (15-1000 ms)
        self.haptics_on = haptics
        self.dm = None
        self._samples = []
        self._lock = threading.Lock()
        self._haptic_q = queue.Queue()
        self._running = False
        self._busy = False
        self._haptic_thread = None
        self.sample_rate = 0.0                # measured notifications per second

    # -- connection --------------------------------------------------------------

    def start(self):
        import legoeducation as le
        self.le = le
        self.dm = le.DoubleMotor()
        color = None
        if self.card_color:
            color = getattr(le, f"LEGO_COLOR_{self.card_color.upper()}")
        who = f"card {self.card_color or 'any'} {self.card_serial or ''}".strip()
        print(f"Connecting to Double Motor ({who})...")
        # Same retry as lelib.doubleMotor.connect, but asking for IMU
        # notifications every notify_ms. The library's default is 100 ms
        # (10 Hz), too slow to catch a quick swing reliably.
        for attempt in range(5):
            try:
                self.dm.connect(card_color=color, card_serial=self.card_serial,
                                device_notification_delay=self.notify_ms)
                break
            except Exception as e:
                if "not ready" in str(e).lower() and attempt < 4:
                    time.sleep(1)
                else:
                    raise
        if not self.dm.connected:
            raise ConnectionError("Error connecting to Double Motor.")

        deadline = time.monotonic() + 5
        while math.isnan(float(self.dm.imu_device.gyroscopeX)):
            if time.monotonic() > deadline:
                raise RuntimeError("Connected, but no IMU readings arrived from the Double Motor.")
            time.sleep(0.05)
        print("Connected.")

        self._running = True
        threading.Thread(target=self._sample_loop, daemon=True).start()
        self._haptic_thread = threading.Thread(target=self._haptic_loop, daemon=True)
        self._haptic_thread.start()

    def stop(self):
        self._running = False
        if self._haptic_thread is not None:
            self._haptic_thread.join(timeout=2)     # let the last pattern finish
        if self.dm is not None:
            # Blocking here on purpose: disconnect() fails any command still
            # waiting for its reply, which prints a scary but harmless
            # "Future exception was never retrieved ... Device disconnected".
            try:
                self.dm.motor_stop(motor=self.le.MOTOR_BOTH)
                self.dm.light_color(self.le.LEGO_COLOR_NOCOLOR)
                time.sleep(0.1)
                self._cancel_unanswered()
                self.dm.disconnect()
            except Exception:
                pass

    def _cancel_unanswered(self):
        """Non-blocking haptic commands leave reply futures that nobody
        awaits; some never get a reply. disconnect() would fail them and
        asyncio would print "Future exception was never retrieved". Cancel
        them first (cancelled futures are silent). Reaches into the
        library's internals, so it's best-effort only."""
        try:
            from legoeducation._platform import _persistent_loop as loop
            pending = [list(dq) for dq in self.dm._pending_responses.values()]

            def cancel():
                for dq in pending:
                    for fut in dq:
                        if not fut.done():
                            fut.cancel()

            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(cancel)
                time.sleep(0.05)
        except Exception:
            pass

    # -- IMU -------------------------------------------------------------------

    def _sample_loop(self):
        """The library swaps in a new ImuDeviceNotification object each time
        one arrives, so a new object = a new sample. Poll faster than the
        notification rate and keep each one once, timestamped on arrival."""
        last = None
        count, t0 = 0, time.monotonic()
        while self._running:
            imu = self.dm.imu_device
            if imu is not last:
                last = imu
                t = time.monotonic()
                g = (float(imu.gyroscopeX), float(imu.gyroscopeY), float(imu.gyroscopeZ))
                with self._lock:
                    self._samples.append((t, gyro_magnitude(*g), g))
                count += 1
                if t - t0 >= 2.0:
                    self.sample_rate, count, t0 = count / (t - t0), 0, t
            time.sleep(0.003)

    def poll(self):
        with self._lock:
            out, self._samples = self._samples, []
        return out

    def raw_imu(self):
        return self.dm.imu_device

    # -- haptics -----------------------------------------------------------------

    def haptic(self, kind, strength=1.0):
        if not self.haptics_on:
            return
        if kind == "tick" and (self._busy or not self._haptic_q.empty()):
            return                      # rumble is best-effort; never queue it
        self._haptic_q.put((kind, strength))

    def _haptic_loop(self):
        # Bluetooth calls happen on this thread so the game loop never waits
        # on them. Patterns are tuned by feel; see check_paddle.py --haptics.
        le = self.le
        motor = le.MOTOR_LEFT if self.haptic_motor == "left" else le.MOTOR_RIGHT

        # brake (not coast) so each pulse ends sharply
        self.dm.motor_set_end_state(le.MOTOR_END_STATE_BRAKE, motor=motor)

        def pulse(ms, duty=100):
            self.dm.motor_set_duty_cycle(duty, motor=motor, blocking=False)
            time.sleep(ms / 1000)
            self.dm.motor_stop(motor=motor, blocking=False)

        while self._running:
            try:
                kind, strength = self._haptic_q.get(timeout=0.2)
            except queue.Empty:
                continue
            self._busy = True
            try:
                if kind == "tick":
                    s = max(0.0, min(1.0, strength))
                    pulse(TICK_MS_FAR + s * (TICK_MS_NEAR - TICK_MS_FAR), TICK_DUTY)
                elif kind == "start":
                    self.dm.light_color(le.LEGO_COLOR_GREEN, blocking=False)
                    self.dm.beep(pattern=le.SOUND_PATTERN_BEEP_UP_MIDDLE_DOWN, blocking=False)
                    pulse(START_MS)
                elif kind == "hit":
                    pulse(HIT_MS)
                elif kind == "sweet":
                    self.dm.light_color(le.LEGO_COLOR_AZURE, blocking=False)
                    pulse(SWEET_MS)
                    self.dm.light_color(le.LEGO_COLOR_GREEN, blocking=False)
                elif kind == "miss":
                    self.dm.light_color(le.LEGO_COLOR_RED, blocking=False)
                    for i in range(3):
                        pulse(MISS_MS, MISS_DUTY if i % 2 == 0 else -MISS_DUTY)
                        time.sleep(MISS_GAP_MS / 1000)
                    self.dm.light_color(le.LEGO_COLOR_GREEN, blocking=False)
            except Exception as e:
                print(f"haptic {kind!r} failed: {e}")
            finally:
                self._busy = False

    def on_key(self, key):
        pass


class KeyboardPaddle:
    """Stands in for the Double Motor: a small resting jitter, and a big gyro
    spike when space (flat), z (twist left) or x (twist right) is pressed in
    the game window. Twist goes on the gyro's x axis, pong.py's default."""
    name = "keyboard (space/z/x = swing)"
    sample_rate = 50.0
    SWINGS = {ord(" "): 0.0, ord("z"): -0.8, ord("x"): 0.8}   # key -> spin

    def __init__(self):
        self._spike = None
        self._last = time.monotonic()

    def start(self):
        pass

    def stop(self):
        pass

    def on_key(self, key):
        if key in self.SWINGS:
            self._spike = self.SWINGS[key]

    def poll(self):
        now = time.monotonic()
        out = []
        t = self._last
        while t + 0.02 <= now:          # 50 Hz of resting noise
            t += 0.02
            out.append((t, random.uniform(0, 5), (0.0, 0.0, 0.0)))
        self._last = t
        if self._spike is not None:
            spin = self._spike
            g = (1000.0 * spin, 1000.0 * math.sqrt(1 - spin * spin), 0.0)
            out.append((now, 1000.0, g))
            out.append((now + 1e-3, 0.0, (0.0, 0.0, 0.0)))
            self._spike = None
        return out

    def haptic(self, kind, strength=1.0):
        pass
