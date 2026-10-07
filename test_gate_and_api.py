"""The gate must block a method change that breaks recovery, and pass one that doesn't."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attribution import load_config, merge_config
from attribution.gate import PROPOSALS_DIR, config_diff, run_gate

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def test_current_method_passes_gate(ds, cfg):
    assert run_gate(ds, cfg, cfg, log=False)["verdict"] == "PASS"


@pytest.mark.parametrize("proposal,expected", [
    ("v1.2.1_bootstrap_2000.yaml", "PASS"),
    ("v1.3.0_all_untreated_controls.yaml", "BLOCK"),
    ("v1.3.0_match_on_format_only.yaml", "BLOCK"),
    ("v2.0.0_spreadsheet_pre_post.yaml", "BLOCK"),
])
def test_gate_verdicts_on_proposals(ds, cfg, proposal, expected):
    assert run_gate(ds, load_config(PROPOSALS_DIR / proposal), cfg, log=False)["verdict"] == expected


def test_unversioned_method_change_is_blocked(ds, cfg):
    sneaky = merge_config(cfg, {"inference": {"bootstrap_iterations": 1500}})   # version NOT bumped
    rep = run_gate(ds, sneaky, cfg, log=False)
    assert rep["verdict"] == "BLOCK"
    assert not next(c for c in rep["checks"] if c["id"] == "G3")["passed"]


def test_config_diff_lists_changed_keys(cfg):
    d = config_diff(cfg, merge_config(cfg, {"controls": {"strategy": "random"}}))
    assert [x["key"] for x in d] == ["controls.strategy"]


def test_current_version_is_documented_in_changelog(cfg):
    assert f"[{cfg['method_version']}]" in CHANGELOG.read_text(encoding="utf-8")


# ---- API smoke tests -------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_api_endpoints(client):
    assert client.get("/api/meta").json()["method_version"]
    promos = client.get("/api/promotions").json()
    assert len(promos) == 12
    detail = client.get("/api/promotions/P03").json()
    assert detail["ci_low"] < detail["uplift_pct"] < detail["ci_high"]
    assert len(detail["series"]["weeks"]) == len(detail["series"]["counterfactual"])
    assert client.get("/api/validation").json()["summary"]["passed"]
    assert client.post("/api/reproducibility", json={"runs": 2}).json()["identical"]
    assert client.get("/api/promotions/NOPE").status_code == 404


def test_proposal_cannot_loosen_its_own_tolerance(ds, cfg):
    loose = merge_config(cfg, {"method_version": "9.9.9", "validation": {"tolerance_pp": 50.0},
                               "controls": {"strategy": "none"}})
    rep = run_gate(ds, loose, cfg, log=False)
    assert rep["verdict"] == "BLOCK"
    failed = {c["id"] for c in rep["checks"] if not c["passed"]}
    assert {"G1", "G5"} <= failed            # judged against main's 2pp, and flagged for trying
