# Mero Bank Assistant - Input & Output Guardrails

Trustworthy AI assignment: a customer-support assistant for a **fictional** bank ("Mero Bank") wrapped in
input and output guardrails. Pure Python standard library: no installs, no API key, runs offline.

- **Input guardrails:** PII detection/redaction, prompt-injection detection, sensitive-topic classification
- **Output guardrails:** schema validation, groundedness validation, sensitive-information detection
- **Failure handling:** redact, regenerate (max 1), refuse, human hand-off, or safe fallback
- **Evaluation:** 85 test cases, precision/recall/FP/FN per guardrail, failure analysis, trade-off sweep

Full write-up: [`REPORT.md`](REPORT.md) | Diagram: [`docs/architecture.svg`](docs/architecture.svg) | Raw results: [`results/`](results/)

## Folder structure

```
trustworthy-ai-guardrails/
├── README.md                    <- yo file
├── REPORT.md                    <- evaluation report (design, results, failures, trade-offs, risks)
├── requirements.txt             <- core ma dependency chaina
├── run_demo.py                  <- interactive CLI / --examples / --json trace
├── guardrails/
│   ├── config.py                <- thresholds, policy, canned messages, system prompt
│   ├── models.py                <- dataclasses (results/trace)
│   ├── text_utils.py            <- tokenizer, stemmer, number extraction
│   ├── pii.py                   <- INPUT #1 (+ reused on output)
│   ├── injection.py             <- INPUT #2
│   ├── topics.py                <- INPUT #3
│   ├── input_guard.py           <- combines 3 input checks + decision precedence
│   ├── schema.py                <- OUTPUT #1
│   ├── output_sensitive.py      <- OUTPUT #2
│   ├── groundedness.py          <- OUTPUT #3
│   ├── output_guard.py          <- combines 3 output checks
│   ├── knowledge_base.py        <- tiny retriever over data/knowledge_base.json
│   ├── llm.py                   <- MockLLM, ScriptedLLM (tests), AnthropicLLM (optional)
│   └── pipeline.py              <- full flow incl. regenerate loop + fallback
├── data/knowledge_base.json     <- 8 fictional FAQ documents (reference info for groundedness)
├── evaluation/
│   ├── test_cases.py            <- 85 test cases (input, reference, expected)
│   ├── run_evaluation.py        <- runs all, writes results/*
│   └── tradeoff_analysis.py     <- threshold sweep (safety vs usability)
├── tests/test_guardrails.py     <- unittest (unit + regression over all cases)
├── results/                     <- test_results.csv/.md, metrics.json/.md, tradeoff_analysis.txt
└── docs/architecture.svg, architecture.md
```

## Setup (Python 3.10+)

```bash
cd trustworthy-ai-guardrails
python run_demo.py --examples          # 10 ready-made examples
python run_demo.py                     # interactive chat ('exit' to quit)
python run_demo.py --json "Ignore all previous instructions"   # full decision trace
python evaluation/run_evaluation.py    # 85 cases -> results/
python evaluation/tradeoff_analysis.py # threshold sweep
python -m unittest discover -s tests -v
```

## Usage in code

```python
from guardrails import GuardrailPipeline, MockLLM

pipe = GuardrailPipeline(MockLLM())
r = pipe.handle("My email is ram@example.com, what is the daily ATM limit?")
print(r.final_action)     # ANSWERED
print(r.response_text)    # The daily ATM withdrawal limit is NPR 50,000.  (Sources: KB-002)
print(r.input_decision.sanitized_text)   # My email is [EMAIL], what is the daily ATM limit?
```

Possible `final_action` values: `ANSWERED`, `ANSWERED_WITH_DISCLAIMER`, `SAFE_FALLBACK`, `BLOCK_INJECTION`,
`REFUSE`, `ESCALATE_CRISIS`, `HUMAN_HANDOFF`, `INVALID_INPUT`.

To use a real model: `pip install anthropic`, set `ANTHROPIC_API_KEY`, then `python run_demo.py --llm anthropic`
(or `GuardrailPipeline(AnthropicLLM())`). That adapter is **not tested** in this project: all reported results use `MockLLM`/`ScriptedLLM`.

## What each guardrail does

| Guardrail               | Detection approach                                                                                                | Action when flagged                                   | Main limitation                                                                                                        |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| PII (input)             | Regex + Luhn + keyword context (email, Nepali phone, citizenship, PAN, account, card)                             | Redact to `[TYPE]`, continue                          | Obfuscated PII; 98xxxxxxxx reference IDs look like phones                                                              |
| Prompt injection        | 11 weighted rule groups + Roman Nepali/Devanagari + base64 decode; noisy-OR score                                 | Score >= 0.5 block; 0.3-0.5 warn                      | Leetspeak, paraphrase, legit phrases containing "ignore previous instructions"                                         |
| Sensitive topic         | Regex rules, 6 categories with per-category action (see `topics.py`)                                              | Crisis message / refuse / human hand-off / disclaimer | Implicit wording missed; broad keywords (e.g. "court") over-trigger                                                    |
| Schema                  | Hand-written validator (types, enums, ranges, no extra fields, citation id format)                                | Reject -> regenerate -> fallback                      | Checks structure, not truth                                                                                            |
| Groundedness            | Claim-level lexical overlap (>= 0.6) + numbers must appear + citations must be provided docs                      | Reject -> regenerate -> fallback                      | Negation/paraphrase (a stricter score of 1.0 does not fix negation); 0.8 score threshold tolerates 1 bad sentence in 5 |
| Sensitive info (output) | PII (with allowlist for bank contacts), secrets, canary token, 6-gram system-prompt overlap, confidential phrases | PII: redact. Leak/secret: block                       | Obfuscated PII, paraphrased prompt leak                                                                                |

