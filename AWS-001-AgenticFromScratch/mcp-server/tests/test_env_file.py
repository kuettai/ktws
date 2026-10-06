"""lib/env.py: .env loading for local runs."""
import os

from lib.env import load_env_file


def test_loads_values_and_keeps_existing_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\n\nLOCAL_ROLE=manager\nexport LOCAL_BRANCH_ID="12"\nOPS_API_KEY=from-file\nBROKEN LINE\n')
    monkeypatch.delenv("LOCAL_ROLE", raising=False)
    monkeypatch.delenv("LOCAL_BRANCH_ID", raising=False)
    monkeypatch.setenv("OPS_API_KEY", "from-shell")
    loaded = load_env_file(env)
    assert os.environ["LOCAL_ROLE"] == "manager"
    assert os.environ["LOCAL_BRANCH_ID"] == "12"          # quotes and "export " removed
    assert os.environ["OPS_API_KEY"] == "from-shell"      # real environment wins
    assert sorted(loaded) == ["LOCAL_BRANCH_ID", "LOCAL_ROLE"]
    for key in loaded:                                  # undo, so later tests are unaffected
        os.environ.pop(key)


def test_missing_file_is_fine(tmp_path):
    assert load_env_file(tmp_path / "nope.env") == []
