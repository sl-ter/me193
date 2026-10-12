"""
Q-learning a straight crawl (Silly Walks).

    python qlearn.py --sim               # train against the simulated crawler, no hardware
    python qlearn.py                     # train the real robot (resumes qtable.json if it exists)
    python qlearn.py --fresh             # start over from an all-zero table
    python qlearn.py --run               # no learning, no exploring: just walk using the table

"Training" = running the loop below over and over. Each step: read the yaw
error -> state, pick a correction (random with probability epsilon,
otherwise the best one in the table), hold it for STEP_TIME, read the yaw
again -> next state + reward, then nudge that one table cell toward
    reward + GAMMA * (best value available from the next state).
The robot is re-aimed by hand between episodes. The table and epsilon are
saved after every episode, so training can stop and resume across runs.
"""

import argparse
import bisect
import csv
import json
import os
import random
import time

from crawler import RealCrawler, SimCrawler, speeds_for

HERE = os.path.dirname(os.path.abspath(__file__))
QTABLE_PATH = os.path.join(HERE, "qtable.json")
LOG_PATH = os.path.join(HERE, "training_log.csv")
QTABLE_SIM_PATH = os.path.join(HERE, "qtable_sim.json")
LOG_SIM_PATH = os.path.join(HERE, "training_log_sim.csv")

# --- The table's shape (from the handout) -----------------------------------
# States: yaw error bins, symmetric about 0. Edges are |error| in degrees:
# |e| < 2 is state 4 (on target), 2..5 is state 3/5, ... >= 20 is state 0/8.
BIN_EDGES = [2, 5, 10, 20]
N_STATES = 2 * len(BIN_EDGES) + 1
STATE_NAMES = ["< -20", "-20..-10", "-10..-5", "-5..-2", "-2..+2",
               "+2..+5", "+5..+10", "+10..+20", "> +20"]

# Actions: differential correction in % speed. Negative = left faster = turn right.
ACTIONS = [-40, -20, 0, 20, 40]
ACTION_NAMES = ["A0 R-turn", "A1 gentle R", "A2 straight", "A3 gentle L", "A4 L-turn"]

# --- Learning settings -------------------------------------------------------
ALPHA = 0.3        # learning rate: how far each update moves a cell toward the new estimate
GAMMA = 0.9        # discount: how much the next state's best value counts
EPS_START = 1.0    # start fully random
EPS_DECAY = 0.98   # per step (handout step 7)
EPS_MIN = 0.05     # never stop exploring entirely while training

# --- Episode settings --------------------------------------------------------
STEP_TIME = 0.5          # s each action is held before measuring; aim for ~1 arm stroke
STEPS_PER_EPISODE = 30
GIVE_UP_YAW = 45         # deg; past this the episode ends (and counts as a failure)


def state_of(err):
    i = bisect.bisect_right(BIN_EDGES, abs(err))   # 0 (on target) .. 4 (worst)
    return 4 + i if err > 0 else 4 - i


def reward_of(err):
    e = abs(err)
    if e < 2:
        return 1.0
    if e < 10:
        return 0.0
    return -1.0


def best_action(q_row):
    """Argmax with random tie-breaking -- otherwise an all-zero row always
    picks A0 and the 'best' action is just whichever comes first."""
    top = max(q_row)
    return random.choice([a for a, v in enumerate(q_row) if v == top])


def load_table(path, fresh):
    if not fresh and os.path.exists(path):
        with open(path) as f:
            saved = json.load(f)
        print(f"Resuming {path}: {saved['steps']} steps so far, epsilon {saved['epsilon']:.3f}")
        return saved
    return {"q": [[0.0] * len(ACTIONS) for _ in range(N_STATES)],
            "epsilon": EPS_START, "steps": 0, "episodes": 0}


def save_table(table, path):
    with open(path, "w") as f:
        json.dump(table, f, indent=1)


def print_table(q, visits=None):
    header = f"{'state':>4} {'yaw err':>9} | " + " ".join(f"{n:>12}" for n in ACTION_NAMES)
    print(header)
    print("-" * len(header))
    for s in range(N_STATES):
        best = max(range(len(ACTIONS)), key=lambda a: q[s][a])
        cells = []
        for a in range(len(ACTIONS)):
            mark = "*" if a == best and any(q[s]) else " "
            cells.append(f"{q[s][a]:>11.2f}{mark}")
        tail = f"  ({visits[s]} visits)" if visits else ""
        print(f"{s:>4} {STATE_NAMES[s]:>9} | " + " ".join(cells) + tail)
    print("* = what the robot will do in that state when exploiting")


