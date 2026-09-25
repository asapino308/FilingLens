from pathlib import Path

from filinglens.desktop import runtime


def test_packaged_first_launch_does_not_import_private_source_data(monkeypatch, tmp_path: Path):
    legacy = tmp_path / "Documents" / "FilingLens"
    (legacy / "data" / "cache").mkdir(parents=True)
    (legacy / ".env").write_text("SEC_USER_AGENT=FilingLens owner@example.com\nOPENAI_API_KEY=private\n")
    (legacy / "data" / "cache" / "filing.bin").write_bytes(b"private research")
    support = tmp_path / "support"
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(runtime, "app_data_dir", lambda: support)

    environment = runtime.prepare_desktop_environment()

    assert environment == support / ".env"
    assert not environment.exists()
    assert list((support / "cache").iterdir()) == []
    assert support.stat().st_mode & 0o777 == 0o700
    assert (support / "cache").stat().st_mode & 0o777 == 0o700
