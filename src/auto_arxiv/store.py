from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json

from .arxiv_client import Paper
from .config import AppConfig
from .scoring import ScoredPaper


def write_recommendation_data(
    *,
    all_papers: list[Paper],
    selected_papers: list[ScoredPaper],
    ranked_count: int,
    fetched_count: int,
    config: AppConfig,
    generated_at: datetime,
) -> Path:
    data_dir = config.output.data_directory
    daily_dir = data_dir / "daily"
    data_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)

    report_date = generated_at.astimezone().date().isoformat()
    payload = build_recommendation_payload(
        selected_papers=selected_papers,
        ranked_count=ranked_count,
        fetched_count=fetched_count,
        config=config,
        generated_at=generated_at,
    )

    latest_path = data_dir / "recommendations.json"
    daily_path = daily_dir / f"{report_date}.json"
    papers_path = data_dir / "papers.json"
    history_path = data_dir / "history.json"

    _write_json(latest_path, payload)
    _write_json(daily_path, payload)
    _write_json(papers_path, _merge_papers(papers_path, all_papers))
    _write_json(history_path, _update_history(history_path, payload))

    return latest_path


def build_recommendation_payload(
    *,
    selected_papers: list[ScoredPaper],
    ranked_count: int,
    fetched_count: int,
    config: AppConfig,
    generated_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "date": generated_at.astimezone().date().isoformat(),
        "generated_at": generated_at.astimezone().isoformat(),
        "profile": {
            "name": config.profile.name,
            "categories": list(config.profile.categories),
            "keywords": list(config.profile.keywords),
            "exclude_keywords": list(config.profile.exclude_keywords),
            "followed_authors": list(config.profile.followed_authors),
        },
        "filters": {
            "days_back": config.search.days_back,
            "max_results": config.search.max_results,
            "limit": config.output.limit,
            "min_score": config.output.min_score,
        },
        "stats": {
            "fetched": fetched_count,
            "matched": ranked_count,
            "selected": len(selected_papers),
        },
        "papers": [
            scored_paper_to_dict(index=index, scored=scored)
            for index, scored in enumerate(selected_papers, start=1)
        ],
    }


def scored_paper_to_dict(index: int, scored: ScoredPaper) -> dict[str, Any]:
    paper = scored.paper
    return {
        "rank": index,
        "score": round(scored.score, 3),
        "matched_keywords": list(scored.matched_keywords),
        "recommendation_reasons": list(scored.recommendation_reasons),
        **paper_to_dict(paper),
    }


def paper_to_dict(paper: Paper) -> dict[str, Any]:
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": list(paper.authors),
        "categories": list(paper.categories),
        "published": paper.published.isoformat(),
        "updated": paper.updated.isoformat(),
        "abs_url": paper.abs_url,
        "pdf_url": paper.pdf_url,
    }


def load_latest_recommendations(data_directory: Path) -> dict[str, Any]:
    return _read_json(data_directory / "recommendations.json")


def load_daily_recommendations(data_directory: Path, date: str) -> dict[str, Any]:
    return _read_json(data_directory / "daily" / f"{date}.json")


def load_history(data_directory: Path) -> dict[str, Any]:
    history_path = data_directory / "history.json"
    if not history_path.exists():
        return {"schema_version": 1, "dates": []}
    return _read_json(history_path)


def load_user_state(data_directory: Path) -> dict[str, Any]:
    state_path = data_directory / "user_state.json"
    if not state_path.exists():
        return {"schema_version": 1, "papers": {}}
    return _read_json(state_path)


def update_user_state(
    data_directory: Path,
    arxiv_id: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    data_directory.mkdir(parents=True, exist_ok=True)
    state = load_user_state(data_directory)
    paper_state = state.setdefault("papers", {}).setdefault(arxiv_id, {})

    for key in ("favorite", "read", "ignored", "reading_list"):
        if key in values:
            paper_state[key] = bool(values[key])
    if "note" in values:
        paper_state["note"] = str(values["note"])

    _write_json(data_directory / "user_state.json", state)
    return state


def find_paper_in_data(data_directory: Path, arxiv_id: str) -> dict[str, Any] | None:
    papers_path = data_directory / "papers.json"
    if papers_path.exists():
        paper_map = _read_json(papers_path).get("papers", {})
        if arxiv_id in paper_map:
            return paper_map[arxiv_id]

    for payload in _iter_payloads(data_directory):
        for paper in payload.get("papers", []):
            if paper.get("arxiv_id") == arxiv_id:
                return paper
    return None


def load_reading_list(data_directory: Path) -> list[dict[str, Any]]:
    state = load_user_state(data_directory)
    papers: list[dict[str, Any]] = []
    for arxiv_id, values in state.get("papers", {}).items():
        if not values.get("reading_list"):
            continue
        paper = find_paper_in_data(data_directory, arxiv_id)
        if paper is None:
            continue
        papers.append({**paper, "user_state": values})

    return sorted(papers, key=lambda item: item.get("updated", ""), reverse=True)


def _merge_papers(path: Path, papers: list[Paper]) -> dict[str, Any]:
    if path.exists():
        payload = _read_json(path)
    else:
        payload = {"schema_version": 1, "papers": {}}

    paper_map = payload.setdefault("papers", {})
    for paper in papers:
        paper_map[paper.arxiv_id] = paper_to_dict(paper)

    return payload


def _update_history(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        history = _read_json(path)
    else:
        history = {"schema_version": 1, "dates": []}

    dates = [
        item for item in history.get("dates", [])
        if item.get("date") != payload["date"]
    ]
    dates.insert(
        0,
        {
            "date": payload["date"],
            "generated_at": payload["generated_at"],
            "profile": payload["profile"]["name"],
            "selected": payload["stats"]["selected"],
            "matched": payload["stats"]["matched"],
        },
    )
    history["dates"] = dates
    return history


def _iter_payloads(data_directory: Path):
    latest = data_directory / "recommendations.json"
    if latest.exists():
        yield _read_json(latest)

    daily_dir = data_directory / "daily"
    if daily_dir.exists():
        for path in sorted(daily_dir.glob("*.json"), reverse=True):
            yield _read_json(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
