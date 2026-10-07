"""Promotion Performance Attribution - the method as version-controlled code.

Public entry points:
    load_dataset, load_config, attribute_promo, attribute_all, fingerprint,
    recovery_report, reproducibility_report
"""
from .data import load_dataset, load_ground_truth
from .engine import attribute_all, attribute_promo, config_hash, fingerprint, load_config, merge_config
from .validation import recovery_report, reproducibility_report

__all__ = ["load_dataset", "load_ground_truth", "attribute_all", "attribute_promo", "config_hash",
           "fingerprint", "load_config", "merge_config", "recovery_report", "reproducibility_report"]