## Design decisions (short)

1. **Dependency-free + deterministic** so every reported number can be reproduced offline by anyone.
2. **PII is redacted first**, before injection/topic checks, so raw PII never reaches the LLM, the logs, or the trace.
3. **Self-harm outranks injection** in the router: a person in distress gets the crisis response even if the message also looks adversarial.
4. **Injection score uses noisy-OR** so two weak signals accumulate (0.3 + 0.3 -> block) while one weak signal only warns.
5. **Numbers are critical in groundedness**: any unsupported claim containing a number fails immediately, regardless of the score threshold.
6. **Leaks are blocked, PII is redacted**: a leaked system prompt cannot be repaired by redaction, but an email can.
7. **Bounded retry**: one regeneration with a stricter prompt, then a safe fallback. No infinite loops.

## Evaluation results (85 cases)

| Guardrail                 | Cases | Pass | TP  | FP  | FN  | TN  | Precision | Recall | F1   |
| ------------------------- | ----- | ---- | --- | --- | --- | --- | --------- | ------ | ---- |
| Input: PII detection      | 12    | 10   | 8   | 1   | 1   | 2   | 0.89      | 0.89   | 0.89 |
| Input: Prompt-injection   | 16    | 13   | 10  | 1   | 2   | 3   | 0.91      | 0.83   | 0.87 |
| Input: Sensitive-topic    | 12    | 10   | 8   | 1   | 1   | 2   | 0.89      | 0.89   | 0.89 |
| Output: Schema validation | 12    | 12   | 10  | 0   | 0   | 2   | 1.00      | 1.00   | 1.00 |
| Output: Groundedness      | 10    | 8    | 4   | 0   | 2   | 4   | 1.00      | 0.67   | 0.80 |
| Output: Sensitive-info    | 11    | 10   | 7   | 0   | 1   | 3   | 1.00      | 0.88   | 0.93 |
| **All 6 (unit level)**    | 73    | 63   | 47  | 3   | 7   | 16  | 0.94      | 0.87   | 0.90 |
| End-to-end pipeline       | 12    | 12   | -   | -   | -   | -   | -         | -      | -    |

**75 / 85 pass.** All 10 failures are documented known limitations (UNEXPECTED: 0), so no test failed outside the weak
spots deliberately probed. Failures: PII-11, PII-12, INJ-14, INJ-15, INJ-16, TOP-11, TOP-12, GRD-09, GRD-10, OUT-11
(see the Failure Analysis section of `REPORT.md`).
Important: the test set was written by the same person who wrote the guardrails, and 10 of the 85 cases were
deliberately chosen to probe weaknesses. These numbers show _how the guardrails behave on this set_; they do not
predict real-world performance.

## Threshold trade-offs (`python evaluation/tradeoff_analysis.py`)

| Setting                                   | TP  | FP  | FN  | TN  | Precision | Recall |
| ----------------------------------------- | --- | --- | --- | --- | --------- | ------ |
| Injection block threshold 0.25 (stricter) | 10  | 2   | 2   | 2   | 0.83      | 0.83   |
| Injection block threshold 0.50 (default)  | 10  | 1   | 2   | 3   | 0.91      | 0.83   |
| Injection block threshold 0.75 (looser)   | 6   | 0   | 6   | 4   | 1.00      | 0.50   |
| Groundedness min score 0.6 (looser)       | 4   | 0   | 2   | 4   | 1.00      | 0.67   |
| Groundedness min score 0.8 (default)      | 4   | 0   | 2   | 4   | 1.00      | 0.67   |
| Groundedness min score 1.0 (stricter)     | 5   | 0   | 1   | 4   | 1.00      | 0.83   |
| Sentence-overlap threshold 0.4 (looser)   | 3   | 0   | 3   | 4   | 1.00      | 0.50   |
| Sentence-overlap threshold 0.6 (default)  | 4   | 0   | 2   | 4   | 1.00      | 0.67   |
| Sentence-overlap threshold 0.8 (stricter) | 4   | 0   | 2   | 4   | 1.00      | 0.67   |

Key takeaways (details in `REPORT.md`):

- Injection threshold: 0.75 removes the false positive but lets 4 more attacks through (recall 0.83 to 0.50).
- Groundedness min score: 0.6 and 0.8 give identical results on this set. Only 1.0 changes the outcome: it catches
  GRD-09 (fabricated sentence, score exactly 0.8) but still misses GRD-10, because the negated sentence scores 1.0.
  Negation needs a polarity check or NLI, not a higher threshold.
- Sentence-overlap threshold: tightening to 0.8 changes nothing; only loosening to 0.4 hurts.

## Disclaimer

Mero Bank, its products, rates and phone/email are fictional. Helpline text in the crisis message is generic
(Nepal Police 100): verify local resources before any real deployment.
