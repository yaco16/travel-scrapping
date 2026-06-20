import re
from pathlib import Path


def test_strategy_docs_track_active_archive_history_diagnostics_task():
    roadmap = Path("docs/strategy/ROADMAP.md").read_text(encoding="utf-8")
    todo = Path("TODO.md").read_text(encoding="utf-8")
    archive = Path("docs/tasks/archive/012-end-date-numbered-steps.md")

    assert archive.exists()
    archive_text = archive.read_text(encoding="utf-8")
    assert "SEARCH_END_DATE=2026-08-31" in roadmap
    assert "Diagnostics fournisseurs" in roadmap
    assert "Étape 02" in todo
    assert "SerpApi" in todo
    assert "Étape 03" in archive_text
    assert "31/08/26" in archive_text


def test_task_archive_files_are_numbered_chronologically():
    files = sorted(Path("docs/tasks/archive").glob("*.md"))
    names = [path.name for path in files]
    prefixes = [name.split("-", 1)[0] for name in names]

    assert prefixes == [f"{index:03d}" for index in range(1, len(names) + 1)]
    assert all(re.match(r"^\d{3}-[a-z0-9-]+\.md$", name) for name in names)
