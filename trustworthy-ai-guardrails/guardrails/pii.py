"""
pii.py  (INPUT guardrail #1 + OUTPUT guardrail ma pani reuse hunchha)
------------------------------------------------------------------
Approach : Regex + validator (Luhn checksum, keyword context).
Action   : Input ma -> REDACT (e.g. [EMAIL]) ani request aghi badhcha. Output ma -> REDACT.
Limitation:
  - Spelled-out PII ("ram dot sharma at gmail dot com") pakdaindaina.
  - 98xxxxxxxx jasto 10-digit reference/transaction ID pani phone number ठहरिन्छ (false positive).
  - Naam, thegana (name/address) jasta free-text PII ko lagi NER model chaincha - yaha chhaina.
"""
import re
from . import config
from .models import PIIMatch


def luhn_valid(number: str) -> bool:
    """Credit/debit card number valid chha ki chhaina (Luhn checksum) - random 16 digit lai card nabhanna."""
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# (type, regex, group_index, validator)
# ORDER MATTERS: specific pattern pahila, general pachi. Overlap bhayo bhane pahilo le jitchha.
_PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), 0, None),
    ("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"), 0, luhn_valid),
    # Nepali citizenship format: 27-01-71-12345
    ("CITIZENSHIP_NO", re.compile(r"(?<!\d)\d{2}-\d{2}-\d{2}-\d{5}(?!\d)"), 0, None),
    # PAN: "PAN 123456789" - keyword chha bhane matra (9 digit random number ma false positive huncha)
    ("PAN_NO", re.compile(r"\bPAN(?:\s*(?:no\.?|number|#))?(?:\s+is)?\s*[:\-]?\s*(\d{9})(?!\d)", re.I), 1, None),
    # Account number: "account number 0012345678901" - keyword context chahincha
    ("ACCOUNT_NO", re.compile(r"\b(?:account|a/c|acc)(?:\s*(?:no\.?|number|#))?(?:\s+is)?\s*[:\-]?\s*(\d{10,20})(?!\d)", re.I), 1, None),
    # Nepali mobile (97/98...) with optional +977, ani Kathmandu landline (01-xxxxxxx)
    ("PHONE", re.compile(r"(?<!\d)(?:\+?977[-\s]?)?(?:9[78]\d[-\s]?\d{3}[-\s]?\d{4}|01[-\s]?\d{7})(?!\d)"), 0, None),
]


class PIIDetector:
    def detect(self, text: str, use_allowlist: bool = False) -> list:
        """text bhitra ka sabai PII matches (non-overlapping) return garcha."""
        matches, taken = [], []
        for name, rx, grp, validator in _PATTERNS:
            for m in rx.finditer(text):
                s, e = m.span(grp)
                if any(s < te and ts < e for ts, te in taken):
                    continue  # pahila nai aarko pattern le liyeko span
                value = text[s:e]
                if validator and not validator(value):
                    continue
                match = PIIMatch(name, value, s, e)
                if use_allowlist and self.is_public(match):
                    continue  # bank ko public contact ho -> PII hoina
                matches.append(match)
                taken.append((s, e))
        return sorted(matches, key=lambda x: x.start)

    @staticmethod
    def is_public(match: PIIMatch) -> bool:
        if match.type == "EMAIL":
            return match.text.lower() in config.PUBLIC_EMAILS
        if match.type == "PHONE":
            digits = re.sub(r"\D", "", match.text)
            return digits in config.PUBLIC_PHONES
        return False

    def redact(self, text: str, matches: list = None) -> str:
        """Har PII lai [TYPE] le replace garcha. Pachhadi bata replace garne ki index nabigros."""
        if matches is None:
            matches = self.detect(text)
        for m in sorted(matches, key=lambda x: x.start, reverse=True):
            text = text[: m.start] + f"[{m.type}]" + text[m.end:]
        return text
