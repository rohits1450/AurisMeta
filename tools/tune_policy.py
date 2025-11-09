import itertools
import subprocess
import yaml
import json
import os
from pathlib import Path
import time

ROOT = Path.cwd()
CONFIG_DIR = ROOT / "config"
RESULTS_DIR = ROOT / "results" / "run01"
ATTACK_FILE = RESULTS_DIR / "attacks" / "comparison_summary.json"

dummy_probs = [0.25, 0.35, 0.45, 0.55]
pad_noise_fracs = [0.06, 0.10, 0.15, 0.20]
slot_intervals = [150, 250, 350, 500]
relay_probs = [0.10, 0.20, 0.30, 0.40]

BASE_POLICY_PATH = CONFIG_DIR / "policy_privacymax.yaml"

def run_command(cmd):
    """Run a shell command and stream its output."""
    print(f"[RUN] {cmd}")
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            print("  " + line.strip())
    process.wait()
    return process.returncode


def read_linkability():
    """Get the most recent ML linkability score from available results."""
    if ATTACK_FILE.exists():
        data = json.load(open(ATTACK_FILE))
        proto = data.get("prototype", {})
        if "ml_attacker" in proto:
            return proto["ml_attacker"].get("linkability_pct", 100.0)
    
    ml_path = RESULTS_DIR / "attacks" / "ml_cross_guesses.json"
    if ml_path.exists():
        with open(ml_path) as f:
            guesses = json.load(f)
            correct = sum(1 for g in guesses if g.get("correct", True))
            total = len(guesses)
            if total > 0:
                return 100.0 * correct / total
    
    print("[WARN] No valid ML linkability file found.")
    return 100.0



best_score = 999.0
best_policy = None
results = []

print("\n=== [AUTO-TUNE STARTED] ===\n")

for dummy, pad_noise, slot, relay in itertools.product(dummy_probs, pad_noise_fracs, slot_intervals, relay_probs):
    base = yaml.safe_load(open(BASE_POLICY_PATH))
    base.update({
        "dummy_prob": dummy,
        "pad_noise_frac": pad_noise,
        "slot_interval_ms": slot,
        "relay_prob": relay
    })

    tmp_path = CONFIG_DIR / "policy_tune_tmp.yaml"
    with open(tmp_path, "w") as f:
        yaml.dump(base, f)

    print(f"\n[TEST] dummy={dummy}, pad_noise={pad_noise}, slot={slot}, relay={relay}")
    print("------------------------------------------------")

    run_command(f"python run_experiment.py")
    run_command(f"python -m attacker.run_attacks --run {RESULTS_DIR} --ground {RESULTS_DIR}/ground_truth.csv")
    run_command(f"python -m attacker.ml_cross_eval")

    score = read_linkability()
    print(f"[RESULT] ML linkability: {score:.2f}%")

    results.append({
        "dummy_prob": dummy,
        "pad_noise_frac": pad_noise,
        "slot_interval_ms": slot,
        "relay_prob": relay,
        "linkability": score
    })

    if score < best_score:
        best_score = score
        best_policy = dict(base)
        print(f"[NEW BEST] linkability={score:.2f}%")

    time.sleep(1)  


best_path = CONFIG_DIR / "policy_tuned.yaml"
if best_policy:
    with open(best_path, "w") as f:
        yaml.dump(best_policy, f)
    print(f"\n✅ Best policy saved to: {best_path}")
    print(f"📉 Best linkability: {best_score:.2f}%")
else:
    print("❌ No best policy found.")


with open(CONFIG_DIR / "tuning_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\n=== [AUTO-TUNE COMPLETE] ===")
