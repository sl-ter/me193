"""
Pure ping-pong logic: ball physics against a wall, the hit rule, and
streak/record bookkeeping. No camera, no Bluetooth, no MQTT -- pong.py feeds
it the paddle position (from pose) and swing times (from the IMU), and it
returns events. That keeps it testable (see tests/test_game.py).

Court coordinates are normalized: x in [0, 1] left to right, y in [0, 1]
from the wall (y=0, the "opponent") down to the player. The ball has to be
hit as it crosses HIT_Y.
"""

import math
import random
from dataclasses import dataclass

HIT_Y = 0.88            # the player's hitting line
BALL_R = 0.018          # ball radius (court units), for drawing and side walls
MAX_ANGLE = math.radians(55)   # return angle when the ball hits the paddle's very edge
SWEET_SPOT = 0.25       # |offset| below this (fraction of half-width) = sweet spot
SWEET_BONUS = 1.06      # extra return speed for a sweet-spot hit
MAX_SPEED = 2.2         # court heights per second; keeps hard mode playable
SERVE_DELAY = 1.2       # seconds between a miss and the next serve

# A swing counts if it lands in [crossing - EARLY, crossing + LATE]. Swinging a
# little early is natural (you start before the ball arrives); LATE covers
# Bluetooth delay between the real swing and the gyro sample reaching us.
SWING_EARLY = 0.30
SWING_LATE = 0.15

# Spin from twisting the paddle (see swing.py). Spin bends the ball sideways
# in proportion to its speed, like the Magnus effect. CURVE = 0.5 moves a
# full-spin ball about a third of the court width on its way to the wall.
SPIN_DEADZONE = 0.25    # |spin| below this counts as a flat swing (no curve)
CURVE = 0.5
WALL_SPIN_KEEP = 0.5    # the wall takes half the spin off; the rest curves the return


@dataclass(frozen=True)
class Level:
    name: str
    speed: float        # serve speed, court heights per second
    speedup: float      # return speed multiplier per hit
    paddle_w: float     # paddle width, court units


# AprilTag ID -> level. Tag 0 is reserved for pause (see pong.py).
LEVELS = {
    1: Level("easy", speed=0.45, speedup=1.03, paddle_w=0.30),
    2: Level("medium", speed=0.65, speedup=1.05, paddle_w=0.22),
    3: Level("hard", speed=0.90, speedup=1.07, paddle_w=0.16),
}


@dataclass
class Swing:
    t: float            # when the swing started (gyro crossed the threshold)
    power: float = 1.0  # peak gyro / threshold; >1, bigger = harder swing
    spin: float = 0.0   # -1..1, twist share of the swing; + = twisted right


