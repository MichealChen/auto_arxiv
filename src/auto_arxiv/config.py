from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    categories: tuple[str, ...]
    keywords: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    followed_authors: tuple[str, ...]


@dataclass(frozen=True)
class SearchConfig:
    days_back: int
    max_results: int


@dataclass(frozen=True)
class OutputConfig:
    limit: int
    min_score: float
    directory: Path
    data_directory: Path
    download_directory: Path


@dataclass(frozen=True)
class AppConfig:
    profile: ProfileConfig
    search: SearchConfig
    output: OutputConfig


def load_config(path: Path) -> AppConfig:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Copy config.example.toml to config.toml first."
        )

    with path.open("rb") as file:
        raw = tomllib.load(file)

    profile = raw.get("profile", {})
    search = raw.get("search", {})
    output = raw.get("output", {})

    return AppConfig(
        profile=ProfileConfig(
            name=str(profile.get("name", "My Research Radar")),
            categories=_as_tuple(profile.get("categories", [])),
            keywords=_as_tuple(profile.get("keywords", [])),
            exclude_keywords=_as_tuple(profile.get("exclude_keywords", [])),
            followed_authors=_as_tuple(profile.get("followed_authors", [])),
        ),
        search=SearchConfig(
            days_back=max(1, int(search.get("days_back", 2))),
            max_results=max(1, int(search.get("max_results", 100))),
        ),
        output=OutputConfig(
            limit=max(1, int(output.get("limit", 10))),
            min_score=float(output.get("min_score", 2.0)),
            directory=_resolve_config_path(path, output.get("directory", "recommendations")),
            data_directory=_resolve_config_path(path, output.get("data_directory", "data")),
            download_directory=_resolve_config_path(path, output.get("download_directory", "downloads")),
        ),
    )


def _as_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError("Expected a TOML array of strings.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _resolve_config_path(config_path: Path, value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return config_path.parent / path
