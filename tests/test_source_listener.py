from pathlib import Path
import tomllib


def test_supported_source_launch_is_local_only():
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / ".streamlit/config.toml").read_text())
    assert config["server"]["address"] == "127.0.0.1"
    launcher = (root / "Launch FilingLens.command").read_text()
    assert "streamlit run app.py --server.address=127.0.0.1" in launcher
