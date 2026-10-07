"""Same data + same method version => byte-identical results."""
import hashlib
import json
import sys
from pathlib import Path

from attribution import attribute_all, attribute_promo, fingerprint, load_dataset, merge_config
from attribution.data import DEFAULT_DATA_DIR

ROOT = Path(__file__).resolve().parents[1]


def test_two_runs_identical(ds, cfg):
    assert fingerprint(attribute_all(ds, cfg)) == fingerprint(attribute_all(ds, cfg))


def test_fresh_load_identical(ds, cfg):
    first = fingerprint(attribute_all(ds, cfg))
    load_dataset.cache_clear()
    again = fingerprint(attribute_all(load_dataset(), cfg))
    assert first == again


def test_result_independent_of_run_order(ds, cfg):
    alone = attribute_promo(ds, "P07", cfg)
    in_batch = {r["promo_id"]: r for r in attribute_all(ds, cfg)}["P07"]
    assert fingerprint([alone]) == fingerprint([in_batch])


def test_seed_is_part_of_the_method(ds, cfg):
    other = merge_config(cfg, {"inference": {"seed": 1}})
    assert fingerprint(attribute_all(ds, cfg)) != fingerprint(attribute_all(ds, other))


def test_results_are_stamped(ds, cfg):
    r = attribute_promo(ds, "P01", cfg)
    assert r["method_version"] == cfg["method_version"]
    assert len(r["config_hash"]) == 12 and len(r["data_hash"]) == 16


def test_generator_reproduces_pinned_data(tmp_path):
    sys.path.insert(0, str(ROOT / "data_gen"))
    from generate_data import generate
    manifest = json.loads((DEFAULT_DATA_DIR / "data_manifest.json").read_text())
    generate(tmp_path, manifest["seed"])
    for f, sha in manifest["sha256"].items():
        assert hashlib.sha256((tmp_path / f).read_bytes()).hexdigest() == sha, f
