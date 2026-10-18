"""
run_evaluation.py
-----------------
Sabai test cases chalauchha, expected vs actual compare garchha, ra yi files banaucha:
  results/test_results.csv   - har case: input, reference, expected, actual, PASS/FAIL
  results/test_results.md    - tyahi, markdown table ma (report ma paste garna sajilo)
  results/metrics.json       - precision / recall / F1 / FP / FN per guardrail
  results/metrics.md         - metrics table

Run:  python evaluation/run_evaluation.py     (project root bata)
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.test_cases import CASES                        # noqa: E402
from guardrails import GuardrailPipeline, KnowledgeBase, MockLLM, ScriptedLLM  # noqa: E402
from guardrails.groundedness import GroundednessValidator       # noqa: E402
from guardrails.injection import InjectionDetector              # noqa: E402
from guardrails.output_sensitive import SensitiveOutputDetector  # noqa: E402
from guardrails.pii import PIIDetector                          # noqa: E402
from guardrails.schema import SchemaValidator                   # noqa: E402
from guardrails.topics import TopicClassifier                   # noqa: E402

RESULTS = ROOT / "results"
KB = KnowledgeBase()
PII, INJ, TOP = PIIDetector(), InjectionDetector(), TopicClassifier()
SCH, GRD, SEN = SchemaValidator(), GroundednessValidator(), SensitiveOutputDetector()

GUARDRAIL_LABELS = {
    "input_pii": "Input: PII detection", "input_injection": "Input: Prompt-injection",
    "input_topic": "Input: Sensitive-topic", "output_schema": "Output: Schema validation",
    "output_grounded": "Output: Groundedness", "output_sensitive": "Output: Sensitive-info",
}


def run_case(c):
    """Return (passed, expected_flag, actual_flag, actual_dict). flag = 'guardrail le kehi pakdiyo/block garyo' (positive class)."""
    g, inp, exp = c["guardrail"], c["input"], c["expected"]

    if g == "input_pii":
        types = sorted({m.type for m in PII.detect(inp)})
        return types == sorted(exp["types"]), bool(exp["types"]), bool(types), {"types": types}

    if g == "input_injection":
        r = INJ.analyze(inp)
        action = "BLOCK" if r.label == "INJECTION" else "ALLOW"
        return action == exp["action"], exp["action"] == "BLOCK", action == "BLOCK", {"action": action, "score": r.score, "rules": r.rules}

    if g == "input_topic":
        r = TOP.classify(inp)
        return r.category == exp["category"], exp["category"] is not None, r.category is not None, {"category": r.category}

    if g == "output_schema":
        r = SCH.validate(inp)
        return r.valid == exp["valid"], not exp["valid"], not r.valid, {"valid": r.valid, "errors": r.errors}

    if g == "output_grounded":
        docs = [KB.get(i) for i in c["reference"]]
        r = GRD.check(inp["answer"], inp["sources"], docs)
        return r.grounded == exp["grounded"], not exp["grounded"], not r.grounded, {"grounded": r.grounded, "score": r.score, "reason": r.reason}

    if g == "output_sensitive":
        r = SEN.scan(inp)
        return r.action == exp["action"], exp["action"] != "PASS", r.action != "PASS", {"action": r.action, "findings": [f["type"] for f in r.findings]}

    if g == "e2e":
        llm = ScriptedLLM(c["llm_script"]) if c.get("llm_script") else MockLLM()
        r = GuardrailPipeline(llm, KB).handle(inp)
        ok = r.final_action == exp["action"]
        ok = ok and all(s in r.response_text for s in exp["contains"])
        ok = ok and all(s not in r.response_text for s in exp["not_contains"])
        return ok, None, None, {"action": r.final_action, "response": r.response_text[:120]}

    raise ValueError(g)


def short(v, n=90):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def prf(tp, fp, fn, tn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return p, r, f1


def fmt(x):
    return "n/a" if x is None else f"{x:.2f}"


def main():
    rows, counts = [], defaultdict(lambda: dict(tp=0, fp=0, fn=0, tn=0, n=0, passed=0))
    for c in CASES:
        passed, exp_flag, act_flag, actual = run_case(c)
        outcome = "-"
        if exp_flag is not None:
            outcome = {(True, True): "TP", (False, True): "FP", (True, False): "FN", (False, False): "TN"}[(exp_flag, act_flag)]
            counts[c["guardrail"]][outcome.lower()] += 1
        counts[c["guardrail"]]["n"] += 1
        counts[c["guardrail"]]["passed"] += int(passed)
        ref = ""
        if c["reference"] is not None:
            ref = " | ".join(f"[{i}] {KB.get(i)['text']}" for i in c["reference"]) or "(no reference docs)"
        rows.append(dict(id=c["id"], guardrail=c["guardrail"], description=c["description"], test_input=short(c["input"], 400),
                         reference=ref, expected=json.dumps(c["expected"], ensure_ascii=False),
                         actual=json.dumps(actual, ensure_ascii=False), status="PASS" if passed else "FAIL",
                         outcome=outcome, known_limitation=c["known_limitation"], note=c["note"]))

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "test_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with open(RESULTS / "test_results.md", "w", encoding="utf-8") as f:
        f.write("| ID | Guardrail | Test input (truncated) | Reference | Expected | Actual | Status |\n|---|---|---|---|---|---|---|\n")
        for r in rows:
            ref = r["reference"][:60] + "..." if len(r["reference"]) > 60 else r["reference"]
            f.write(f"| {r['id']} | {r['guardrail']} | {short(r['test_input'], 70).replace('|', '/')} | {ref.replace('|', '/')} | "
                    f"{short(r['expected'], 50)} | {short(r['actual'], 70).replace('|', '/')} | {r['status']}{' (known)' if r['status']=='FAIL' and r['known_limitation'] else ''} |\n")

    metrics, tot = {}, dict(tp=0, fp=0, fn=0, tn=0)
    for g, label in GUARDRAIL_LABELS.items():
        m = counts[g]
        p, r, f1 = prf(m["tp"], m["fp"], m["fn"], m["tn"])
        metrics[g] = dict(label=label, cases=m["n"], passed=m["passed"], tp=m["tp"], fp=m["fp"], fn=m["fn"], tn=m["tn"],
                          precision=p, recall=r, f1=f1)
        for k in tot:
            tot[k] += m[k]
    p, r, f1 = prf(**tot)
    metrics["overall_guardrails"] = dict(label="All 6 guardrails (unit level)", **tot, precision=p, recall=r, f1=f1)
    e = counts["e2e"]
    metrics["e2e"] = dict(label="End-to-end pipeline", cases=e["n"], passed=e["passed"])
    metrics["summary"] = dict(total_cases=len(CASES), passed=sum(r["status"] == "PASS" for r in rows),
                              failed=sum(r["status"] == "FAIL" for r in rows),
                              failed_known=sum(r["status"] == "FAIL" and r["known_limitation"] for r in rows),
                              failed_unexpected=sum(r["status"] == "FAIL" and not r["known_limitation"] for r in rows),
                              known_but_passed=sum(r["status"] == "PASS" and r["known_limitation"] for r in rows))
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    lines = ["| Guardrail | Cases | Pass | TP | FP | FN | TN | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g in list(GUARDRAIL_LABELS) + ["overall_guardrails"]:
        m = metrics[g]
        lines.append(f"| {m['label']} | {m.get('cases', '')} | {m.get('passed', '')} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
                     f"{fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['f1'])} |")
    lines.append(f"| End-to-end pipeline | {e['n']} | {e['passed']} | - | - | - | - | - | - | - |")
    (RESULTS / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    s = metrics["summary"]
    print(f"\nTOTAL {s['total_cases']} cases | PASS {s['passed']} | FAIL {s['failed']} "
          f"(known limitations: {s['failed_known']}, UNEXPECTED: {s['failed_unexpected']})")
    for r in rows:
        if r["status"] == "FAIL":
            print(f"  FAIL {r['id']:7} {'(known)' if r['known_limitation'] else '(UNEXPECTED)'} expected={r['expected']} actual={short(r['actual'], 110)}")
    for r in rows:
        if r["status"] == "PASS" and r["known_limitation"]:
            print(f"  NOTE {r['id']} was marked known_limitation but PASSED")


if __name__ == "__main__":
    main()
