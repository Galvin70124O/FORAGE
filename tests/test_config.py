"""Security settings in .streamlit/config.toml that must not be lost in an edit."""

import tomllib
from pathlib import Path

CONFIG = tomllib.loads((Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text(encoding="utf-8"))


def test_errors_show_no_details_and_uploads_are_capped():
    assert CONFIG["client"]["showErrorDetails"] == "none"  # false still shows the traceback
    assert CONFIG["server"]["maxUploadSize"] == 2
