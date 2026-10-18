"""
topics.py  (INPUT guardrail #3)
-------------------------------
Approach : Keyword/regex rules (English + Roman Nepali + thoda Devanagari), category anusar priority.
Action   : Har category ko afnai action chha (table talako):

  Category           Action                  Kina?
  -----------------  ----------------------  -------------------------------------------------
  SELF_HARM          ESCALATE_CRISIS         LLM le answer nadine; supportive message + helpline
  ILLEGAL_ACTIVITY   REFUSE                  money laundering, jaali document, hundi/hawala ...
  THIRD_PARTY_ACCESS REFUSE                  arko manche ko balance/OTP/password (privacy)
  FRAUD_REPORT       HUMAN_HANDOFF           unauthorized transaction -> urgent, human le herne
  LEGAL_DISPUTE      HUMAN_HANDOFF           sue/court/lawyer -> bot le legal kura bhanna hudaina
  FINANCIAL_ADVICE   ANSWER_WITH_DISCLAIMER  investment salaha haina, general info + disclaimer

Priority: SELF_HARM sabai bhanda mathi (safety first), tespachi serial order.
Limitation:
  - Keyword matching ho -> implicit/indirect wording miss hunchha ("I don't see any point going on").
  - Broad keyword (jastai "court") le legit question ("court fee") pani flag garchha (false positive).
  - Multilingual coverage limited.
"""
import re
import unicodedata
from .models import TopicResult

_RULES = [
    ("SELF_HARM", "ESCALATE_CRISIS", [
        r"\b(?:kill|hurt|harm|end)\s+(?:my\s*self|myself|my\s+life)\b",
        r"\bsuicid(?:e|al)\b",
        r"\b(?:want|wanna)\s+to\s+die\b",
        r"\b(?:don'?t|do\s+not)\s+want\s+to\s+(?:live|be\s+alive)\b",
        r"\bno\s+reason\s+to\s+live\b",
        r"\b(?:aa?tmahatya|marna\s+man\s+lag\w*|marna\s+chah\w*|bachna\s+man\s+lagdaina)\b",
        r"आत्महत्या|मर्न\s*मन\s*लाग",
    ]),
    ("ILLEGAL_ACTIVITY", "REFUSE", [
        r"\blaunder(?:ing)?\s+(?:my\s+|the\s+|some\s+|black\s+)?(?:money|cash|funds)\b",
        r"\bhow\s+(?:to|can\s+i|do\s+i)\s+launder\b",
        r"\b(?:fake|forged|forge|counterfeit|jaali|jali|nakali)\s+(?:\w+\s+){0,2}(?:citizenship|kyc|documents?|cheques?|checks?|passports?|notes|currency|id)\b",
        r"\bbypass\s+(?:the\s+)?(?:kyc|aml|verification|otp)\b",
        r"\b(?:hack|hacking|crack)\s+(?:into\s+)?(?:\w+\s+){0,2}(?:account|atm|bank|app|wallet)\b",
        r"\btax\s+evasion\b|\bevade\s+(?:the\s+)?tax",
        r"\b(?:hawala|hundi)\b",
    ]),
    ("THIRD_PARTY_ACCESS", "REFUSE", [
        r"\b(?:someone\s+else'?s?|somebody\s+else'?s?|another\s+person'?s?|"
        r"my\s+(?:wife|husband|ex|friend|neighbou?r|boss|colleague|brother|sister)'?s?)\s+(?:\w+\s+){0,2}?"
        r"(?:balance|password|otp|pin|account\s+details|transactions?|statement|card\s+number)\b",
        r"\b(?:otp|pin|password)\s+of\s+(?:someone|another|my\s+(?:wife|husband|friend|ex))\b",
    ]),
    ("FRAUD_REPORT", "HUMAN_HANDOFF", [
        r"\b(?:unauthori[sz]ed|fraudulent|suspicious)\s+(?:\w+\s+){0,2}?(?:transactions?|transfers?|withdrawals?|activity|charges?)\b",
        r"\bmy\s+account\s+(?:was|got|has\s+been|is)\s+(?:hacked|compromised)\b|\bhacked\s+my\s+account\b",
        r"\bscammed\b|\b(?:i|we)\s+(?:was|were|got|have\s+been)\s+(?:cheated|defrauded)\b",
    ]),
    ("LEGAL_DISPUTE", "HUMAN_HANDOFF", [
        r"\b(?:sue|suing|lawsuit|legal\s+action|court|consumer\s+(?:court|forum)|lawyer|advocate|file\s+a\s+case|police\s+complaint)\b",
    ]),
    ("FINANCIAL_ADVICE", "ANSWER_WITH_DISCLAIMER", [
        r"\bshould\s+i\s+(?:buy|sell|invest|put\s+my)\b",
        r"\bwhich\s+(?:share|stock|ipo|mutual\s+fund)s?\s+(?:is|are|should|to)\b",
        r"\b(?:best|good|safe)\s+(?:stock|share|investment|crypto|ipo)s?\b",
        r"\bwill\s+(?:nepse|the\s+market|the\s+share\s+market)\s+(?:go|rise|fall|crash|increase|decrease)\b",
        r"\binvest\w*\s+(?:in\s+)?(?:nepse|crypto|bitcoin|shares?|stocks?)\b",
    ]),
]

_COMPILED = [(c, a, [re.compile(p, re.I) for p in pats]) for c, a, pats in _RULES]


class TopicClassifier:
    def classify(self, text: str) -> TopicResult:
        norm = unicodedata.normalize("NFKC", text)
        matched = [(c, a) for c, a, pats in _COMPILED if any(p.search(norm) for p in pats)]
        if not matched:
            return TopicResult(category=None, action="ALLOW", matched_categories=[])
        cat, action = matched[0]            # rules ko order = priority order
        return TopicResult(category=cat, action=action, matched_categories=[c for c, _ in matched])
