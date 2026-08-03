from jd_keyword_check import extract_keywords, overlap_score, top_missing_keywords

SYSTEMS_RESUME = """
Experienced in writing Linux kernel drivers, C and C++ systems programming,
memory management, multithreading, network sockets, and real-time embedded
firmware development on ARM microcontrollers.
"""

FULLSTACK_RESUME = """
Built React and TypeScript frontends, Node.js REST APIs, PostgreSQL
databases, Docker containers, and deployed on AWS with CI/CD pipelines.
"""

DRIVER_JD = """
We are looking for a Software Engineer Intern to write Linux kernel drivers
in C, work on memory management and multithreading, and debug embedded
firmware on ARM microcontrollers.
"""


def test_overlap_score_high_for_matching_domain():
    score = overlap_score(SYSTEMS_RESUME, DRIVER_JD)
    assert score >= 0.5


def test_overlap_score_low_for_mismatched_domain():
    score = overlap_score(FULLSTACK_RESUME, DRIVER_JD)
    assert score < 0.3


def test_top_missing_keywords_flags_domain_gap():
    missing = top_missing_keywords(FULLSTACK_RESUME, DRIVER_JD)
    assert "kernel" in missing or "firmware" in missing


def test_extract_keywords_strips_stopwords():
    keywords = extract_keywords("The quick engineer is working with the team")
    assert "the" not in keywords
    assert "is" not in keywords
    assert "engineer" in keywords


def test_overlap_score_is_permissive_when_jd_has_no_keywords():
    # an empty/unparseable JD shouldn't produce a false "bad match" warning
    assert overlap_score(FULLSTACK_RESUME, "") == 1.0
