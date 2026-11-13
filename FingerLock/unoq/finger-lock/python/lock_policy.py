"""The safe's rules (its lock policy), on their own so they can be tested
without a camera (FingerLock/test_lock_policy.py). The board's main.py and the
laptop's laptop_lock.py feed it one camera frame's answers at a time with
update(), and it says what happened.

For every frame the network gives two answers: the probability of each count
(no hand, 0, 1, 2, 3, 4, 5 fingers) and the probability that the hand is the
owner's. The rules:

1. Reading: the most likely count, if its probability is at least CONF
   (settings.json's "conf" on the board and the laptop). Otherwise the
   frame is "unsure".
2. A digit (0-5) counts once the same reading has held for HOLD_S seconds.
   That's seconds, not frames, so the rules behave the same at the board's
   frame rate and the laptop's. A different reading has to last longer than
   GRACE_S to take over (so a one-frame blip doesn't restart the hold), and
   when it does take over, its own hold dates from when it first appeared.
3. Each digit also gets an owner score: the owner probability averaged over
   its hold. The owner is judged once per code, on the average of those
   scores over all the code's digits (rule 5), not digit by digit. So one
   shaky digit doesn't sink the owner, a stranger can't tell which digit
   gave them away, and one code is at most one wrong try.
4. After each digit the hand has to leave the mat (no hand for CLEAR_S)
   before the next digit can start. That's how a code like 3-3 works, and why
   the frames of a hand moving in or out never count.
5. Once as many digits are in as the code has (CODE_LEN = 3 for codes set
   with set_codes.py, as the brief asks): if the code's owner score is
   below OWNER_T, the hand is a stranger's. The attempt is refused, it counts as a wrong try,
   and the safe reports a stranger (main.py takes a photo). Otherwise the
   real code opens the safe. The duress code opens it exactly the same way,
   but the event says duress=True so main.py can raise a silent alarm.
   Anything else is a wrong try.
6. MAX_FAILS wrong tries in a row (wrong codes or strangers' codes) lock the
   safe for LOCKOUT_S (settings.json's "lockout_s" on the board and the
   laptop), which also reports an intruder (photo).
7. If no new digit comes for TIMEOUT_S while entering a code, the entry
   starts over. That isn't a wrong try.
8. The safe stays open for OPEN_S (settings.json's "open_s" on the board and
   the laptop), then locks again. The door has to be shut by then: the latch
   arm swings back over its edge either way.
9. The button (button=True; settings.json "button": true): the brief's "walk
   up, push a button, the LEDs light up". The safe sleeps, LEDs dark, until
   press() wakes it for one code. After that code (opened, wrong or a
   stranger's), or TIMEOUT_S without a digit, it goes back to sleep.
   Pressing while it's open locks it at once (shut the door, press); pressing
   while a code is going in starts the code over; during a lockout the
   button does nothing. While asleep the camera is still followed, but
   nothing counts.
"""
from dataclasses import dataclass, field

LABELS = ["none", "0", "1", "2", "3", "4", "5"]
NONE = 0                # class index of "no hand"
UNSURE = -1             # reading when no class reaches CONF

# Defaults (the trained model's meta can override CONF and OWNER_T, and
# settings.json can override OWNER_T again: see owner_threshold())
HOLD_S = 0.8
GRACE_S = 0.25
CONF = 0.8
OWNER_T = 0.5
CLEAR_S = 0.3
CODE_LEN = 3            # new codes (set_codes.py): 3 different digits, each 1-5, as the brief asks
MAX_FAILS = 3
LOCKOUT_S = 60.0
TIMEOUT_S = 10.0
OPEN_S = 5.0
EPS = 1e-6              # for comparing times (frame times are sums of floats)


@dataclass
class Event:
    kind: str               # wake, digit, open, wrong, stranger, lockout, timeout, relock, lockout_over
    t: float
    digit: int = None       # for "digit"
    duress: bool = False    # for "open"
    detail: dict = field(default_factory=dict)


def check_code(code, name, code_len=None, low=0, distinct=False):
    """A code as a tuple of digits. code_len None takes any length; set_codes.py
    asks for the brief's format (code_len=CODE_LEN, low=1, distinct=True)."""
    code = tuple(int(d) for d in code)
    what = (f"{code_len} " if code_len else "") + ("different digits" if distinct else "digits") + f", each {low}-5"
    if (not code or (code_len and len(code) != code_len) or not all(low <= d <= 5 for d in code)
            or (distinct and len(set(code)) != len(code))):
        raise ValueError(f"{name} must be {what} (got {len(code)} digits)")
    return code


