import yaml, json, os, subprocess, sys
from privacy.layer import run_privacy_layer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / "results" / "run01"
ATT_DIR = RUN_DIR / "attacks"
CONFIG_DIR = ROOT / "config"
os.makedirs(ATT_DIR, exist_ok=True)

def call(cmd):
    """Helper to run subprocess and print live output."""
    print(">>>", " ".join(cmd))
    r = subprocess.run(cmd, shell=False, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout)
    return r.returncode, r.stdout


def main():
    # Auto-detect tuned or temporary policy (for tuner)
    tune_tmp = CONFIG_DIR / "policy_tune_tmp.yaml"
    tuned = CONFIG_DIR / "policy_tuned.yaml"
    default = CONFIG_DIR / "policy_tight_noise.yaml"

    if tune_tmp.exists():
        policy_path = tune_tmp
        print(f"[i] Using tuned temp policy: {policy_path.name}")
    elif tuned.exists():
        policy_path = tuned
        print(f"[i] Using saved tuned policy: {policy_path.name}")
    elif default.exists():
        policy_path = default
        print(f"[i] Using default policy: {policy_path.name}")
    else:
        print("❌ No policy file found.")
        sys.exit(1)

    print("[1] Load policy and apply privacy layer")
    policy = yaml.safe_load(open(policy_path))
    run_privacy_layer(str(RUN_DIR / "metadata_raw.csv"), str(RUN_DIR), policy, seed=42)

    print("[2] Run baseline & prototype attackers (heuristics + ML)")
    call([sys.executable, "-m", "attacker.run_attacks", "--run", str(RUN_DIR), "--ground", str(RUN_DIR / "ground_truth.csv")])

    print("[3] Run ML cross-run realistic attacker")
    call([sys.executable, "-m", "attacker.ml_cross_eval"])

    # Collect results
    summary = {}
    comp = ATT_DIR / "comparison_summary.json"
    if comp.exists():
        summary["comparison"] = json.load(open(comp))
    ml_cross = ATT_DIR / "ml_cross_guesses.json"
    if ml_cross.exists():
        summary["ml_cross_guesses"] = str(ml_cross)
    stats = RUN_DIR / "privacy_stats.json"
    if stats.exists():
        summary["privacy_stats"] = json.load(open(stats))
    out = ATT_DIR / "experiment_summary.json"
    json.dump(summary, open(out, "w"), indent=2)
    print(f"[DONE] Summary saved to {out}")


if __name__ == "__main__":
    main()
