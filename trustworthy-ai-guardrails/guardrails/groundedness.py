"""
groundedness.py  (OUTPUT guardrail #2)
--------------------------------------
Approach : Claim-level lexical support check (LLM-as-judge chaina -> deterministic, offline, testable).
  1. Answer lai sentence (claim) ma tod.
  2. Public contact (bank ko email/phone) hataune; greeting/deflection jasta non-claim skip garne.
  3. Har claim lai reference doc ko 1-2 sentence window sanga compare:
       - content-word overlap >= SENTENCE_SUPPORT_THRESHOLD (0.6)
       - claim ma bhako SABAI numbers (50,000 / 9.5%) tyo window ma hunu parcha
  4. Cited sources sabai provided reference docs ma hunu parcha (hallucinated citation block).
  5. score = supported / total. Pass: score >= GROUNDEDNESS_MIN_SCORE ra koi numeric claim unsupported chhaina.
Action   : Fail bhayo bhane REJECT -> regenerate -> safe fallback.
Limitation:
  - Lexical ho, semantic hoina: NEGATION ("is NOT credited") ra paraphrase/synonym le fail garna sakchha.
  - Threshold 0.8 le 5 sentence ma 1 unsupported claim lai pass garna sakchha (trade-off).
  - Non-claim pattern ("Please ...") bata number-nabhako unsupported claim lukaera pass garna sakine possibility.
  - NLI model (entailment) use garyo bhane aaru accurate hunchha.
"""
import re
from . import config
from .models import GroundednessResult
from .pii import PIIDetector
from .text_utils import content_tokens, numbers, split_sentences

_NON_CLAIM = re.compile(
    r"^(?:hello|hi|hey|namaste|thanks?|thank\s+you|sure|of\s+course|certainly|please|sorry|"
    r"i\s+(?:can|could)\s+(?:only|not|help|assist)|i(?:'m|\s+am)\s+(?:sorry|unable|not\s+able)|"
    r"i\s+(?:can't|cannot|don't\s+know|do\s+not\s+know)|you\s+can\s+(?:contact|call|email|visit)|"
    r"feel\s+free|let\s+me\s+know|for\s+(?:more|further)\s+(?:help|details|information))\b",
    re.I,
)
_pii = PIIDetector()


def _strip_public_contacts(text: str) -> str:
    """Bank ko public email/phone hataidine (tiniharu ko 'unsupported number' bhanera fail nahos)."""
    for m in sorted(_pii.detect(text), key=lambda x: x.start, reverse=True):
        if _pii.is_public(m):
            text = text[: m.start] + text[m.end:]
    return text


class GroundednessValidator:
    def _windows(self, docs: list) -> list:
        """Har doc ko 1-sentence ra 2-sentence window (tokens + numbers)."""
        wins = []
        for d in docs:
            sents = split_sentences(d["text"])
            for i in range(len(sents)):
                for size in (1, 2):
                    chunk = " ".join(sents[i:i + size])
                    wins.append({"id": d["id"], "tokens": content_tokens(chunk), "nums": numbers(chunk)})
        return wins

    def check(self, answer: str, sources: list, docs: list) -> GroundednessResult:
        ref_ids = {d["id"] for d in docs}
        invalid = [s for s in sources if s not in ref_ids]
        windows = self._windows(docs)
        claims, unsupported = [], []

        for sent in split_sentences(answer):
            stripped = _strip_public_contacts(sent)
            toks, nums = content_tokens(stripped), numbers(stripped)
            is_short = len(toks) < 3 and not nums
            is_deflection = bool(_NON_CLAIM.match(stripped.strip())) and not nums and len(stripped.split()) <= 20
            if is_short or is_deflection:
                continue                                   # factual claim hoina -> skip

            best_overlap, supported = 0.0, False
            for w in windows:
                overlap = len(toks & w["tokens"]) / len(toks) if toks else 1.0
                best_overlap = max(best_overlap, overlap)
                if overlap >= config.SENTENCE_SUPPORT_THRESHOLD and nums <= w["nums"]:
                    supported = True
                    break
            claim = {"sentence": sent, "supported": supported, "overlap": round(best_overlap, 2),
                     "has_numbers": bool(nums)}
            claims.append(claim)
            if not supported:
                unsupported.append(claim)

        total = len(claims)
        score = 1.0 if total == 0 else round((total - len(unsupported)) / total, 2)
        critical = [c for c in unsupported if c["has_numbers"]]   # galat number = seedai fail

        if invalid:
            reason = f"cited sources not in reference docs: {invalid}"
        elif critical:
            reason = "unsupported claim containing numbers"
        elif score < config.GROUNDEDNESS_MIN_SCORE:
            reason = f"groundedness score {score} < {config.GROUNDEDNESS_MIN_SCORE}"
        else:
            reason = "ok"
        return GroundednessResult(grounded=(reason == "ok"), score=score, claims=claims,
                                  unsupported=unsupported, invalid_citations=invalid, reason=reason)