class Game:
    def __init__(self, level=LEVELS[1], seed=None):
        self.rng = random.Random(seed)
        self.level = level
        self.streak = 0
        self.record = 0
        self.x = self.y = 0.5
        self.vx = self.vy = 0.0
        self.spin = 0.0             # -1..1; + curves the ball to the right
        self.in_play = False
        self.serve_at = None        # time of the next serve, while waiting after a miss
        self.crossing = None        # (t, paddle_x, paddle_seen) once the ball reaches HIT_Y
        self.swings = []            # recent swings, oldest first
        self.last_hit = None        # dict describing the last hit, for the HUD

    # -- control ------------------------------------------------------------

    def set_level(self, level):
        """Change level. The streak restarts (it wouldn't be a fair streak
        otherwise), but the record stands."""
        self.level = level
        self.streak = 0
        self.in_play = False
        self.serve_at = None

    def serve(self, now=0.0):
        """Ball leaves the wall toward the player at a random angle."""
        self.x = self.rng.uniform(0.2, 0.8)
        self.y = 0.05
        angle = self.rng.uniform(-math.radians(25), math.radians(25))
        self.vx = self.level.speed * math.sin(angle)
        self.vy = self.level.speed * math.cos(angle)
        self.spin = 0.0
        self.in_play = True
        self.serve_at = None
        self.crossing = None
        self.swings = [s for s in self.swings if s.t >= now - SWING_EARLY]

    def add_swing(self, swing):
        self.swings = [s for s in self.swings if s.t >= swing.t - 2.0]
        self.swings.append(swing)

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    # -- simulation -----------------------------------------------------------

    def time_to_paddle(self):
        """Seconds until the ball reaches the hitting line, or None if it's
        heading away (or not in play). Used for the approach rumble."""
        if not self.in_play or self.vy <= 0 or self.crossing is not None:
            return None
        return max(0.0, (HIT_Y - self.y) / self.vy)

    def step(self, dt, now, paddle_x, paddle_seen=True):
        """Advance the ball by dt seconds. paddle_x is the paddle center in
        court units (None/paddle_seen=False when the pose was lost). Returns
        a list of events: ("wall",), ("hit", info), ("miss", reason), ("serve",)."""
        events = []
        if not self.in_play:
            if self.serve_at is not None and now >= self.serve_at:
                self.serve(now)
                events.append(("serve",))
            return events

        if self.spin:
            self.vx += CURVE * self.spin * self.speed * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        # side walls
        if self.x < BALL_R:
            self.x, self.vx = BALL_R, abs(self.vx)
        elif self.x > 1 - BALL_R:
            self.x, self.vx = 1 - BALL_R, -abs(self.vx)

        # the wall (opponent) always returns the ball
        if self.y <= 0 and self.vy < 0:
            self.y, self.vy = 0.0, abs(self.vy)
            self.spin *= WALL_SPIN_KEEP
            events.append(("wall",))

        # reaching the hitting line: freeze where the paddle was at that
        # instant, then wait up to SWING_LATE for the swing to show up
        if self.crossing is None and self.vy > 0 and self.y >= HIT_Y:
            self.crossing = (now, paddle_x, paddle_seen and paddle_x is not None)

        if self.crossing is not None:
            events.extend(self._judge(now))
        return events

    def _judge(self, now):
        t_cross, px, seen = self.crossing
        half = self.level.paddle_w / 2
        offset = (self.x - px) / half if seen else None
        in_place = seen and abs(offset) <= 1.0 + BALL_R / half
        swing = next((s for s in self.swings
                      if t_cross - SWING_EARLY <= s.t <= t_cross + SWING_LATE), None)

        if in_place and swing is not None:
            return [self._hit(offset, swing, now)]
        if now < t_cross + SWING_LATE:
            return []           # still waiting for a late swing
        if not seen:
            reason = "no pose"
        elif not in_place:
            reason = "out of position"
        else:
            reason = "no swing"
        return [self._miss(now, reason)]

    def _hit(self, offset, swing, now):
        offset = max(-1.0, min(1.0, offset))
        sweet = abs(offset) < SWEET_SPOT
        # harder swings return faster, within reason
        power = max(0.9, min(1.3, 0.85 + 0.15 * swing.power))
        speed = self.speed * self.level.speedup * power * (SWEET_BONUS if sweet else 1.0)
        speed = min(speed, MAX_SPEED)
        angle = offset * MAX_ANGLE
        self.vx = speed * math.sin(angle)
        self.vy = -speed * math.cos(angle)
        self.y = HIT_Y - 0.001
        self.spin = swing.spin if abs(swing.spin) >= SPIN_DEADZONE else 0.0
        self.crossing = None
        self.swings.remove(swing)
        self.streak += 1
        self.record = max(self.record, self.streak)
        self.last_hit = {"offset": offset, "sweet": sweet, "power": swing.power,
                         "spin": self.spin, "t": now}
        return ("hit", self.last_hit)

    def _miss(self, now, reason):
        self.streak = 0
        self.in_play = False
        self.crossing = None
        self.serve_at = now + SERVE_DELAY
        return ("miss", reason)
