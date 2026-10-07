"""
Evaluation set for the Ask feature.

Each case fixes the question, the expected intent, which promotions must be
resolved, and facts the answer must contain. Every answer must pass the
number check (all numbers traceable to evidence), and the checker itself is
tested on deliberately wrong answers so it can't silently pass everything.
"""
import json

import pytest

from app.ask import AskEngine, pct, verify_numbers
from attribution import attribute_all, recovery_report
from attribution.engine import ROOT


@pytest.fixture(scope="module")
def engine(ds, cfg):
    results = attribute_all(ds, cfg)
    calib = ROOT / "reports" / "tolerance_calibration.json"
    return AskEngine(results, cfg, (ROOT / "METHOD.md").read_text(encoding="utf-8"),
                     validation=lambda: recovery_report(ds, cfg, results),
                     calibration=json.loads(calib.read_text()) if calib.exists() else None,
                     gate=lambda: [])


@pytest.fixture(scope="module")
def by_id(ds, cfg):
    return {r["promo_id"]: r for r in attribute_all(ds, cfg)}


CASES = [
    # question,                                         intent,       promo ids,       must contain
    ("How did P09 perform?",                            "promotion",  ["P09"],         ["significant uplift"]),
    ("how did pr-9 do",                                 "promotion",  ["P09"],         []),
    ("How did the chocolate promotion do?",             "promotion",  ["P09"],         []),
    ("How did the yogurt promotions do?",               "compare",    ["P07", "P10"],  []),
    ("Compare P03 and P12",                             "compare",    ["P03", "P12"],  []),
    ("Top 5 promotions by ROI in 2025",                 "ranking",    [],              ["Top 5", "ROI"]),
    ("Worst 3 promotions by uplift",                    "ranking",    [],              ["Bottom 3", "P08"]),
    ("Which mechanics work best on average?",           "group",      [],              ["BOGO", "TPR", "descriptive"]),
    ("Which promotions lost money?",                    "list",       [],              ["negative ROI"]),
    ("Which promotions had no effect?",                 "list",       [],              ["P06"]),
    ("How is the confidence interval computed?",        "method",     [],              ["bootstrap", "seeded"]),
    ("How is the baseline defined?",                    "method",     [],              ["holiday", "by rule"]),
    ("How are control stores chosen?",                  "method",     [],              ["format and region"]),
    ("Did the method recover the planted effects?",     "validation", [],              ["12 of 12"]),
    ("How did promotions do overall?",                  "portfolio",  [],              ["12 promotions"]),
    ("How did the Harbor promotion do?",                "not_found",  [],              ["couldn't find"]),
    ("asdf qwerty",                                     "fallback",   [],              []),
]


@pytest.mark.parametrize("question,intent,ids,contains", CASES)
def test_ask_eval_case(engine, question, intent, ids, contains):
    a = engine.answer(question)
    assert a["intent"] == intent, a["trace"]
    if ids:
        assert sorted(a["context"]["promo_ids"]) == ids
    for c in contains:
        assert c in a["answer"], f"{c!r} missing from: {a['answer']}"
    assert a["verification"]["all_verified"], [n for n in a["verification"]["numbers"] if not n["verified"]]
    if a["evidence"]:
        assert "[E1]" in a["answer"]          # answers cite their evidence


def test_answer_numbers_match_the_attribution(engine, by_id):
    a = engine.answer("How did P09 perform?")
    r = by_id["P09"]
    for v in (pct(r["uplift_pct"]), pct(r["ci_low"]), pct(r["ci_high"]), pct(r["roi"], 0)):
        assert v in a["answer"]


def test_follow_up_uses_conversation_context(engine, by_id):
    first = engine.answer("How did P09 perform?")
    a = engine.answer("What about its ROI?", first["context"])
    assert a["intent"] == "promotion" and a["context"]["promo_ids"] == ["P09"]
    assert pct(by_id["P09"]["roi"], 0) in a["answer"]
    b = engine.answer("How sure are we?", first["context"])
    assert b["intent"] == "promotion" and "confidence interval" in b["answer"]


def test_same_question_same_answer(engine):
    assert engine.answer("Top 5 promotions by ROI in 2025") == engine.answer("Top 5 promotions by ROI in 2025")


# ---- the checker must catch wrong numbers ------------------------------------------
EV = [{"id": "E1", "data": {"uplift_pct": 0.186, "roi": 0.53, "incremental_revenue": 39455.2, "start_week": "2025-12-01"}}]


@pytest.mark.parametrize("text,ok", [
    ("Uplift was +18.6% and ROI +53% [E1]", True),
    ("Revenue $39.5k from 2025-12-01 [E1]", True),
    ("Uplift was +21.4% [E1]", False),           # wrong number
    ("Revenue $52.0k [E1]", False),              # wrong money
    ("It started 2025-11-03 [E1]", False),       # wrong date
])
def test_number_checker(text, ok):
    assert verify_numbers(text, EV)["all_verified"] is ok
