import re
from pathlib import Path


def test_strategy_docs_track_active_archive_history_diagnostics_task():
    roadmap = Path("docs/strategy/ROADMAP.md").read_text(encoding="utf-8")
    todo = Path("TODO.md").read_text(encoding="utf-8")
    archive = Path("docs/tasks/archive/019-ground-transport-scaffold.md")

    assert archive.exists()
    archive_text = archive.read_text(encoding="utf-8")
    assert "flight`, `bus`, `train" in roadmap
    assert "Diagnostics fournisseurs exposent `distribusion`" in roadmap
    assert "Étape 02" in todo
    assert "Distribusion" in todo
    assert "Mode `train`" in archive_text
    assert "DISTRIBUSION credentials missing" in archive_text


def test_task_archive_files_are_numbered_chronologically():
    files = sorted(Path("docs/tasks/archive").glob("*.md"))
    names = [path.name for path in files]
    prefixes = [name.split("-", 1)[0] for name in names]

    assert prefixes == [f"{index:03d}" for index in range(1, len(names) + 1)]
    assert all(re.match(r"^\d{3}-[a-z0-9-]+\.md$", name) for name in names)
