"""
output_sensitive.py  (OUTPUT guardrail #3)
------------------------------------------
Approach : (a) PII detector reuse (bank ko public contact allowlist sahit),
           (b) secret/credential regex (API key, "password is X1234"),
           (c) canary token, (d) system-prompt verbatim leak (6-word shingle overlap),
           (e) confidential phrase list.
Action   : PII           -> REDACT ([EMAIL] le replace, answer aghi badhcha)
           Secret/leak   -> BLOCK (redact garera hudaina; regenerate -> fallback)
Limitation:
  - Spelled-out/obfuscated PII, paraphrased system prompt, ya naya confidential phrase miss hunchha.
  - Phrase list manually maintain garnu parcha.
  - Allowlist le attacker-controlled "public" email ko risk lai ghataucha tara exact match matra.
"""
import re
from . import config
from .models import SensitiveResult
from .pii import PIIDetector

_SECRET_PATTERNS = [
    ("API_KEY", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # "password is Ram@12345": value ma digit hunai parcha -> "OTP is never shared" jasto safe sentence ma false positive nahos
    ("CREDENTIAL", re.compile(r"\b(?:password|passwd|pwd|pin|otp)\b\s*(?:is|=|:)\s*['\"]?(?=\S*\d)\S{4,}", re.I)),
]


def _shingles(text: str, n: int = 6) -> set:
    words = re.findall(r"[a-z0-9\-]+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


_PROMPT_SHINGLES = _shingles(config.SYSTEM_PROMPT)


class SensitiveOutputDetector:
    def __init__(self):
        self.pii = PIIDetector()

    def scan(self, text: str) -> SensitiveResult:
        findings = []

        for name, rx in _SECRET_PATTERNS:
            if rx.search(text):
                findings.append({"type": name, "severity": "BLOCK"})
        if config.CANARY_TOKEN.lower() in text.lower():
            findings.append({"type": "CANARY_TOKEN", "severity": "BLOCK"})
        if _shingles(text) & _PROMPT_SHINGLES:
            findings.append({"type": "SYSTEM_PROMPT_LEAK", "severity": "BLOCK"})
        low = text.lower()
        for phrase in config.CONFIDENTIAL_PHRASES:
            if phrase in low:
                findings.append({"type": "CONFIDENTIAL_INFO", "severity": "BLOCK"})
                break

        pii_matches = self.pii.detect(text, use_allowlist=True)
        for m in pii_matches:
            findings.append({"type": m.type, "severity": "REDACT"})   # raw value store gardaina

        if any(f["severity"] == "BLOCK" for f in findings):
            action = "BLOCK"
        elif pii_matches:
            action = "REDACT"
        else:
            action = "PASS"
        return SensitiveResult(action=action, findings=findings, redacted_text=self.pii.redact(text, pii_matches))
