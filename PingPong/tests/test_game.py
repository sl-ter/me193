import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import HIT_Y, LEVELS, SWING_EARLY, SWING_LATE, Game, Swing  # noqa: E402


def ball_about_to_cross(x=0.5, speed=0.5):
    """A game whose ball crosses the hitting line on the next 0.05 s step."""
    g = Game(LEVELS[2], seed=1)
    g.serve(0.0)
    g.x, g.y, g.vx, g.vy = x, HIT_Y - 0.01, 0.0, speed
    return g


def run(g, start, paddle_x, seconds=0.5, seen=True):
    events, t = [], start
    while t < start + seconds:
        t += 0.05
        events += g.step(0.05, t, paddle_x, seen)
    return events


def kinds(events):
    return [e[0] for e in events if e[0] in ("hit", "miss")]


def test_hit_needs_position_and_swing():
    g = ball_about_to_cross()
    g.add_swing(Swing(t=0.0, power=1.5))
    events = run(g, 0.0, paddle_x=0.5)
    assert kinds(events)[0] == "hit"
    assert g.streak == 1 and g.record == 1
    assert g.vy < 0                     # going back toward the wall


def test_in_position_but_no_swing_is_a_miss():
    g = ball_about_to_cross()
    events = run(g, 0.0, paddle_x=0.5)
    assert ("miss", "no swing") in events
    assert g.streak == 0 and not g.in_play


def test_swing_out_of_position_is_a_miss():
    g = ball_about_to_cross(x=0.1)
    g.add_swing(Swing(t=0.0))
    events = run(g, 0.0, paddle_x=0.8)
    assert ("miss", "out of position") in events


def test_lost_pose_is_a_miss():
    g = ball_about_to_cross()
    g.add_swing(Swing(t=0.0))
    events = run(g, 0.0, paddle_x=None, seen=False)
    assert ("miss", "no pose") in events


def test_slightly_late_swing_still_counts():
    g = ball_about_to_cross()
    events = g.step(0.05, 0.05, 0.5)            # crosses at t=0.05
    assert not kinds(events)
    g.add_swing(Swing(t=0.05 + SWING_LATE * 0.8))
    events = run(g, 0.05, paddle_x=0.5)
    assert kinds(events)[0] == "hit"


def test_too_early_swing_misses():
    g = ball_about_to_cross()
    g.add_swing(Swing(t=0.05 - SWING_EARLY - 0.1))
    events = run(g, 0.0, paddle_x=0.5)
    assert kinds(events) == ["miss"]


def test_record_survives_a_miss():
    g = ball_about_to_cross()
    t = 0.0
    for _ in range(3):                          # three hits in a row
        g.x, g.y, g.vx, g.vy = 0.5, HIT_Y - 0.01, 0.0, 0.5
        g.add_swing(Swing(t=t))
        run(g, t, 0.5, seconds=0.1)
        t += 1.0
    assert g.streak == 3 and g.record == 3
    g.x, g.y, g.vx, g.vy = 0.5, HIT_Y - 0.01, 0.0, 0.5
    run(g, t, 0.5)                              # no swing -> miss
    assert g.streak == 0 and g.record == 3


def test_edge_hit_angles_ball_and_sweet_spot_is_straighter_and_faster():
    edge = ball_about_to_cross(x=0.5 + LEVELS[2].paddle_w / 2 * 0.9)
    edge.add_swing(Swing(t=0.0, power=1.0))
    run(edge, 0.0, 0.5, seconds=0.1)
    centre = ball_about_to_cross(x=0.5)
    centre.add_swing(Swing(t=0.0, power=1.0))
    run(centre, 0.0, 0.5, seconds=0.1)
    assert edge.vx > 0.2                        # deflected right
    assert abs(centre.vx) < 1e-9
    assert centre.last_hit["sweet"] and not edge.last_hit["sweet"]
    assert centre.speed > edge.speed


def test_wall_returns_ball():
    g = Game(LEVELS[1], seed=2)
    g.serve(0.0)
    g.x, g.y, g.vx, g.vy = 0.5, 0.01, 0.0, -0.5
    events = g.step(0.05, 0.05, 0.5)
    assert ("wall",) in events and g.vy > 0


def test_serves_again_after_a_miss():
    g = ball_about_to_cross()
    run(g, 0.0, 0.5)
    assert not g.in_play
    events = run(g, 0.5, 0.5, seconds=2.0)
    assert ("serve",) in events and g.in_play
    assert math.isclose(g.speed, LEVELS[2].speed)


def test_level_change_resets_streak_not_record():
    g = ball_about_to_cross()
    g.add_swing(Swing(t=0.0))
    run(g, 0.0, 0.5, seconds=0.1)
    g.set_level(LEVELS[3])
    assert g.streak == 0 and g.record == 1


def hit_with_spin(spin):
    g = ball_about_to_cross()
    g.add_swing(Swing(t=0.0, power=1.0, spin=spin))
    run(g, 0.0, 0.5, seconds=0.1)
    return g


def test_twisted_swing_curves_the_ball():
    right, flat = hit_with_spin(0.8), hit_with_spin(0.0)
    assert right.spin == 0.8 and flat.spin == 0.0
    for g in (right, flat):
        for i in range(10):
            g.step(0.05, 1 + i * 0.05, 0.5)
    assert right.vx > 0.1 and abs(flat.vx) < 1e-9
    assert right.x > flat.x


def test_small_twist_is_a_flat_shot():
    from game import SPIN_DEADZONE
    assert hit_with_spin(SPIN_DEADZONE * 0.5).spin == 0.0


def test_wall_takes_off_half_the_spin():
    from game import WALL_SPIN_KEEP
    g = Game(LEVELS[1], seed=2)
    g.serve(0.0)
    g.x, g.y, g.vx, g.vy, g.spin = 0.5, 0.01, 0.0, -0.5, 0.8
    g.step(0.05, 0.05, 0.5)
    assert g.spin == 0.8 * WALL_SPIN_KEEP


def test_time_to_paddle_only_when_ball_is_coming():
    g = Game(LEVELS[1], seed=2)
    g.serve(0.0)
    g.x, g.y, g.vx, g.vy = 0.5, HIT_Y - 0.5, 0.0, 0.5
    assert math.isclose(g.time_to_paddle(), 1.0)
    g.vy = -0.5
    assert g.time_to_paddle() is None
