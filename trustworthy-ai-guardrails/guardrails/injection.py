"""
injection.py  (INPUT guardrail #2)
----------------------------------
Approach : Rule-based weighted detector. Har rule ko weight (0-1) hunchha; matched rules ko
           score "noisy-OR" le combine hunchha:  score = 1 - prod(1 - w).
           -> ek strong rule (0.7) matra pani block garna pugchha, ra duita kamjor signal (0.3 + 0.3)
              ek ladi bhayo bhane pani block hunchha.
Action   : score >= 0.5 -> BLOCK (canned refusal, LLM call hudaina)
           0.3 <= score < 0.5 -> SUSPICIOUS (allow, tara warn flag set)
Extras   : Unicode NFKC normalize, zero-width char hataune, base64 decode garera feri scan garne.
Limitation:
  - Obfuscation (leetspeak "1gn0re"), paraphrase, aru bhasha (Roman Nepali ko limited coverage matra).
  - Legit sentence ma "ignore the previous instructions" aayo bhane false positive.
  - Indirect injection (retrieved document ma lukaieko instruction) yo le scan gardaina.
  - Regex arms-race: attacker le naya wording banayo bhane rule update garnu parcha. ML classifier
    (jastai Llama Guard / Prompt-Guard) sanga combine garnu better.
"""
import base64
import re
import unicodedata
from . import config
from .models import InjectionResult

_QUAL = r"(?:all|any|every|the|your|my|these|those|previous|prior|above|earlier|preceding|system|safety|original)"
_NOUN = r"(?:instructions?|rules?|prompts?|guidelines?|directives?|restrictions?|policies|programming)"

# (rule_name, weight, [regex patterns])  - pattern haru lowercase text ma match garchhan
_RULES = [
    ("instruction_override", 0.7, [
        rf"\b(?:ignore|disregard|forget|override|overrule)\W+(?:{_QUAL}\W+){{1,3}}{_NOUN}\b",
        r"\b(?:forget|ignore|disregard)\s+(?:everything|anything)\s+(?:you|i|we)\s+(?:were\s+told|said|know|learned)",
    ]),
    ("prompt_extraction", 0.7, [
        r"\b(?:reveal|show|print|display|repeat|tell|give|leak|output|share|dump|recite)\W+(?:\w+\W+){0,3}?"
        r"(?:system\s+prompt|initial\s+prompt|hidden\s+(?:prompt|instructions?)|"
        r"your\s+(?:instructions|rules|guidelines|prompt|configuration|programming)|"
        r"developer\s+(?:message|prompt|instructions?))",
        r"\bwhat\s+(?:is|are|were)\s+your\s+(?:system\s+prompt|(?:initial\s+|original\s+|hidden\s+)?instructions|rules)",
        r"\brepeat\s+(?:the\s+)?(?:text|words|everything|message)\s+above\b",
    ]),
    ("role_hijack", 0.6, [
        r"\byou\s+are\s+(?:now\s+)?(?:dan\b|an?\s+(?:unrestricted|unfiltered|jailbroken|evil)\b)",
        r"\b(?:act|behave|respond|answer)\s+as\s+(?:if\s+you\s+(?:were|are)\s+)?(?:an?\s+)?(?:unrestricted|unfiltered|jailbroken|evil|dan\b|root|admin)",
        r"\bpretend\s+(?:to\s+be|you\s+are|that\s+you\s+are)\s+(?:an?\s+)?(?:\w+\s+){0,3}?"
        r"(?:unrestricted|unfiltered|jailbroken|dan\b|without\s+(?:any\s+)?(?:rules|restrictions|limits))",
        r"\bfrom\s+now\s+on,?\s+you\s+(?:are|will|must|shall)\b",
    ]),
    ("you_are_now", 0.4, [r"\byou\s+are\s+now\b"]),
    ("restriction_bypass", 0.6, [
        r"\b(?:jailbreak|jailbroken|developer\s+mode|god\s+mode|dan\s+mode|do\s+anything\s+now)\b",
        r"\b(?:without|disable|turn\s+off|bypass|circumvent)\s+(?:any\s+|all\s+|your\s+|the\s+)?"
        r"(?:safety|guardrails?|filters?|censorship|content\s+polic(?:y|ies))\b",
    ]),
    # kamjor signal: legit user le pani "remove restrictions on my account" bhanna sakchha
    ("mentions_restrictions", 0.3, [
        r"\b(?:without|no|remove|disable|lift|turn\s+off)\s+(?:any\s+|all\s+|your\s+|the\s+)?(?:restrictions?|limitations?|limits|rules)\b",
    ]),
    ("delimiter_injection", 0.6, [
        r"</?\s*(?:system|assistant|instructions?)\s*>",
        r"\[/?\s*(?:inst|system)\s*\]",
        r"<\|(?:im_start|im_end|system|endoftext)\|>",
        r"(?:^|\s)#{2,}\s*(?:system|instructions?)\b",
        r"\bsystem\s*:\s*you\s+are\b",
    ]),
    ("new_instructions", 0.4, [r"\bnew\s+instructions?\s*:", r"\bupdated\s+instructions?\s*:"]),
    ("authority_claim", 0.4, [r"\bi\s+am\s+(?:your|the)\s+(?:developer|creator|administrator|admin|owner|engineer)\b"]),
    ("mentions_system_prompt", 0.3, [r"\bsystem\s+prompt\b", r"\bhidden\s+(?:instructions?|rules?|prompt)\b"]),
    # Roman Nepali + Devanagari
    ("nepali_override", 0.7, [
        r"\bsystem\s*prompt\s+(?:dekhau|dekhaunu|bhana|bhanera|pathau|dinus|deu)\b",
        r"\b(?:instructions?|niyam|nirdesh\w*|rules?)\s*(?:haru)?\s+(?:sabai\s+)?(?:ignore|bhula\w*|nabhan\w*|hatau\w*)\b",
        r"(?:निर्देशन|निर्देश|नियम)\S*\s*(?:हरू|हरु)?\s*(?:सबै\s*)?(?:बेवास्ता|बिर्स|इग्नोर)",
    ]),
]