def owner_threshold(meta, settings=None):
    """The owner threshold the safe uses: settings.json's "owner_threshold" if it
    sets one (0 turns the owner check off), otherwise the trained model's (0 if
    the model had no strangers to test its owner check on)."""
    if (settings or {}).get("owner_threshold") is not None:
        return float(settings["owner_threshold"])
    return float(meta.get("owner_threshold", OWNER_T)) if meta.get("owner_check", True) else 0.0


class LockPolicy:
    def __init__(self, code, duress=None, hold_s=HOLD_S, grace_s=GRACE_S, conf=CONF,
                 owner_t=OWNER_T, clear_s=CLEAR_S, code_len=None, max_fails=MAX_FAILS,
                 lockout_s=LOCKOUT_S, timeout_s=TIMEOUT_S, open_s=OPEN_S, button=False):
        self.code = check_code(code, "code", code_len)
        code_len = len(self.code)
        self.duress = check_code(duress, "duress code", code_len) if duress is not None else None
        if self.duress == self.code:
            raise ValueError("the duress code must differ from the real code")
        self.hold_s, self.grace_s, self.conf, self.owner_t = hold_s, grace_s, conf, owner_t
        self.clear_s, self.code_len, self.max_fails = clear_s, code_len, max_fails
        self.lockout_s, self.timeout_s, self.open_s = lockout_s, timeout_s, open_s
        self.button = button

        # idle (asleep: button mode only), locked (taking a code; "entering" = digits in), open or lockout
        self.state = "idle" if button else "locked"
        self.entered = []               # digits so far (never published or displayed)
        self.digit_owner = []           # each entered digit's owner score (its hold's average)
        self.fails = 0
        self.need_clear = True          # a hand already on the mat at start doesn't count
        self.until = 0.0                # when "open" or "lockout" ends
        self.last_digit_t = 0.0
        # the reading being held
        self.cand = UNSURE
        self.cand_since = 0.0
        self.cand_seen = 0.0            # last frame that agreed with it
        self.owner_sum, self.owner_n = 0.0, 0
        # a different reading waiting out the grace period
        self.pend = None                # None = nothing pending
        self.pend_since = 0.0
        self.pend_owner = [0.0, 0]
        self.last = {"reading": UNSURE, "conf": 0.0, "owner_p": None}

    # ---- helpers -------------------------------------------------------------------

    def _take_over(self):
        """The pending reading becomes the one being held, from when it first appeared."""
        self.cand, self.cand_since = self.pend, self.pend_since
        self.owner_sum, self.owner_n = self.pend_owner
        self.pend, self.pend_owner = None, [0.0, 0]

    def _clear_entry(self):
        self.entered, self.digit_owner = [], []

    def _wrong(self, t, kind, events, detail=None):
        """A refused attempt (a wrong code, or a stranger's code)."""
        self._clear_entry()
        self.fails += 1
        events.append(Event(kind, t, detail=dict(detail or {}, fails=self.fails)))
        if self.fails >= self.max_fails:
            self.state, self.until = "lockout", t + self.lockout_s
            events.append(Event("lockout", t, detail={"seconds": self.lockout_s}))
        elif self.button:
            self.state = "idle"         # one code per press of the button

    def _rest(self):
        """After opening or a lockout: asleep (with the button) or ready for a code."""
        self.state = "idle" if self.button else "locked"
        self.need_clear = True

    def _track(self, t, reading, owner_p):
        """Rule 2's bookkeeping: which reading is being held. False while a
        different reading waits out the grace period (maybe a blip)."""
        if reading == self.cand:
            self.cand_seen = t
            self.pend = None
            self.owner_sum += owner_p
            self.owner_n += 1
            return True
        if reading != self.pend:
            self.pend, self.pend_since, self.pend_owner = reading, t, [0.0, 0]
        self.pend_owner[0] += owner_p
        self.pend_owner[1] += 1
        if self.cand != UNSURE and t - self.cand_seen <= self.grace_s + EPS:
            return False
        self._take_over()
        self.cand_seen = t
        return True

    def _finish_code(self, t, events):
        entered = tuple(self.entered)
        owner_avg = sum(self.digit_owner) / max(len(self.digit_owner), 1)
        self._clear_entry()
        detail = {"owner_avg": round(owner_avg, 3)}
        if owner_avg < self.owner_t:
            self._wrong(t, "stranger", events, detail)
        elif entered == self.code or (self.duress is not None and entered == self.duress):
            self.fails = 0
            self.state, self.until = "open", t + self.open_s
            events.append(Event("open", t, duress=entered == self.duress, detail=detail))
        else:
            self._wrong(t, "wrong", events, detail)

    # ---- the rules -----------------------------------------------------------------

    def press(self, t):
        """The button (rule 9). Returns a list of Events."""
        events = []
        if self.state == "open":                # shut the door, press: locked now
            self._rest()
            events.append(Event("relock", t, detail={"by": "button"}))
        elif self.state in ("idle", "locked"):  # wake up for a code, or start the code over
            self._clear_entry()
            self.state, self.need_clear, self.last_digit_t = "locked", True, t
            events.append(Event("wake", t))
        return events                           # lockout: the button does nothing

    def update(self, t, count_probs, owner_p):
        """One frame: t in seconds, count_probs (7 probabilities, LABELS order),
        owner_p (probability the hand is the owner's). Returns a list of Events."""
        events = []
        best = max(range(len(count_probs)), key=lambda i: count_probs[i])
        conf = float(count_probs[best])
        reading = best if conf >= self.conf else UNSURE
        owner_p = float(owner_p)
        self.last = {"reading": reading, "conf": conf, "owner_p": owner_p}

        if self.state == "lockout":
            if t < self.until:
                return events
            self.fails = 0
            self._rest()
            events.append(Event("lockout_over", t))
        if self.state == "open":
            if t < self.until:
                return events
            self._rest()
            events.append(Event("relock", t))

        # Rule 7 (rule 9 with the button: awake with nothing shown also times out, back to sleep)
        if self.state == "locked" and (self.entered or self.button) and t - self.last_digit_t >= self.timeout_s:
            self._clear_entry()
            if self.button:
                self.state = "idle"
            events.append(Event("timeout", t))

        # 1. Which reading is being held? (followed while asleep too, so waking up starts fresh)
        if not self._track(t, reading, owner_p) or self.state == "idle":
            return events

        # 2. Act on it.
        held = t - self.cand_since
        if self.cand == NONE:
            if held + EPS >= self.clear_s:
                self.need_clear = False
            return events
        if self.cand == UNSURE or self.need_clear or held + EPS < self.hold_s:
            return events

        owner_avg = self.owner_sum / max(self.owner_n, 1)
        self.need_clear = True
        digit = self.cand - 1
        self.entered.append(digit)
        self.digit_owner.append(owner_avg)
        self.last_digit_t = t
        events.append(Event("digit", t, digit=digit,
                            detail={"owner_avg": round(owner_avg, 3), "n": len(self.entered)}))
        if len(self.entered) >= self.code_len:
            self._finish_code(t, events)
        return events

    def status(self, t):
        """For the LED matrix and the MQTT status. Never includes the digits."""
        hold = 0.0
        if self.state == "locked" and self.cand not in (UNSURE, NONE) and not self.need_clear:
            hold = min(1.0, (t - self.cand_since) / self.hold_s)
        reading = self.last["reading"]
        return {
            "state": self.state,
            "entered": len(self.entered),
            "code_len": self.code_len,
            "reading": None if reading == UNSURE else LABELS[reading],
            "conf": round(self.last["conf"], 3),
            "owner_p": None if self.last["owner_p"] is None else round(self.last["owner_p"], 3),
            "hold": round(hold, 2),
            "need_clear": self.need_clear,
            "fails": self.fails,
            "left_s": round(max(0.0, self.until - t), 1) if self.state in ("open", "lockout") else 0.0,
        }


def make_policy(code, duress, meta, settings=None):
    """The rules as the board and the laptop run them: the trained model's
    confidence and owner threshold (meta), then settings.json's overrides
    ("conf", "owner_threshold", "open_s", "lockout_s") and whether it waits for the button ("button")."""
    settings = settings or {}
    conf = settings.get("conf")
    conf = float(conf) if conf is not None else float(meta.get("count_conf", CONF))
    return LockPolicy(code, duress, conf=conf, owner_t=owner_threshold(meta, settings),
                      open_s=float(settings.get("open_s", OPEN_S)), lockout_s=float(settings.get("lockout_s", LOCKOUT_S)),
                      button=bool(settings.get("button", False)))
