"""Lightweight resume-vs-job-description keyword overlap check — no ML/NLP
dependency, just tokenize + stopword-strip + set/frequency comparison. Meant
to catch "sent the wrong resume variant for this role" before you commit to
sending it, not to be a precise ATS simulator.
"""
from __future__ import annotations

import html
import re
from collections import Counter

import requests

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "our", "that", "the",
    "to", "was", "we", "will", "with", "you", "your", "this", "these",
    "those", "have", "had", "but", "not", "all", "can", "who", "what",
    "when", "where", "why", "how", "their", "they", "them", "us", "if",
    "about", "into", "than", "then", "so", "such", "more", "most", "other",
    "some", "any", "each", "which", "while", "per", "etc", "including",
    "team", "role", "work", "working", "job", "years", "year", "experience",
    "strong", "ability", "excellent", "looking", "join", "new",
    # generic filler that dominates real job-posting boilerplate (EEO/culture/
    # benefits sections) without carrying any skill signal
    "do", "does", "did", "done", "one", "like", "need", "needs", "ll", "re",
    "ve", "please", "time", "end", "opportunity", "opportunities", "world",
    "people", "life", "make", "made", "get", "gets", "help", "helps",
    "provide", "provides", "across", "many", "well", "also", "may", "must",
}

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#.]*")


def _tokenize(text: str) -> list[str]:
    raw_tokens = _TOKEN_RE.findall(text.lower())
    tokens = []
    for token in raw_tokens:
        token = token.rstrip(".")  # trailing sentence periods, not "node.js"-style dots
        if token and token not in _STOPWORDS and len(token) > 1:
            tokens.append(token)
    return tokens


def extract_keywords(text: str) -> set[str]:
    return set(_tokenize(text))


def _keyword_frequencies(text: str) -> Counter:
    return Counter(_tokenize(text))


_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def fetch_jd_text(job_url: str) -> str:
    response = requests.get(job_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    text = _SCRIPT_STYLE_RE.sub(" ", response.text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)  # &nbsp;/&amp;/etc. were otherwise leaking in as fake "keywords"
    return re.sub(r"\s+", " ", text).strip()


def overlap_score(resume_text: str, jd_text: str, top_k: int = 50) -> float:
    """Overlap against only the JD's `top_k` most-frequent keywords, not its
    entire unique vocabulary. A real job posting's unique-word count is
    dominated by one-off EEO/benefits/culture boilerplate (measured: ~450
    unique keywords on a real ~7,000-character posting) — scoring against
    the full set makes it mathematically impossible for a short resume to
    score meaningfully even on a strong match. The words a JD repeats are a
    much better proxy for what it actually cares about.
    """
    jd_freq = _keyword_frequencies(jd_text)
    if not jd_freq:
        return 1.0  # nothing meaningful to compare against; don't false-warn
    top_jd_keywords = {word for word, _ in jd_freq.most_common(top_k)}
    resume_keywords = extract_keywords(resume_text)
    matched = top_jd_keywords & resume_keywords
    return len(matched) / len(top_jd_keywords)


def top_missing_keywords(resume_text: str, jd_text: str, limit: int = 15) -> list[str]:
    """JD keywords not present in the resume, ranked by how often the JD uses them."""
    resume_keywords = extract_keywords(resume_text)
    freq = _keyword_frequencies(jd_text)
    missing = [word for word, _ in freq.most_common() if word not in resume_keywords]
    return missing[:limit]
