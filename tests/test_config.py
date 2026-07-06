from auto_arxiv.config import load_config


def test_load_config_resolves_relative_output_paths_from_config_location(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    config_path = app_dir / "config.toml"
    config_path.write_text(
        """
[profile]
name = "Test"
categories = ["cs.AI"]
keywords = ["agent"]
exclude_keywords = []

[search]
days_back = 2
max_results = 10

[output]
limit = 5
min_score = 2.0
directory = "recommendations"
data_directory = "data"
download_directory = "downloads"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = load_config(config_path)

    assert config.output.directory == app_dir / "recommendations"
    assert config.output.data_directory == app_dir / "data"
    assert config.output.download_directory == app_dir / "downloads"
