"""Tests for the safe's rules (unoq/finger-lock/python/lock_policy.py), fed
made-up streams of network answers, so they run without a camera.

    venv/bin/python -m pytest FingerLock -q
"""
import common  # noqa: F401  (puts the board's python folder on the path)
import pytest

import lock_policy as LP

CODE = (3, 1, 4, 2)
DURESS = (2, 4, 1, 3)
NONE = 0
UNSURE = None
HOLD = 1.4          # comfortably longer than HOLD_S, even at 4 frames a second
GAP = 0.8           # hand off the mat: longer than CLEAR_S plus a frame or two at 4 frames a second


def d(digit):
    """Class index of a digit (index 0 is 'no hand')."""
    return digit + 1


def probs(label, conf=0.95):
    if label is UNSURE:
        return [0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]       # best is 0.3 < CONF
    p = [(1 - conf) / 6] * 7
    p[label] = conf
    return p


def run(policy, segments, fps=10, t0=0.0, owner=0.95):
    """segments: [(seconds, class index or UNSURE[, owner probability])].
    Returns (events, time after the last frame)."""
    events, t = [], t0
    for seg in segments:
        secs, label = seg[0], seg[1]
        owner_p = seg[2] if len(seg) > 2 else owner
        for _ in range(int(round(secs * fps))):
            events += policy.update(t, probs(label), owner_p)
            t += 1.0 / fps
    return events, t


def enter(code, hold=HOLD, gap=GAP, owner=0.95):
    """Show a code. owner: one owner probability for every digit, or one per digit."""
    owners = owner if isinstance(owner, (list, tuple)) else [owner] * len(code)
    segs = [(gap, NONE)]
    for digit, o in zip(code, owners):
        segs += [(hold, d(digit), o), (gap, NONE)]
    return segs


def kinds(events):
    return [e.kind for e in events]


def digits(events):
    return [e.digit for e in events if e.kind == "digit"]


def test_right_code_opens():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter(CODE))
    assert digits(ev) == list(CODE)
    opens = [e for e in ev if e.kind == "open"]
    assert len(opens) == 1 and not opens[0].duress
    assert p.state == "open"


def test_duress_code_opens_the_same_way_but_flags_it():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter(DURESS))
    opens = [e for e in ev if e.kind == "open"]
    assert len(opens) == 1 and opens[0].duress
    assert p.state == "open"
    assert p.status(0)["state"] == "open"         # nothing visible gives it away


def test_wrong_code_is_refused():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter((0, 0, 0, 0)))
    assert "open" not in kinds(ev) and kinds(ev).count("wrong") == 1
    assert p.state == "locked" and p.fails == 1


def test_three_wrong_codes_lock_out_then_it_recovers():
    p = LP.LockPolicy(CODE, DURESS)
    ev, t = run(p, enter((0, 0, 0, 0)) * 3)
    assert kinds(ev).count("wrong") == 3 and "lockout" in kinds(ev)
    assert p.state == "lockout"
    ev, t = run(p, enter(CODE), t0=t)              # ignored during the lockout
    assert "digit" not in kinds(ev) and "open" not in kinds(ev)
    ev, t = run(p, [(LP.LOCKOUT_S, NONE)] + enter(CODE), t0=t)
    assert "lockout_over" in kinds(ev) and "open" in kinds(ev)


def test_right_code_resets_the_wrong_count():
    p = LP.LockPolicy(CODE, DURESS)
    ev, t = run(p, enter((0, 0, 0, 0)) * 2 + enter(CODE))
    assert "open" in kinds(ev) and p.fails == 0


def test_holding_a_digit_counts_once_and_repeats_need_the_hand_off():
    p = LP.LockPolicy((3, 3, 1, 2), DURESS)
    ev, t = run(p, [(GAP, NONE), (4.0, d(3))])
    assert digits(ev) == [3]
    ev, t = run(p, [(GAP, NONE), (HOLD, d(3)), (GAP, NONE), (HOLD, d(1)), (GAP, NONE), (HOLD, d(2))], t0=t)
    assert digits(ev) == [3, 1, 2] and "open" in kinds(ev)


