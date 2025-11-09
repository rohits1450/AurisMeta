"""
Run baseline and prototype attackers.
Usage:
  python attacker/run_attacks.py --run results/run01 --ground results/run01/ground_truth.csv [--use_pathway]
"""

import argparse
import os
import json
from attacker.attack_manager import run_all_attacks

try:
    from pathway.llm_xpack_adapter import generate_attack_params_via_rag
    PATHWAY_AVAILABLE = True
except Exception:
    PATHWAY_AVAILABLE = False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="results run folder (contains metadata_raw.csv and metadata_privacy.csv)")
    parser.add_argument("--ground", required=True, help="ground truth csv path")
    parser.add_argument("--use_pathway", action="store_true", help="use Pathway RAG+LLM for attack params")
    args = parser.parse_args()

    outdir = os.path.join(args.run, "attacks")
    os.makedirs(outdir, exist_ok=True)

    attack_param_list = None
    if args.use_pathway:
        if not PATHWAY_AVAILABLE:
            print("[!] pathway.llm_xpack_adapter not available. Make sure pathway/llm_xpack_adapter.py exists.")
        else:
            print("[*] Generating attack params from Pathway RAG+LLM...")
            attack_param_list = generate_attack_params_via_rag(run_tag=os.path.basename(args.run), top_k_context=5)
            if isinstance(attack_param_list, dict) and "attacks" in attack_param_list:
                attack_param_list = attack_param_list["attacks"]

    raw = os.path.join(args.run, "metadata_raw.csv")
    print("== Baseline attackers on raw metadata ==")
    baseline_out = run_all_attacks(raw, args.ground, os.path.join(outdir, "baseline"), attack_param_list)

    priv = os.path.join(args.run, "metadata_privacy.csv")
    print("\n== Prototype attackers on privacy metadata ==")
    proto_out = run_all_attacks(priv, args.ground, os.path.join(outdir, "prototype"), attack_param_list)

    summary = {"baseline": baseline_out, "prototype": proto_out}
    with open(os.path.join(outdir, "comparison_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n[+] Attack comparison saved to:", os.path.join(outdir, "comparison_summary.json"))

if __name__ == "__main__":
    main()