_COMPILED = [(n, w, [re.compile(p, re.I) for p in pats]) for n, w, pats in _RULES]
_B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)     # fullwidth/compat characters lai normal banaucha
    text = _ZERO_WIDTH.sub("", text)               # lukeko zero-width chars hataucha
    return re.sub(r"\s+", " ", text).lower()


class InjectionDetector:
    def _match_rules(self, norm_text: str) -> list:
        hits = []
        for name, weight, patterns in _COMPILED:
            if any(p.search(norm_text) for p in patterns):
                hits.append((name, weight))
        return hits

    def _decoded_payloads(self, text: str) -> list:
        """Long base64-jasto token haru decode garera text return garcha (attacker le encode garera pathauna sakchha)."""
        out = []
        for tok in _B64_TOKEN.findall(text):
            try:
                raw = base64.b64decode(tok + "=" * (-len(tok) % 4), validate=True)
                decoded = raw.decode("utf-8")
            except Exception:
                continue
            printable = sum(c.isprintable() or c.isspace() for c in decoded)
            if decoded and printable / len(decoded) > 0.9:
                out.append(decoded)
        return out

    def analyze(self, text: str) -> InjectionResult:
        norm = _normalize(text)
        hits = self._match_rules(norm)
        for decoded in self._decoded_payloads(text):         # depth=1 matra (nested encoding scan gardaina)
            hits += [(f"encoded:{n}", w) for n, w in self._match_rules(_normalize(decoded))]

        # noisy-OR: score = 1 - (1-w1)(1-w2)...
        remaining = 1.0
        for _, w in hits:
            remaining *= (1.0 - w)
        score = round(1.0 - remaining, 3)

        if score >= config.INJECTION_BLOCK_THRESHOLD:
            label = "INJECTION"
        elif score >= config.INJECTION_WARN_THRESHOLD:
            label = "SUSPICIOUS"
        else:
            label = "SAFE"
        return InjectionResult(score=score, label=label, rules=[n for n, _ in hits])
