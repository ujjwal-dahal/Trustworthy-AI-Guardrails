"""
llm.py
------
LLM adapters. Sabai le `generate(user_message, docs, strict=False) -> str (raw JSON text)` implement garchhan.

  MockLLM       - offline, deterministic. Retrieved doc bata sentence nikalera valid JSON banaucha. (default)
  ScriptedLLM   - test ko lagi: tapai le diyeko raw outputs ek-ek garera return garcha
                  (bad JSON, hallucination, leak jasto failure inject garna).
  AnthropicLLM  - optional real LLM (pip install anthropic + ANTHROPIC_API_KEY). Yo project ma test gareko chhaina.
"""
import json
import os
import re
from . import config
from .text_utils import content_tokens, split_sentences


def build_user_prompt(user_message: str, docs: list, strict: bool = False) -> str:
    refs = "\n".join(f"[{d['id']}] {d['text']}" for d in docs) or "(no relevant documents found)"
    extra = ("\nSTRICT MODE: use ONLY facts stated verbatim in the documents. Do not add any numbers or claims "
             "that are not in them. Reply with valid JSON only." if strict else "")
    return f"Reference documents:\n{refs}\n\nCustomer question: {user_message}{extra}"


class BaseLLM:
    def generate(self, user_message: str, docs: list, strict: bool = False) -> str:
        raise NotImplementedError


class MockLLM(BaseLLM):
    def generate(self, user_message, docs, strict=False):
        if not docs:
            return json.dumps({
                "answer": "I can only help with Mero Bank services such as accounts, cards, loans and remittance. "
                          "Please contact support for anything else.",
                "category": "out_of_scope", "confidence": 0.3, "sources": [], "needs_human": True,
            })
        top = docs[0]
        q = content_tokens(user_message)
        sents = split_sentences(top["text"])
        ranked = sorted(range(len(sents)), key=lambda i: -len(q & content_tokens(sents[i])))
        chosen = [i for i in ranked[:2] if len(q & content_tokens(sents[i])) > 0] or [0]
        answer = " ".join(sents[i] for i in sorted(chosen))
        return json.dumps({"answer": answer, "category": top["category"], "confidence": 0.8,
                           "sources": [top["id"]], "needs_human": False})


class ScriptedLLM(BaseLLM):
    """Test ko lagi: responses list bata ek-ek garera return; sakiyo bhane aakhiri response repeat."""
    def __init__(self, responses: list):
        self.responses, self.calls = list(responses), 0

    def generate(self, user_message, docs, strict=False):
        r = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return r


class AnthropicLLM(BaseLLM):  # pragma: no cover - network chahincha, yaha run gareko chhaina
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str = None):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def generate(self, user_message, docs, strict=False):
        resp = self.client.messages.create(
            model=self.model, max_tokens=600, system=config.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(user_message, docs, strict)}],
        )
        return resp.content[0].text
