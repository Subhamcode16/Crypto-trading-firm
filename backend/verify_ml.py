"""Quick ML pipeline verification - outputs to ml_verify_results.txt"""
import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.disable(logging.CRITICAL)

from src.ml.feature_builder import FeatureBuilder
from src.ml.trainer import MLTrainer

DATA_DIR = os.path.join(os.path.dirname(__file__), 'src', 'ml', 'data')
output_lines = []

def check(name, condition):
    status = "PASS" if condition else "FAIL"
    output_lines.append(f"[{status}] {name}")

# 1. Feature builder embeds _trade_id
builder = FeatureBuilder()
features = builder.build(
    token_address="So11111111111111111111111111111111111111112",
    agent_1_data={"score": 7.0, "source": "dexscreener"},
    agent_2_data={"score": 8.0, "status": "CLEARED"},
    trade_id="test_pipeline_001"
)
check("_trade_id embedded in features", features.get("_trade_id") == "test_pipeline_001")

# 2. Save feature vector
os.makedirs(DATA_DIR, exist_ok=True)
fp = os.path.join(DATA_DIR, "features_test_pipeline_001.json")
clean = {k: v for k, v in features.items() if isinstance(v, (int, float, str))}
with open(fp, "w") as f:
    json.dump(clean, f, indent=2)
check("Feature file saved to ml/data/", os.path.exists(fp))

# 3. Save outcome
trainer = MLTrainer()
trainer.save_outcome("test_pipeline_001", 75.0, 1.50)
op = os.path.join(DATA_DIR, "outcome_test_pipeline_001.json")
check("Outcome file saved to ml/data/", os.path.exists(op))

# 4. Trainer matches features to outcomes
outcomes_list = [{"trade_id": "test_pipeline_001", "price_change_pct": 75.0}]
loaded_f, loaded_l, loaded_i = trainer._load_training_data(outcomes_list)
check("Trainer matched features to outcomes", len(loaded_f) >= 1)
if loaded_l:
    check("Label is correct (pump=1 for 75%)", loaded_l[0] == 1)

# 5. collect_outcomes_from_disk
collected = trainer.collect_outcomes_from_disk()
check("collect_outcomes_from_disk finds files", len(collected) >= 1)

# 6. retrain_from_disk (should skip - not enough data)
report = trainer.retrain_from_disk()
check("retrain_from_disk correctly skips (need 30+)", report.get("status") == "skipped")

# Cleanup
for f in [fp, op]:
    if os.path.exists(f):
        os.remove(f)
check("Test files cleaned up", not os.path.exists(fp) and not os.path.exists(op))

# Write results
results_path = os.path.join(os.path.dirname(__file__), "ml_verify_results.txt")
with open(results_path, "w", encoding="utf-8") as f:
    for line in output_lines:
        f.write(line + "\n")
    passed = sum(1 for l in output_lines if "[PASS]" in l)
    total = len(output_lines)
    f.write(f"\nTotal: {passed}/{total} passed\n")
