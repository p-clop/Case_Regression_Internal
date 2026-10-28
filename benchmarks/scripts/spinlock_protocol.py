"""Explore a finite, manually mapped SC abstraction of the B02 CAS lock."""
from collections import deque
from dataclasses import dataclass, replace, asdict
import json


PROTOCOL_CONTRACT = {
    "schema": "b02-spinlock-protocol-1",
    "workers": 2,
    "baseline_rounds": [1, 2, 3],
    "control_rounds": 2,
    "semantics": "single-lock SC state machine; not a C11/RVWMO full-program model",
    "expected": {"atomic_cas": "PASS", "split_cas": "FAIL", "missing_expected_reset": "FAIL"},
}


@dataclass(frozen=True)
class Worker:
    pc: str = "cas"
    expected: int = 0
    completed: int = 0


@dataclass(frozen=True)
class State:
    locked: int = 0
    workers: tuple = (Worker(), Worker())


def successors(state, rounds, variant):
    for index, w in enumerate(state.workers):
        locked = state.locked
        if w.pc == "done":
            continue
        if w.pc == "cas":
            if locked == w.expected:
                if variant == "split_cas":
                    nxt, action = replace(w, pc="write"), "split_compare_succeeds"
                else:
                    locked = 1
                    nxt, action = replace(w, pc="critical"), "cas_success"
            else:
                nxt, action = replace(w, pc="wait", expected=locked), "cas_failure_updates_expected"
        elif w.pc == "write":
            locked = 1
            nxt, action = replace(w, pc="critical"), "split_write_one"
        elif w.pc == "wait":
            # A nonzero observation is an explicit stutter; visited states merge it.
            nxt = replace(w, pc="reset") if locked == 0 else w
            action = "wait_observes_zero" if locked == 0 else "wait_observes_one"
        elif w.pc == "reset":
            expected = w.expected if variant == "missing_expected_reset" else 0
            nxt, action = replace(w, pc="cas", expected=expected), "reset_expected"
        elif w.pc == "critical":
            nxt, action = replace(w, pc="unlock"), "finish_critical_section"
        elif w.pc == "unlock":
            locked = 0
            completed = w.completed + 1
            # Each new call initializes a fresh exp=0, even in the reset mutant.
            nxt = Worker("done" if completed == rounds else "cas", 0, completed)
            action = "release_unlock"
        else:
            raise ValueError(f"unknown protocol location: {w.pc}")
        workers = list(state.workers)
        workers[index] = nxt
        yield State(locked, tuple(workers)), index, action


def explore(rounds, variant="atomic_cas"):
    if type(rounds) is not int or not 1 <= rounds <= 3:
        raise ValueError("rounds must be in 1..3")
    if variant not in PROTOCOL_CONTRACT["expected"]:
        raise ValueError("unknown protocol variant")
    initial = State()
    queue, parents = deque([initial]), {initial: None}
    transitions, terminals, actions = 0, 0, {}
    while queue:
        state = queue.popleft()
        holders = [i for i, w in enumerate(state.workers) if w.pc in ("critical", "unlock")]
        if len(holders) > 1 or (holders and state.locked != 1):
            witness = []
            current = state
            while parents[current] is not None:
                prior, worker, action = parents[current]
                witness.append({"worker": worker, "action": action, "state": asdict(current)})
                current = prior
            witness.reverse()
            return {"status": "FAIL", "variant": variant, "rounds_per_worker": rounds,
                    "states_discovered": len(parents), "transitions": transitions,
                    "violation": "overlapping_critical_sections_or_unlocked_holder",
                    "counterexample": witness, "actions": actions}
        if all(w.pc == "done" for w in state.workers):
            terminals += 1
        for nxt, worker, action in successors(state, rounds, variant):
            transitions += 1
            actions[action] = actions.get(action, 0) + 1
            if nxt not in parents:
                parents[nxt] = (state, worker, action)
                queue.append(nxt)
    return {"status": "PASS" if terminals else "UNKNOWN", "variant": variant,
            "rounds_per_worker": rounds, "states_discovered": len(parents),
            "transitions": transitions, "terminal_states": terminals,
            "counterexample": [], "actions": actions}


def run_checks():
    results = []
    for rounds in PROTOCOL_CONTRACT["baseline_rounds"]:
        results.append(explore(rounds))
    for variant in ("split_cas", "missing_expected_reset"):
        results.append(explore(PROTOCOL_CONTRACT["control_rounds"], variant))
    for result in results:
        result["expected"] = PROTOCOL_CONTRACT["expected"][result["variant"]]
        result["comparison_status"] = ("UNKNOWN" if result["status"] == "UNKNOWN" else
                                       "PASS" if result["status"] == result["expected"] else "FAIL")
    states = [r["comparison_status"] for r in results]
    return {"schema": PROTOCOL_CONTRACT["schema"],
            "status": "FAIL" if "FAIL" in states else "UNKNOWN" if "UNKNOWN" in states else "PASS",
            "scope": PROTOCOL_CONTRACT["semantics"], "checks": results,
            "formal_review": "UNKNOWN", "full_program_verification": "UNKNOWN"}


if __name__ == "__main__":
    result = run_checks()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit({"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["status"]])
