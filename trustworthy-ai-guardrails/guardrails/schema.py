"""
schema.py  (OUTPUT guardrail #1)
--------------------------------
Approach : Hand-written validator (jsonschema library chahidaina). LLM le dinu parne JSON:
           { answer:str(1..1000), category:enum, confidence:float[0,1], sources:[KB-xxx], needs_human:bool }
Action   : Invalid bhayo bhane -> REJECT -> pipeline le regenerate garcha, tyo pani fail bhayo bhane safe fallback.
Light repair: ```json fence ya agadi-pachadi extra text bhaye {...} nikalera parse garne (config le on/off).
Limitation:
  - Yo le STRUCTURE matra check garchha, MEANING hoina. Valid JSON ma galat answer pani pass hunchha
    (tesaiko lagi groundedness validator chahinchha).
  - Repair on rakhda attacker/LLM le extra text lukaera pathauna sakchha (tara hami JSON bhitrako matra use garchau).
"""
import json
import math
import re
from . import config
from .models import SchemaResult

REQUIRED_FIELDS = ("answer", "category", "confidence", "sources", "needs_human")


class SchemaValidator:
    def _parse(self, raw: str):
        text = raw.strip()
        try:
            return json.loads(text), False
        except ValueError:
            pass
        if config.ALLOW_JSON_REPAIR:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1]), True
                except ValueError:
                    pass
        return None, False

    def validate(self, raw) -> SchemaResult:
        if not isinstance(raw, str):
            return SchemaResult(False, ["output is not a string"], None)
        parsed, repaired = self._parse(raw)
        if parsed is None:
            return SchemaResult(False, ["output is not valid JSON"], None)
        if not isinstance(parsed, dict):
            return SchemaResult(False, ["top-level JSON must be an object"], None, repaired)

        errors = []
        missing = [f for f in REQUIRED_FIELDS if f not in parsed]
        extra = [k for k in parsed if k not in REQUIRED_FIELDS]
        if missing:
            errors.append(f"missing fields: {missing}")
        if extra:
            errors.append(f"unexpected fields: {extra}")

        if "answer" in parsed:
            a = parsed["answer"]
            if not isinstance(a, str) or not a.strip():
                errors.append("answer must be a non-empty string")
            elif len(a) > config.ANSWER_MAX_CHARS:
                errors.append(f"answer longer than {config.ANSWER_MAX_CHARS} chars")

        if "category" in parsed and parsed["category"] not in config.ALLOWED_CATEGORIES:
            errors.append(f"category must be one of {list(config.ALLOWED_CATEGORIES)}")

        if "confidence" in parsed:
            c = parsed["confidence"]
            # bool pani Python ma int ho -> alag check garnu parcha
            if isinstance(c, bool) or not isinstance(c, (int, float)):
                errors.append("confidence must be a number")
            elif math.isnan(c) or not 0.0 <= c <= 1.0:
                errors.append("confidence must be between 0 and 1")

        if "sources" in parsed:
            s = parsed["sources"]
            if not isinstance(s, list) or not all(isinstance(x, str) for x in s):
                errors.append("sources must be a list of strings")
            else:
                bad = [x for x in s if not re.match(config.SOURCE_ID_PATTERN, x)]
                if bad:
                    errors.append(f"invalid source ids: {bad}")
                if not s and parsed.get("category") != "out_of_scope":
                    errors.append("sources cannot be empty unless category is out_of_scope")

        if "needs_human" in parsed and not isinstance(parsed["needs_human"], bool):
            errors.append("needs_human must be a boolean")

        return SchemaResult(valid=not errors, errors=errors, parsed=parsed if not errors else None, repaired=repaired)
