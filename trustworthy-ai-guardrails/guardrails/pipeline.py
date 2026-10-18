"""
pipeline.py
-----------
Pura flow yaha jodiyeko chha:

  user msg -> InputGuard -> (terminal action bhaye canned response)
           -> Retriever -> LLM -> OutputGuard -> PASS/REDACTED -> final response
                                     -> REJECTED -> regenerate (max MAX_REGENERATIONS) -> SAFE_FALLBACK

Privacy: trace ma raw user text / raw LLM output store gardaina (sanitized matra).
"""
from . import config
from .input_guard import InputGuard
from .knowledge_base import KnowledgeBase
from .models import PipelineResult
from .output_guard import OutputGuard

_TERMINAL = {"INVALID_INPUT", "BLOCK_INJECTION", "REFUSE", "ESCALATE_CRISIS", "HUMAN_HANDOFF"}


class GuardrailPipeline:
    def __init__(self, llm, kb=None, input_guard=None, output_guard=None, max_regenerations=None):
        self.llm = llm
        self.kb = kb or KnowledgeBase()
        self.input_guard = input_guard or InputGuard()
        self.output_guard = output_guard or OutputGuard()
        self.max_regenerations = config.MAX_REGENERATIONS if max_regenerations is None else max_regenerations

    def handle(self, user_message) -> PipelineResult:
        decision = self.input_guard.check(user_message)

        # --- Stage 1: input guardrails le rokyo bhane LLM call nai hudaina ---
        if decision.action in _TERMINAL:
            return PipelineResult(decision.sanitized_text, decision.action,
                                  config.MESSAGES[decision.action], decision)

        # --- Stage 2: retrieve + generate + output guardrails (regenerate loop) ---
        docs = self.kb.retrieve(decision.sanitized_text)
        attempts, final = [], None
        for attempt in range(self.max_regenerations + 1):
            raw = self.llm.generate(decision.sanitized_text, docs, strict=attempt > 0)
            out = self.output_guard.check(raw, docs)
            attempts.append({"attempt": attempt + 1, "status": out.status, "reasons": out.reasons})
            if out.status in ("PASS", "REDACTED"):
                final = out
                break

        ids = [d["id"] for d in docs]
        if final is None:                                   # sabai attempt fail -> safe fallback
            return PipelineResult(decision.sanitized_text, "SAFE_FALLBACK", config.MESSAGES["SAFE_FALLBACK"],
                                  decision, ids, attempts, "REJECTED")

        a = final.answer
        text = a["answer"]
        if a["sources"]:
            text += f"\n\n(Sources: {', '.join(a['sources'])})"
        if a["needs_human"]:
            text += config.MESSAGES["NEEDS_HUMAN_SUFFIX"]
        action = "ANSWERED"
        if decision.action == "ALLOW_WITH_DISCLAIMER":
            text = config.MESSAGES["DISCLAIMER_PREFIX"] + text
            action = "ANSWERED_WITH_DISCLAIMER"
        return PipelineResult(decision.sanitized_text, action, text, decision, ids, attempts, final.status)
