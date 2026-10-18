"""
text_utils.py
-------------
Tokenize, stem, number extraction jasta chhoto helper haru.
Retriever ra groundedness validator duitai le yehi use garchhan (consistency ko lagi).
"""
import re

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "for", "with", "by", "from",
    "as", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these", "those",
    "i", "you", "your", "we", "our", "my", "me", "he", "she", "they", "them", "their", "can", "will",
    "would", "should", "could", "may", "might", "must", "do", "does", "did", "has", "have", "had", "what",
    "how", "when", "which", "who", "there", "than", "then", "also", "any", "all", "some", "per", "into",
    "about", "tell", "please", "want", "need", "get", "give", "show", "much", "many", "one", "out", "off",
}

_WORD = re.compile(r"[a-z]+")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def stem(word: str) -> str:
    """Bahut simple stemmer: charges/charged/charge -> 'charg'. (NLTK chaina, dependency-free rakhna)"""
    for suf in ("ing", "ed", "ly", "s"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            word = word[: -len(suf)]
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def content_tokens(text: str) -> set:
    """Stopword hataera, stem gareko content words ko set."""
    words = _WORD.findall(text.lower())
    return {stem(w) for w in words if len(w) >= 3 and w not in STOPWORDS}


def numbers(text: str) -> set:
    """'NPR 50,000' -> {'50000'}, '9.5%' -> {'9.5'}"""
    return {n.replace(",", "") for n in _NUM.findall(text)}


def split_sentences(text: str) -> list:
    return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
