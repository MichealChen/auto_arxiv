from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import shorten

from .config import AppConfig
from .scoring import ScoredPaper


def write_markdown_report(
    papers: list[ScoredPaper],
    config: AppConfig,
    generated_at: datetime,
) -> Path:
    config.output.directory.mkdir(parents=True, exist_ok=True)
    report_date = generated_at.astimezone().date().isoformat()
    output_path = config.output.directory / f"{report_date}.md"
    output_path.write_text(
        render_markdown_report(papers, config=config, generated_at=generated_at),
        encoding="utf-8",
    )
    return output_path


def render_markdown_report(
    papers: list[ScoredPaper],
    config: AppConfig,
    generated_at: datetime,
) -> str:
    report_date = generated_at.astimezone().date().isoformat()
    lines = [
        f"# arXiv Daily Recommendations - {report_date}",
        "",
        f"Profile: {config.profile.name}",
        f"Generated at: {generated_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Filters: last {config.search.days_back} day(s), score >= {config.output.min_score}",
        "",
    ]

    if not papers:
        lines.extend(
            [
                "No papers matched today's filters.",
                "",
                "Try lowering `output.min_score`, increasing `search.days_back`, or adding broader keywords.",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    for index, scored in enumerate(papers, start=1):
        paper = scored.paper
        authors = ", ".join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors += ", et al."

        lines.extend(
            [
                f"## {index}. {paper.title}",
                "",
                f"- Score: {scored.score:.1f}",
                f"- arXiv: [{paper.arxiv_id}]({paper.abs_url})",
                f"- PDF: {paper.pdf_url or 'N/A'}",
                f"- Authors: {authors or 'N/A'}",
                f"- Categories: {', '.join(paper.categories) or 'N/A'}",
                f"- Published: {paper.published.date().isoformat()}",
                f"- Updated: {paper.updated.date().isoformat()}",
                f"- Matched keywords: {', '.join(scored.matched_keywords) or 'N/A'}",
                f"- Why recommended: {'; '.join(scored.recommendation_reasons) or 'N/A'}",
                "",
                shorten(paper.abstract, width=700, placeholder="..."),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"
