| Guardrail | Cases | Pass | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|---|
| Input: PII detection | 12 | 10 | 8 | 1 | 1 | 2 | 0.89 | 0.89 | 0.89 |
| Input: Prompt-injection | 16 | 13 | 10 | 1 | 2 | 3 | 0.91 | 0.83 | 0.87 |
| Input: Sensitive-topic | 12 | 10 | 8 | 1 | 1 | 2 | 0.89 | 0.89 | 0.89 |
| Output: Schema validation | 12 | 12 | 10 | 0 | 0 | 2 | 1.00 | 1.00 | 1.00 |
| Output: Groundedness | 10 | 8 | 4 | 0 | 2 | 4 | 1.00 | 0.67 | 0.80 |
| Output: Sensitive-info | 11 | 10 | 7 | 0 | 1 | 3 | 1.00 | 0.88 | 0.93 |
| All 6 guardrails (unit level) |  |  | 47 | 3 | 7 | 16 | 0.94 | 0.87 | 0.90 |
| End-to-end pipeline | 12 | 12 | - | - | - | - | - | - | - |
