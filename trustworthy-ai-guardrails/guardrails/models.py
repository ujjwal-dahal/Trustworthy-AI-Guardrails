"""
models.py
---------
Guardrail haru ko result haru ko dataclass definition.
NOTE: Raw PII (jastai email, phone) kahile pani trace/log ma store gardaina - sirf type matra.
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class PIIMatch:
    type: str      # EMAIL, PHONE, CREDIT_CARD ...
    text: str      # asli value (sirf redaction ko lagi, log ma jaadaina)
    start: int
    end: int


@dataclass
class InjectionResult:
    score: float                       # 0.0 - 1.0 (noisy-OR le combine gareko)
    label: str                         # SAFE | SUSPICIOUS | INJECTION
    rules: list = field(default_factory=list)


@dataclass
class TopicResult:
    category: Optional[str]            # SELF_HARM, ILLEGAL_ACTIVITY ... ya None
    action: str                        # ALLOW | ESCALATE_CRISIS | REFUSE | HUMAN_HANDOFF | ANSWER_WITH_DISCLAIMER
    matched_categories: list = field(default_factory=list)


@dataclass
class InputDecision:
    action: str                        # ALLOW | ALLOW_WITH_DISCLAIMER | BLOCK_INJECTION | REFUSE | ESCALATE_CRISIS | HUMAN_HANDOFF | INVALID_INPUT
    sanitized_text: str                # PII redact gareko text (yehi LLM lai jaanchha)
    pii_types: list
    injection: InjectionResult
    topic: TopicResult
    reasons: list
    warn: bool = False


@dataclass
class SchemaResult:
    valid: bool
    errors: list
    parsed: Optional[dict]
    repaired: bool = False


@dataclass
class GroundednessResult:
    grounded: bool
    score: float
    claims: list
    unsupported: list
    invalid_citations: list
    reason: str


@dataclass
class SensitiveResult:
    action: str                        # PASS | REDACT | BLOCK
    findings: list
    redacted_text: str


@dataclass
class OutputDecision:
    status: str                        # PASS | REDACTED | REJECTED
    reasons: list
    answer: Optional[dict]
    schema: Optional[SchemaResult] = None
    sensitive: Optional[SensitiveResult] = None
    groundedness: Optional[GroundednessResult] = None


@dataclass
class PipelineResult:
    sanitized_message: str
    final_action: str                  # ANSWERED | ANSWERED_WITH_DISCLAIMER | SAFE_FALLBACK | BLOCK_INJECTION | REFUSE | ...
    response_text: str
    input_decision: InputDecision
    retrieved_ids: list = field(default_factory=list)
    attempts: list = field(default_factory=list)
    output_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