def test_short_hold_does_not_count():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, [(GAP, NONE), (0.5, d(3)), (GAP, NONE)])
    assert digits(ev) == []


def test_a_one_frame_blip_does_not_restart_the_hold():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, [(GAP, NONE), (0.6, d(3)), (0.1, d(1)), (0.6, d(3))])
    assert digits(ev) == [3]


def test_frames_of_the_hand_moving_in_do_not_count():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, [(GAP, NONE), (0.2, d(1)), (0.2, d(2)), (HOLD, d(3))])
    assert digits(ev) == [3]


def test_unsure_frames_never_count():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, [(GAP, NONE), (3.0, UNSURE)])
    assert digits(ev) == []


def test_a_strangers_code_is_refused_once_at_the_end():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter(CODE, owner=0.1))
    assert digits(ev) == list(CODE)                 # nothing mid-code shows which digit gave them away
    assert kinds(ev).count("stranger") == 1 and "open" not in kinds(ev)
    assert p.fails == 1 and p.state == "locked"


def test_one_code_is_at_most_one_wrong_try():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter(CODE, owner=0.1) * 2)
    assert kinds(ev).count("stranger") == 2 and "lockout" not in kinds(ev) and p.fails == 2


def test_three_strangers_codes_lock_out():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter(CODE, owner=0.1) * 3)
    assert kinds(ev).count("stranger") == 3 and "lockout" in kinds(ev) and p.state == "lockout"


def test_a_strangers_wrong_code_is_reported_as_a_stranger():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, enter((0, 0, 0, 0), owner=0.1))
    assert kinds(ev).count("stranger") == 1 and "wrong" not in kinds(ev)


def test_the_owner_is_judged_on_the_whole_codes_average():
    p = LP.LockPolicy(CODE, DURESS, owner_t=0.5)
    ev, _ = run(p, enter(CODE, owner=[0.9, 0.05, 0.9, 0.9]))      # one shaky digit: average 0.69
    assert "open" in kinds(ev)
    p = LP.LockPolicy(CODE, DURESS, owner_t=0.5)
    ev, _ = run(p, enter(CODE, owner=[0.9, 0.05, 0.05, 0.05]))    # one good digit isn't enough: 0.26
    assert "stranger" in kinds(ev) and "open" not in kinds(ev)


def test_the_owner_after_a_stranger_still_gets_in():
    p = LP.LockPolicy(CODE, DURESS)
    ev, t = run(p, enter(CODE, owner=0.1) + enter(CODE))
    assert "stranger" in kinds(ev) and "open" in kinds(ev) and p.fails == 0


def test_timeout_also_forgets_the_owner_scores():
    p = LP.LockPolicy(CODE, DURESS, owner_t=0.5)
    ev, t = run(p, enter(CODE[:3], owner=0.0) + [(LP.TIMEOUT_S + 1, NONE)])
    assert "timeout" in kinds(ev) and p.fails == 0
    ev, t = run(p, enter(CODE, owner=0.6), t0=t)    # 0.6 on its own; 0.34 if the zeros stayed
    assert "open" in kinds(ev)


def test_owner_threshold_comes_from_settings_then_the_model():
    meta = {"owner_threshold": 0.09, "owner_check": True}
    assert LP.owner_threshold(meta, {"owner_threshold": 0.01}) == 0.01
    assert LP.owner_threshold(meta, {"owner_threshold": 0}) == 0.0          # 0 turns the check off
    assert LP.owner_threshold(meta, {}) == 0.09
    assert LP.owner_threshold(meta, None) == 0.09
    assert LP.owner_threshold({"owner_threshold": 0.09, "owner_check": False}, {}) == 0.0


