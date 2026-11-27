"""Run the OpsPilot benchmark and compare the current rules with the legacy (V3) rules.

    PYTHONPATH=. python evaluation/benchmark.py            # print the report
    PYTHONPATH=. python evaluation/benchmark.py --check    # also fail if the current rules regress

All cases are synthetic and generated deterministically by evaluation/cases.py.
"""
import json, logging, os, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["OPSPILOT_REASONER"] = "rules"
logging.disable(logging.CRITICAL)

from app.store import reset, STATE  # noqa: E402
from app.agent import investigate, collect_evidence  # noqa: E402
from evaluation.cases import build_cases  # noqa: E402
from evaluation.legacy_rules import legacy_rank  # noqa: E402

CATEGORIES = [
    ("known", "Known failures diagnosed correctly"),
    ("near_miss", "Near misses: abstained instead of forcing a known cause"),
    ("unseen", "Unseen failure types: abstained"),
    ("compound", "Two simultaneous failures: abstained"),
    ("unexplained", "Diagnosis correct and unexplained signal flagged"),
    ("healthy", "Healthy telemetry: no incident reported"),
    ("edge", "Edge cases chosen to expose limits (no threshold)"),
]

# Minimum pass rates for --check (current rules only).
THRESHOLDS = {"known": 0.95, "near_miss": 0.9, "unseen": 0.9, "compound": 0.8, "unexplained": 0.8, "healthy": 0.9}


def load(case):
    reset()
    STATE["metrics"].update(case["metrics"])
    STATE["logs"] += case["logs"]
    STATE["deployments"] += case["deployments"]


def run():
    cases = build_cases()
    tally = defaultdict(lambda: {"n": 0, "current": 0, "legacy": 0})
    false_abstain = {"current": 0, "legacy": 0}
    failures = []
    for c in cases:
        load(c)
        evidence, anomaly = collect_evidence()
        legacy = legacy_rank(STATE["metrics"], evidence, anomaly)
        r = investigate("diagnose incident")
        ok_current = r.root_cause_key == c["expected"]
        ok_legacy = legacy == c["expected"]
        if c["category"] == "unexplained":
            ok_current = ok_current and c["must_flag"] in r.unexplained_signals
            ok_legacy = False  # the legacy rules have no way to flag unexplained signals
        t = tally[c["category"]]
        t["n"] += 1; t["current"] += ok_current; t["legacy"] += ok_legacy
        if c["category"] == "known":
            false_abstain["current"] += r.root_cause_key in ("unknown", "healthy")
            false_abstain["legacy"] += legacy in ("unknown", "healthy")
        if not ok_current:
            note = f' ({c["note"]})' if c.get("note") else ""
            failures.append(f'{c["id"]}: expected {c["expected"]}, got {r.root_cause_key}{note}')
    return cases, tally, false_abstain, failures


def main():
    cases, tally, false_abstain, failures = run()
    print(f"OpsPilot benchmark: {len(cases)} synthetic cases, rules reasoner\n")
    print(f'{"Category":<58}{"Cases":>6}{"Current":>10}{"Legacy V3":>11}')
    print("-" * 85)
    for key, label in CATEGORIES:
        t = tally[key]
        print(f'{label:<58}{t["n"]:>6}{t["current"] / t["n"]:>10.0%}{t["legacy"] / t["n"]:>11.0%}')
    known_n = tally["known"]["n"]
    print(f'{"False abstentions on known failures (lower is better)":<58}{known_n:>6}'
          f'{false_abstain["current"] / known_n:>10.0%}{false_abstain["legacy"] / known_n:>11.0%}')
    if failures:
        print("\nCurrent-rules misses (all expected to be edge cases):")
        for f in failures:
            print("  " + f)
    summary = {k: {"cases": v["n"], "current": round(v["current"] / v["n"], 3), "legacy": round(v["legacy"] / v["n"], 3)} for k, v in tally.items()}
    summary["false_abstention_known"] = {k: round(v / known_n, 3) for k, v in false_abstain.items()}
    Path(__file__).with_name("results.json").write_text(json.dumps(summary, indent=2) + "\n")
    if "--check" in sys.argv:
        bad = [k for k, th in THRESHOLDS.items() if tally[k]["current"] / tally[k]["n"] < th]
        if bad:
            print(f"\nFAILED thresholds: {bad}")
            sys.exit(1)
        print("\nAll thresholds met.")


if __name__ == "__main__":
    main()
