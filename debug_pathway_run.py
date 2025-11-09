import json, os, sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

try:
    from pathway.llm_xpack_adapter import generate_attack_params_via_rag
    print("[+] pathway.llm_xpack_adapter loaded")
except Exception as e:
    print("[!] failed to import pathway.llm_xpack_adapter:", repr(e))
    raise

try:
    from attacker.attack_manager import run_all_attacks
    print("[+] attacker.attack_manager loaded")
except Exception as e:
    print("[!] failed to import attacker.attack_manager:", repr(e))
    raise

print("[*] Generating attacks via RAG+LLM...")
att = generate_attack_params_via_rag(run_tag="run01", top_k_context=5)
print("[*] Adapter returned (sanitized):")
print(json.dumps(att, indent=2))

if isinstance(att, dict) and "attacks" in att:
    attacks = att["attacks"]
else:
    attacks = att

print("[*] Running attacks on prototype metadata...")
out = run_all_attacks("results/run01/metadata_privacy.csv", "results/run01/ground_truth.csv", "results/run01/attacks/debug_prototype", attack_param_list=attacks)
print("[*] run_all_attacks returned summary:")
print(json.dumps(out, indent=2))