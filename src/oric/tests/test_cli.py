from __future__ import annotations

from oric.cli import main_smoke, main_version, run_packaged_smoke


def test_packaged_smoke_returns_stable_shape():
    result = run_packaged_smoke()
    assert result["ok"] is True
    assert result["package"] == "oric"
    assert result["n_points"] == 6
    assert result["sigma_sum"] >= 0.0
    assert "threshold_improvement" in result


def test_cli_smoke_json(capsys):
    assert main_smoke(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"ok": true' in out
    assert '"package": "oric"' in out


def test_cli_version(capsys):
    assert main_version([]) == 0
    assert capsys.readouterr().out.strip()
