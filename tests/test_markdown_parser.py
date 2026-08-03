from pathlib import Path

from watchers.parsers.markdown_parser import parse_markdown_table

SPEEDYAPPLY_FIXTURE = Path(__file__).parent / "fixtures" / "speedyapply_sample.md"
JOBRIGHT_FIXTURE = Path(__file__).parent / "fixtures" / "jobright_sample.md"


def test_parses_html_style_table_speedyapply():
    listings = parse_markdown_table(SPEEDYAPPLY_FIXTURE.read_text())

    assert len(listings) == 3  # 2 FAANG rows + 1 Quant row
    companies = {l.company for l in listings}
    assert companies == {"NVIDIA", "Rivian", "Citadel"}

    nvidia = next(l for l in listings if l.company == "NVIDIA")
    assert nvidia.title.startswith("Performance Engineer Intern")
    assert nvidia.location == "St. Louis, MO"
    assert nvidia.url == (
        "https://nvidia.wd5.myworkdayjobs.com/en-US/nvidiaexternalcareersite/job/"
        "US-MO-St-Louis/Performance-Engineer-Intern--Systems-Software---Fall-2026_JR2015779"
    )
    assert nvidia.date_posted == "27d"


def test_parses_markdown_link_style_with_continuation_jobright():
    listings = parse_markdown_table(JOBRIGHT_FIXTURE.read_text())

    assert len(listings) == 3
    assert listings[0].company == "Copart"
    # continuation row ("↳") should inherit the company from the row above it
    assert listings[1].company == "Copart"
    assert listings[1].title.startswith("Software Engineering Intern")
    assert listings[1].url == (
        "https://jobright.ai/jobs/info/6a6b61bc5c54bc4752ce894c?utm_campaign=1079&utm_source=git"
    )
    assert listings[2].company == "ByteDance"
