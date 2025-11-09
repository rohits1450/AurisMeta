"""
RAG + LLM adapter: reads latest privacy stats + recent privacy events,
updates a local RAG index, retrieves context snippets, asks LLM for attack params,
parses & clamps the LLM JSON, saves raw + sanitized outputs, and returns sanitized attacks.

Usage:
  from pathway.llm_xpack_adapter import generate_attack_params_via_rag
  attacks = generate_attack_params_via_rag(run_tag="run01", top_k_context=5)
"""

import os
import json
import time
import pandas as pd
from pathlib import Path
from utils.io import ensure_dir, save_json, load_json
from llm.llm_client import ask_llm
from pathway.rag_index import SimpleRAGIndex

RESP_DIR = "llm/responses"
ensure_dir(RESP_DIR)

RAG = SimpleRAGIndex()


def _read_privacy_stats(stats_path):
    if not os.path.exists(stats_path):
        return {}
    try:
        return load_json(stats_path)
    except Exception:
        return {}


def _read_recent_privacy_events(csv_path, max_rows=200):
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    if "delivered_timestamp" in df.columns:
        df = df.sort_values("delivered_timestamp", ascending=False).head(max_rows)
    else:
        df = df.sort_values("timestamp", ascending=False).head(max_rows)
    rows = []
    for _, r in df.iterrows():
        padded = int(r.get("padded_size", r.get("size", 0)))
        delivered = float(r.get("delivered_timestamp", r.get("timestamp", 0)))
        rows.append({
            "id": f"e_{r['msg_id']}",
            "text": f"msg {r['msg_id']} from {r['sender']} to {r['recipient']} padded={padded} delivered={delivered:.3f} dummy={bool(r.get('is_dummy', False))}",
            "meta": {"sender": r["sender"], "recipient": r["recipient"], "padded": padded, "delivered": delivered}
        })
    return rows


def clamp_attack(a):
    t = a.get("type")
    p = a.get("params", {}) or {}
    safe = {}
    if t == "size_time":
        safe["timestamp_window_s"] = max(0.01, min(5.0, float(p.get("timestamp_window_s", 0.2))))
        safe["size_tolerance_bytes"] = int(max(0, min(2000, int(p.get("size_tolerance_bytes", 0)))))
    elif t == "batch_anchor":
        safe["recipient_batch_window_s"] = max(0.05, min(5.0, float(p.get("recipient_batch_window_s", 1.0))))
        safe["match_threshold"] = max(0.0, min(1.0, float(p.get("match_threshold", 0.6))))
    elif t == "frequency_intersection":
        windows = p.get("observation_windows", [1.0])
        try:
            windows = [max(0.01, min(10.0, float(w))) for w in windows]
        except Exception:
            windows = [1.0]
        safe["observation_windows"] = windows
        safe["min_common_frac"] = max(0.0, min(1.0, float(p.get("min_common_frac", 0.5))))
    elif t == "ml":
        safe["feature_set"] = p.get("feature_set", ["time_diff", "size_diff"])
        safe["min_examples"] = int(max(10, min(10000, int(p.get("min_examples", 50)))))
    else:
        safe = {}
    return {"name": a.get("name", "unnamed"), "type": t, "params": safe, "notes": a.get("notes", "")}


def generate_attack_params_via_rag(run_tag="run01", top_k_context=5, model="gpt-4o", temperature=0.0):
    """
    Main entrypoint.
    - reads results/{run_tag}/privacy_stats.json and metadata_privacy.csv
    - updates rag index
    - retrieves top_k_context passages
    - asks LLM for attack JSON
    - sanitizes/clamps numeric params and saves raw+sanitized files
    Returns: list of sanitized attack dicts (or {"attacks": [...]} )
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(RESP_DIR, f"attacker_raw_{run_tag}_{ts}.txt")
    sanit_path = os.path.join(RESP_DIR, f"attacker_sanitized_{run_tag}_{ts}.json")

    stats = _read_privacy_stats(f"results/{run_tag}/privacy_stats.json")
    events = _read_recent_privacy_events(f"results/{run_tag}/metadata_privacy.csv", max_rows=200)

    docs = []
    if stats:
        docs.append({"id": f"stats_{int(time.time())}", "text": f"privacy_stats: {json.dumps(stats)}", "meta": {"type": "stats"}})
    docs.extend(events)
    if docs:
        RAG.add_documents(docs)

    prompt_query = "generate attacker configs given the latest privacy metrics and recent message patterns"
    retrieved = RAG.retrieve(prompt_query, top_k=top_k_context)
    ctx_lines = []
    for r in retrieved:
        ctx_lines.append(f"- {r['text']} (score={r.get('score', 0.0):.3f})")
    context_blob = "\n".join(ctx_lines)

    prompt = f"""
You are a safe traffic-analysis researcher. Produce JSON only.
We have recent privacy stats and recent message snippets below. Using that context, propose up to 5 attacker specs.
Each attacker object must have:
 - name: short (no spaces)
 - type: one of ["size_time","batch_anchor","frequency_intersection","ml"]
 - params: numeric params only
 - notes: one short sentence
Return only JSON like: {{ "attacks": [ {{...}}, ... ] }}

Context:
{context_blob}
"""

    raw = ask_llm(prompt, model=model, temperature=temperature, max_tokens=800)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw)

    try:
        parsed = json.loads(raw)
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if not m:
            raise RuntimeError("LLM response could not be parsed as JSON. Raw saved at: " + raw_path)
        parsed = json.loads(m.group(0))

    attacks = parsed.get("attacks", []) if isinstance(parsed, dict) else []
    safe_attacks = []
    for a in attacks:
        if a.get("type") not in ["size_time", "batch_anchor", "frequency_intersection", "ml"]:
            continue
        safe_attacks.append(clamp_attack(a))

    save_json(sanit_path, {"attacks": safe_attacks})
    return {"attacks": safe_attacks}
