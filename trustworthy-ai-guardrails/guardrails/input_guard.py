"""
input_guard.py
--------------
Teen ota INPUT guardrail (PII, injection, topic) lai ek thau ma jodera final decision dincha.

Decision precedence (maathi bata talla):
  1. INVALID_INPUT       - khali ya MAX_INPUT_CHARS bhanda lamo
  2. ESCALATE_CRISIS     - SELF_HARM (safety sabai bhanda mathi, injection bhaye pani)
  3. BLOCK_INJECTION     - injection score >= threshold
  4. REFUSE / HUMAN_HANDOFF / ALLOW_WITH_DISCLAIMER - sensitive topic ko action
  5. ALLOW               - baaki sabai
PII chai decision haina, SANITIZATION ho: hamesha redact garera matra aghi pathaune (LLM/log ma raw PII jaadaina).
"""
from . import config
from .injection import InjectionDetector
from .models import InputDecision, InjectionResult, TopicResult
from .pii import PIIDetector
from .topics import TopicClassifier

_TOPIC_TO_ACTION = {
    "ESCALATE_CRISIS": "ESCALATE_CRISIS",
    "REFUSE": "REFUSE",
    "HUMAN_HANDOFF": "HUMAN_HANDOFF",
    "ANSWER_WITH_DISCLAIMER": "ALLOW_WITH_DISCLAIMER",
}


class InputGuard:
    def __init__(self):
        self.pii = PIIDetector()
        self.injection = InjectionDetector()
        self.topics = TopicClassifier()

    def check(self, text) -> InputDecision:
        empty_inj, empty_topic = InjectionResult(0.0, "SAFE"), TopicResult(None, "ALLOW")
        if not isinstance(text, str) or not text.strip():
            return InputDecision("INVALID_INPUT", "", [], empty_inj, empty_topic, ["empty input"])
        if len(text) > config.MAX_INPUT_CHARS:
            return InputDecision("INVALID_INPUT", "", [], empty_inj, empty_topic, ["input too long"])

        # Step 1: PII redact (pahila nai, taki aaru detectors/logs ma raw PII nagaos)
        matches = self.pii.detect(text)
        sanitized = self.pii.redact(text, matches)
        pii_types = sorted({m.type for m in matches})
        reasons = [f"PII redacted: {pii_types}"] if pii_types else []

        # Step 2 & 3: injection + topic
        inj = self.injection.analyze(sanitized)
        topic = self.topics.classify(sanitized)
        warn = inj.label == "SUSPICIOUS"

        # Step 4: precedence anusar action chhanne
        if topic.category == "SELF_HARM":
            action = "ESCALATE_CRISIS"
            reasons.append("topic: SELF_HARM")
        elif inj.label == "INJECTION":
            action = "BLOCK_INJECTION"
            reasons.append(f"injection score {inj.score} rules {inj.rules}")
        elif topic.category:
            action = _TOPIC_TO_ACTION[topic.action]
            reasons.append(f"topic: {topic.category}")
        else:
            action = "ALLOW"
        if warn:
            reasons.append(f"suspicious (score {inj.score}) - allowed with warning")
        return InputDecision(action, sanitized, pii_types, inj, topic, reasons, warn)