def run_episode(robot, table, episode, learn, sim, log_writer):
    q = table["q"]
    robot.reset_heading()
    err = robot.yaw()
    s = state_of(err)
    total_reward = 0.0
    on_target = 0
    visits = [0] * N_STATES

    for step in range(STEPS_PER_EPISODE):
        eps = table["epsilon"] if learn else 0.0

        # 3. choose: explore or exploit
        explored = random.random() < eps
        a = random.randrange(len(ACTIONS)) if explored else best_action(q[s])

        # 4. execute
        robot.drive(ACTIONS[a])
        if sim:
            robot.advance(STEP_TIME)
        else:
            time.sleep(STEP_TIME)

        # 5. observe
        err2 = robot.yaw()
        s2 = state_of(err2)
        r = reward_of(err2)
        failed = abs(err2) > GIVE_UP_YAW

        # 6. update: nudge Q(s,a) toward r + GAMMA * max Q(s'). A failure ends the
        # episode, so there is no future value to add.
        if learn:
            future = 0.0 if failed else max(q[s2])
            q[s][a] = (1 - ALPHA) * q[s][a] + ALPHA * (r + GAMMA * future)
            # 7. decay epsilon
            table["epsilon"] = max(EPS_MIN, table["epsilon"] * EPS_DECAY)
            table["steps"] += 1

        visits[s] += 1
        total_reward += r
        on_target += r > 0
        left, right = speeds_for(ACTIONS[a])
        tag = "explore" if explored else "exploit"
        if not sim:
            print(f"  step {step:2d}  yaw {err:+6.1f} (s{s}) -> {ACTION_NAMES[a]:<12} "
                  f"[{left:3d}/{right:3d}] {tag}  -> yaw {err2:+6.1f} (s{s2})  r {r:+.0f}  "
                  f"Q {q[s][a]:+.2f}  eps {eps:.2f}")
        log_writer.writerow([episode, step, f"{err:.2f}", s, a, f"{err2:.2f}", s2, r,
                             f"{q[s][a]:.4f}", f"{eps:.4f}", int(explored), int(learn)])

        # 8. the next state becomes the current one
        err, s = err2, s2
        if failed:
            break

    robot.stop()
    n = step + 1
    return {"steps": n, "reward": total_reward, "on_target": on_target / n,
            "failed": failed, "final_yaw": err, "visits": visits}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true", help="simulated crawler instead of the robot")
    ap.add_argument("--fresh", action="store_true", help="ignore any saved table and start from zeros")
    ap.add_argument("--run", action="store_true", help="exploit only: no exploring, no table updates")
    ap.add_argument("--episodes", type=int, default=None,
                    help="stop after N episodes (default: 60 in --sim, until you quit on the robot)")
    ap.add_argument("--seed", type=int, default=None, help="random seed (sim reproducibility)")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    learn = not args.run
    episodes = args.episodes or (60 if args.sim else 10**9)

    # The sim keeps its own table so practice runs never overwrite the robot's.
    qtable_path = QTABLE_SIM_PATH if args.sim else QTABLE_PATH
    log_path = LOG_SIM_PATH if args.sim else LOG_PATH
    table = load_table(qtable_path, args.fresh)
    if args.fresh and os.path.exists(log_path):
        os.remove(log_path)

    robot = SimCrawler(seed=args.seed) if args.sim else RealCrawler()
    new_log = not os.path.exists(log_path)
    log_file = open(log_path, "a", newline="")
    log = csv.writer(log_file)
    if new_log:
        log.writerow(["episode", "step", "yaw", "state", "action", "next_yaw", "next_state",
                      "reward", "q_new", "epsilon", "explored", "learning"])

    ep_run = 0
    try:
        for _ in range(episodes):
            if not args.sim:
                ans = input("\nAim the robot straight, then Enter to crawl (q + Enter to quit): ")
                if ans.strip().lower() == "q":
                    break
            ep = table["episodes"] + 1 if learn else ep_run + 1
            ep_run = ep
            res = run_episode(robot, table, ep, learn, args.sim, log)
            log_file.flush()
            if learn:
                table["episodes"] = ep
                save_table(table, qtable_path)
            end = "FELL OFF COURSE" if res["failed"] else "ok"
            print(f"episode {ep:3d}: {res['steps']:2d} steps, reward {res['reward']:+5.0f}, "
                  f"on target {100 * res['on_target']:3.0f}%, final yaw {res['final_yaw']:+6.1f}, "
                  f"eps {table['epsilon'] if learn else 0:.3f}  [{end}]")
            if not args.sim:
                print_table(table["q"])
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        robot.close()
        log_file.close()
        if learn:
            save_table(table, qtable_path)
        print()
        print_table(table["q"])
        print(f"\nTable saved to {qtable_path}; per-step log in {log_path}")


if __name__ == "__main__":
    main()