def test_make_policy_applies_the_settings():
    meta = {"owner_threshold": 0.09, "owner_check": True, "count_conf": 0.7}
    p = LP.make_policy(CODE, DURESS, meta, {"owner_threshold": 0.01, "open_s": 15})
    assert (p.owner_t, p.open_s, p.conf) == (0.01, 15.0, 0.7)
    p = LP.make_policy(CODE, DURESS, meta, {})
    assert (p.owner_t, p.open_s) == (0.09, LP.OPEN_S)
    ev, t = run(p, enter(CODE) + [(LP.OPEN_S + 1, NONE)])
    assert "relock" in kinds(ev)
    p = LP.make_policy(CODE, DURESS, meta, {"open_s": 15})
    ev, t = run(p, enter(CODE) + [(LP.OPEN_S + 1, NONE)])
    assert "open" in kinds(ev) and "relock" not in kinds(ev) and p.state == "open"


def test_timeout_starts_the_entry_over():
    p = LP.LockPolicy(CODE, DURESS)
    ev, t = run(p, enter(CODE[:2]) + [(LP.TIMEOUT_S + 1, NONE)])
    assert "timeout" in kinds(ev) and p.fails == 0
    ev, t = run(p, enter(CODE), t0=t)
    assert "open" in kinds(ev)


def test_same_result_at_board_and_laptop_frame_rates():
    for fps in (4, 10, 30):
        p = LP.LockPolicy(CODE, DURESS)
        ev, _ = run(p, enter(CODE), fps=fps)
        assert digits(ev) == list(CODE) and "open" in kinds(ev), fps


def test_relocks_after_open_s():
    p = LP.LockPolicy(CODE, DURESS)
    ev, t = run(p, enter(CODE) + [(LP.OPEN_S + 1, NONE)])
    assert "relock" in kinds(ev) and p.state == "locked"


def test_hand_already_on_the_mat_at_start_does_not_count():
    p = LP.LockPolicy(CODE, DURESS)
    ev, _ = run(p, [(3.0, d(3))])
    assert digits(ev) == []


def test_status_never_shows_the_digits():
    p = LP.LockPolicy(CODE, DURESS)
    run(p, enter(CODE[:2]))
    s = p.status(100.0)
    assert s["entered"] == 2
    assert list(CODE[:2]) not in s.values() and tuple(CODE[:2]) not in s.values()


@pytest.mark.parametrize("code, duress", [((), None), ((1, 2, 3, 6), None), ((1, 2, 3, 4), (1, 2, 3, 4)),
                                          ((1, 2, 4), (1, 2, 4, 5))])
def test_bad_codes_are_rejected(code, duress):
    with pytest.raises(ValueError):
        LP.LockPolicy(code, duress)


def test_new_codes_are_three_different_digits_1_to_5():
    assert LP.check_code("241", "code", LP.CODE_LEN, low=1, distinct=True) == (2, 4, 1)
    for bad in ("2241", "24", "221", "201", "261"):
        with pytest.raises(ValueError):
            LP.check_code(bad, "code", LP.CODE_LEN, low=1, distinct=True)


def test_a_three_digit_code_opens():
    p = LP.LockPolicy((2, 4, 1), (1, 5, 2))
    ev, _ = run(p, enter((2, 4, 1)))
    assert digits(ev) == [2, 4, 1] and "open" in kinds(ev) and p.status(0)["code_len"] == 3


# ---- The button (rule 9) ----------------------------------------------------------------

def awake(p, t=0.0):
    ev = p.press(t)
    assert kinds(ev) == ["wake"] and p.state == "locked"
    return t


def test_with_the_button_it_sleeps_until_pressed():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    assert p.state == "idle" and p.status(0)["state"] == "idle"
    ev, t = run(p, enter(CODE))
    assert digits(ev) == [] and "open" not in kinds(ev) and p.state == "idle"
    awake(p, t)
    ev, t = run(p, enter(CODE), t0=t)
    assert digits(ev) == list(CODE) and "open" in kinds(ev)


