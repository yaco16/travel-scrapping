from pathlib import Path


def test_strategy_docs_track_end_date_numbered_steps():
    roadmap = Path("docs/strategy/ROADMAP.md").read_text(encoding="utf-8")
    todo = Path("TODO.md").read_text(encoding="utf-8")
    active_files = list(Path("docs/tasks/active").glob("*.md"))
    archive = Path("docs/tasks/archive/2026-06-20-end-date-numbered-steps.md")

    assert active_files == []
    assert archive.exists()
    archive_text = archive.read_text(encoding="utf-8")
    assert "SEARCH_END_DATE=2026-08-31" in roadmap
    assert "Étape 01" in roadmap
    assert "Étape 02" in todo
    assert "Étape 03" in archive_text
    assert "31/08/26" in archive_text
