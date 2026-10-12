#!/usr/bin/env python3
"""
Haptic lab: find a motor drive that you can actually feel.

The first haptics used motor_run_for_time(30-120 ms). That command is
speed-regulated with an acceleration ramp, so a short pulse barely gets the
motor moving, and the LEGO motor is geared down (only a few turns per second)
so an off-center weight never spins fast enough to buzz.

This tries alternatives. It measures how far the weighted output actually
turned (from the motor's own position sensor) and asks how strongly you felt
each one, 0-3. Results go to haptic_lab.json for tuning paddles.py.

Hold the paddle the way you play. Each variant waits for Enter.

  venv/bin/python haptic_lab.py
"""

import json
import os
import threading
import time

from paddles import LegoPaddle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haptic_lab.json")


class Lab:
    def __init__(self, paddle, motor_side="left"):
        self.p = paddle
        self.dm = paddle.dm
        le = paddle.le
        self.le = le
        self.motor = le.MOTOR_LEFT if motor_side == "left" else le.MOTOR_RIGHT
        self.idx = 0 if motor_side == "left" else 1

    def pos(self):
        return float(self.dm.motor[self.idx].position)

    def duty(self, d):
        self.dm.motor_set_duty_cycle(d, motor=self.motor, blocking=False)

    def stop(self):
        self.dm.motor_stop(motor=self.motor, blocking=False)

    def measure(self, action, settle=0.4):
        """Run action() while sampling position; returns degrees: (max
        excursion from the start, net change)."""
        start = self.pos()
        seen = [start]
        done = threading.Event()

        def sample():
            while not done.is_set():
                seen.append(self.pos())
                time.sleep(0.005)

        t = threading.Thread(target=sample, daemon=True)
        t.start()
        action()
        time.sleep(settle)
        done.set()
        t.join()
        return max(abs(v - start) for v in seen), self.pos() - start


def variants(lab):
    le, dm, m = lab.le, lab.dm, lab.motor

    def old_hit():                                   # what the game did before
        dm.motor_run_for_time(120, motor=m, speed=100, blocking=False)
        time.sleep(0.12)

    def pulse(ms, d=100):
        def run():
            lab.duty(d)
            time.sleep(ms / 1000)
            lab.stop()
        return run

    def jolt(ms):                                    # out and straight back
        def run():
            lab.duty(100)
            time.sleep(ms / 1000)
            lab.duty(-100)
            time.sleep(ms / 1000)
            lab.stop()
        return run

    def shake(ms, n, d=100):                         # rapid back-and-forth
        def run():
            for i in range(n):
                lab.duty(d if i % 2 == 0 else -d)
                time.sleep(ms / 1000)
            lab.stop()
        return run

    return [
        ("A  old: run_for_time 120 ms (baseline)", old_hit),
        ("B  raw duty 100%, 150 ms", pulse(150)),
        ("C  raw duty 100%, 400 ms", pulse(400)),
        ("D  jolt: 100% out 80 ms, straight back 80 ms", jolt(80)),
        ("E  jolt, bigger: 150 ms out, 150 ms back", jolt(150)),
        ("F  shake: +-100% every 50 ms, 8 times", shake(50, 8)),
        ("G  shake: +-100% every 30 ms, 12 times", shake(30, 12)),
        ("H  light tick: duty 40%, 60 ms", pulse(60, 40)),
        ("I  long spin: 100% for 1.5 s (how fast does the weight go?)", pulse(1500)),
    ]


def main():
    paddle = LegoPaddle("0994", "orange", haptics=False)
    paddle.start()
    lab = Lab(paddle)
    # brake (not coast) so a stop is a sharp stop
    paddle.dm.motor_set_end_state(paddle.le.MOTOR_END_STATE_BRAKE, motor=lab.motor)
    results = []
    try:
        print("\nHold the paddle like you play. For each one: Enter to run it, then rate it.\n"
              "Also watch the weight: does it move at all?\n")
        for name, action in variants(lab):
            input(f"{name}   [Enter]")
            excursion, net = lab.measure(action)
            print(f"    weight turned: max {excursion:.0f} deg, ended {net:+.0f} deg")
            rating = ""
            while rating not in ("0", "1", "2", "3"):
                rating = input("    felt it? 0 nothing / 1 barely / 2 clear / 3 strong: ").strip()
            note = input("    notes (optional): ").strip()
            results.append({"variant": name, "max_deg": round(excursion), "net_deg": round(net),
                            "felt": int(rating), "note": note})
    finally:
        with open(OUT, "w") as f:
            json.dump({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, f, indent=2)
        print(f"\nSaved {os.path.basename(OUT)} ({len(results)} results).")
        paddle.stop()


if __name__ == "__main__":
    main()
