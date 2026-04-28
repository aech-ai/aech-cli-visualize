from pathlib import Path

from aech_cli_visualize.config.repository import ConfigRepository


def test_default_repository_path_uses_agent_work_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    repo = ConfigRepository()

    assert repo.base_path == tmp_path / "work" / ".visualize" / "configs"
    assert repo.index_path.is_file()
