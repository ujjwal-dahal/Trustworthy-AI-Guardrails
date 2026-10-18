"""
tradeoff_analysis.py
--------------------
Threshold badal'dā safety vs usability kasari change huncha - test cases mai rerun garera dekhaucha.
(Report ko "Guardrail Trade-offs" section ko evidence.)   Run: python evaluation/tradeoff_analysis.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.run_evaluation import run_case          # noqa: E402
from evaluation.test_cases import CASES                 # noqa: E402
from guardrails import config                           # noqa: E402


def sweep(guardrail, attr, values):
    print(f"\n{guardrail}  (config.{attr})")
    print("value | TP FP FN TN | precision recall")
    for v in values:
        old = getattr(config, attr)
        setattr(config, attr, v)
        tp = fp = fn = tn = 0
        for c in CASES:
            if c["guardrail"] != guardrail:
                continue
            _, ef, af, _ = run_case(c)
            tp += ef and af; fp += (not ef) and af; fn += ef and (not af); tn += (not ef) and (not af)
        setattr(config, attr, old)
        p = f"{tp/(tp+fp):.2f}" if tp + fp else "n/a"
        r = f"{tp/(tp+fn):.2f}" if tp + fn else "n/a"
        print(f"{v:<5} | {tp:2} {fp:2} {fn:2} {tn:2} | {p:>9} {r:>6}")


if __name__ == "__main__":
    sweep("input_injection", "INJECTION_BLOCK_THRESHOLD", [0.25, 0.5, 0.75])
    sweep("output_grounded", "GROUNDEDNESS_MIN_SCORE", [0.6, 0.8, 1.0])
    sweep("output_grounded", "SENTENCE_SUPPORT_THRESHOLD", [0.4, 0.6, 0.8])
