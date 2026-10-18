"""
output_guard.py
---------------
LLM ko raw output lai teen stage ma check garcha. Order jaan-bujhera yesto chha:

  1. Schema       (sasto, structure nai galat bhaye aru check ko artha chhaina)
  2. Sensitive    (security-critical: leak/PII; groundedness bhanda aghi, taki PII/secret kahile aghi naa jaos)
  3. Groundedness (sabai bhanda mahango, redacted text ma chalaucha)

Result: PASS | REDACTED (PII hataera pass) | REJECTED (pipeline le regenerate/fallback garcha)
"""
from .groundedness import GroundednessValidator
from .models import OutputDecision
from .output_sensitive import SensitiveOutputDetector
from .schema import SchemaValidator


class OutputGuard:
    def __init__(self):
        self.schema = SchemaValidator()
        self.sensitive = SensitiveOutputDetector()
        self.grounded = GroundednessValidator()

    def check(self, raw_output, docs: list) -> OutputDecision:
        schema = self.schema.validate(raw_output)
        if not schema.valid:
            return OutputDecision("REJECTED", [f"schema: {e}" for e in schema.errors], None, schema=schema)

        answer = dict(schema.parsed)
        sens = self.sensitive.scan(answer["answer"])
        if sens.action == "BLOCK":
            types = sorted({f["type"] for f in sens.findings if f["severity"] == "BLOCK"})
            return OutputDecision("REJECTED", [f"sensitive: {types}"], None, schema=schema, sensitive=sens)

        status = "PASS"
        if sens.action == "REDACT":
            answer["answer"] = sens.redacted_text
            status = "REDACTED"

        ground = self.grounded.check(answer["answer"], answer["sources"], docs)
        if not ground.grounded:
            return OutputDecision("REJECTED", [f"groundedness: {ground.reason}"], None,
                                  schema=schema, sensitive=sens, groundedness=ground)

        reasons = ["PII redacted from output"] if status == "REDACTED" else []
        return OutputDecision(status, reasons, answer, schema=schema, sensitive=sens, groundedness=ground)