def test_it_goes_back_to_sleep_after_opening():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    awake(p)
    ev, t = run(p, enter(CODE) + [(LP.OPEN_S + 1, NONE)])
    assert "open" in kinds(ev) and "relock" in kinds(ev) and p.state == "idle"
    ev, t = run(p, enter(CODE), t0=t)
    assert digits(ev) == []


def test_one_code_per_press():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    awake(p)
    ev, t = run(p, enter((0, 0, 0, 0)))
    assert "wrong" in kinds(ev) and p.state == "idle" and p.fails == 1
    ev, t = run(p, enter(CODE), t0=t)                 # no press: nothing counts
    assert digits(ev) == []
    awake(p, t)
    ev, t = run(p, enter(CODE), t0=t)
    assert "open" in kinds(ev) and p.fails == 0


def test_three_wrong_presses_lock_out_and_the_button_waits():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    t = 0.0
    for _ in range(3):
        awake(p, t)
        ev, t = run(p, enter((0, 0, 0, 0)), t0=t)
    assert "lockout" in kinds(ev) and p.state == "lockout"
    assert p.press(t) == [] and p.state == "lockout"
    ev, t = run(p, [(LP.LOCKOUT_S, NONE)], t0=t)
    assert "lockout_over" in kinds(ev) and p.state == "idle" and p.fails == 0


def test_awake_with_nothing_shown_goes_back_to_sleep():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    awake(p)
    ev, t = run(p, [(LP.TIMEOUT_S + 1, NONE)])
    assert "timeout" in kinds(ev) and p.state == "idle" and p.fails == 0


def test_pressing_while_open_locks_now():
    p = LP.LockPolicy(CODE, DURESS, button=True, open_s=30)
    awake(p)
    ev, t = run(p, enter(CODE))
    assert p.state == "open"
    ev = p.press(t)
    assert kinds(ev) == ["relock"] and p.state == "idle"


def test_pressing_mid_code_starts_it_over():
    p = LP.LockPolicy(CODE, DURESS, button=True)
    awake(p)
    ev, t = run(p, enter(CODE[:2]))
    assert len(p.entered) == 2
    awake(p, t)
    assert p.entered == [] and p.fails == 0
    ev, t = run(p, enter(CODE), t0=t)
    assert "open" in kinds(ev)


def test_confidence_bar_comes_from_settings_then_the_model():
    meta = {"count_conf": 0.8}
    assert LP.make_policy(CODE, DURESS, meta, {"conf": 0.6}).conf == 0.6
    assert LP.make_policy(CODE, DURESS, meta, {}).conf == 0.8


def test_a_lower_bar_counts_a_less_sure_digit():
    seen = {}
    for bar in (0.8, 0.6):
        p = LP.LockPolicy(CODE, DURESS, conf=bar)
        ev, t = [], 0.0
        for secs, label, conf in [(GAP, NONE, 0.95), (HOLD, d(3), 0.7)]:      # a 3 held at 70% sure
            for _ in range(int(round(secs * 10))):
                ev += p.update(t, probs(label, conf), 0.95)
                t += 0.1
        seen[bar] = digits(ev)
    assert seen == {0.8: [], 0.6: [3]}


def test_lockout_length_comes_from_settings():
    p = LP.make_policy(CODE, DURESS, {}, {"lockout_s": 10})
    ev, t = run(p, enter((0, 0, 0, 0)) * 3)
    assert "lockout" in kinds(ev) and p.lockout_s == 10
    ev, t = run(p, [(11, NONE)], t0=t)
    assert "lockout_over" in kinds(ev) and p.fails == 0


def test_the_button_setting_reaches_the_policy():
    meta = {"owner_threshold": 0.09}
    assert LP.make_policy(CODE, DURESS, meta, {"button": True}).state == "idle"
    assert LP.make_policy(CODE, DURESS, meta, {}).state == "locked"
