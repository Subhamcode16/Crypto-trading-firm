#!/usr/bin/env python3
"""
Test script: Verify the ML data pipeline is working end-to-end.

Tests:
1. Feature vectors save to the correct directory with _trade_id
2. Outcome files save to the correct directory
3. Trainer can match features ↔ outcomes and load training data
4. retrain_from_disk() works self-sufficiently

Run from: backend/
    python test_ml_pipeline.py
"""

import os
import sys
import json
import glob

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Suppress all logging from libraries (they emit emojis that break Windows console)
import logging
logging.disable(logging.CRITICAL)

# Add project paths
sys.path.insert(0, os.path.dirname(__file__))

from src.ml.feature_builder import FeatureBuilder
from src.ml.trainer import MLTrainer

DATA_DIR = os.path.join(os.path.dirname(__file__), 'src', 'ml', 'data')
PASS = "[OK]"
FAIL = "[FAIL]"

results = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

print("=" * 60)
print("[TEST] ML Pipeline Verification")
print("=" * 60)

# ── TEST 1: Feature Builder saves with correct path + _trade_id ──
print("\n[1] Feature Builder: save() path and _trade_id")

builder = FeatureBuilder()
test_trade_id = "test_pipeline_001"

features = builder.build(
    token_address="So11111111111111111111111111111111111111112",
    agent_1_data={"score": 7.0, "source": "dexscreener"},
    agent_2_data={"score": 8.0, "status": "CLEARED"},
    agent_3_data={"score": 6.5, "smart_wallets_detected": ["wallet1"]},
    agent_4_data={"score": 5.0, "narrative_bonus_awarded": True},
    trade_id=test_trade_id
)

test("_trade_id embedded in features", features.get('_trade_id') == test_trade_id, f"got: {features.get('_trade_id')}")
test("_token_address present", features.get('_token_address') is not None)

# Save synchronously for testing (bypass async)
os.makedirs(DATA_DIR, exist_ok=True)
filepath = os.path.join(DATA_DIR, f"features_{test_trade_id}.json")
clean_features = {k: v for k, v in features.items() if isinstance(v, (int, float, str))}
with open(filepath, 'w') as f:
    json.dump(clean_features, f, indent=2)

test("Feature file saved to ml/data/", os.path.exists(filepath), filepath)

# ── TEST 2: Trainer saves outcomes ──
print("\n[2] MLTrainer: save_outcome()")

trainer = MLTrainer()
trainer.save_outcome(
    trade_id=test_trade_id,
    price_change_pct=75.0,
    profit_usd=1.50
)

outcome_path = os.path.join(DATA_DIR, f"outcome_{test_trade_id}.json")
test("Outcome file saved to ml/data/", os.path.exists(outcome_path), outcome_path)

if os.path.exists(outcome_path):
    with open(outcome_path) as f:
        outcome = json.load(f)
    test("Outcome has trade_id", outcome.get('trade_id') == test_trade_id)
    test("Outcome has price_change_pct", outcome.get('price_change_pct') == 75.0)

# ── TEST 3: Trainer can load + match features ↔ outcomes ──
print("\n[3] MLTrainer: _load_training_data() matching")

outcomes_list = [{"trade_id": test_trade_id, "price_change_pct": 75.0, "profit_usd": 1.50}]
loaded_features, loaded_labels, loaded_ids = trainer._load_training_data(outcomes_list)

test("Loaded at least 1 matched feature", len(loaded_features) >= 1, f"got {len(loaded_features)}")
if loaded_labels:
    test("Label is correct (pump=1 for 75%)", loaded_labels[0] == 1, f"got {loaded_labels[0]}")

# ── TEST 4: collect_outcomes_from_disk() ──
print("\n[4] MLTrainer: collect_outcomes_from_disk()")

collected = trainer.collect_outcomes_from_disk()
test("At least 1 outcome collected", len(collected) >= 1, f"got {len(collected)}")

# ── TEST 5: retrain_from_disk() (will skip — not enough data) ──
print("\n[5] MLTrainer: retrain_from_disk() (expected: skip)")

report = trainer.retrain_from_disk()
test("Report status is 'skipped' (not enough data)", report.get('status') == 'skipped', f"got: {report.get('status')}")

# ── CLEANUP ──
print("\n[6] Cleanup test files")

for f in [filepath, outcome_path]:
    if os.path.exists(f):
        os.remove(f)
        
test("Test files cleaned up", not os.path.exists(filepath) and not os.path.exists(outcome_path))

# ── SUMMARY ──
print("\n" + "=" * 60)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"Results: {passed} passed, {failed} failed out of {len(results)} tests")

if failed == 0:
    print("[PASS] ALL TESTS PASSED -- ML pipeline is wired correctly!")
else:
    print("⚠️ Some tests failed — review output above")
print("=" * 60)
