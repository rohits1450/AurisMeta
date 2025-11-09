import os
import json
import random
from collections import defaultdict, Counter

import pandas as pd
from utils.io import ensure_dir, save_json, save_csv

def load_csv_rows(path):
    df = pd.read_csv(path)
    df = df.fillna({'padded_size': df.get('size')})
    rows = df.to_dict(orient="records")
    for r in rows:
        r["padded_size"] = int(r.get("padded_size", r.get("size", 0)))
        r["delivered_timestamp"] = float(r.get("delivered_timestamp", r.get("timestamp", 0)))
    return rows

def load_ground_truth(path):
    df = pd.read_csv(path)
    return df.to_dict(orient="records")

def attacker_size_time(rows, params):
    ts_win = float(params.get("timestamp_window_s", 0.2))
    size_tol = int(params.get("size_tolerance_bytes", 0))
    guesses = []
    for r in rows:
        candidates = []
        for cand in rows:
            if abs(cand["padded_size"] - r["padded_size"]) <= size_tol:
                if abs(cand["delivered_timestamp"] - r["delivered_timestamp"]) <= ts_win:
                    candidates.append(cand["sender"])
        guessed = None
        if candidates:
            guessed = sorted(Counter(candidates).items(), key=lambda x: (-x[1], x[0]))[0][0]
            confidence = min(0.95, 0.5 + 0.05 * len(candidates))
        else:
            confidence = 0.0
        guesses.append({"msg_id": r["msg_id"], "guessed_sender": guessed, "guessed_recipient": r.get("recipient"), "confidence": confidence})
    return guesses

def attacker_batch_anchor(rows, params):
    win = float(params.get("recipient_batch_window_s", 1.0))
    buckets = defaultdict(list)
    for r in rows:
        b = int(r["delivered_timestamp"] // win)
        buckets[(r["recipient"], b)].append(r)
    guesses = []
    for (rec, b), msgs in buckets.items():
        freq = Counter([m["sender"] for m in msgs])
        top_sender, top_count = freq.most_common(1)[0]
        for m in msgs:
            guesses.append({"msg_id": m["msg_id"], "guessed_sender": top_sender, "guessed_recipient": rec, "confidence": max(0.4, min(0.99, top_count / len(msgs)))})
    return guesses

def attacker_frequency_intersection(rows, params):
    counts = Counter((r["sender"], r["recipient"]) for r in rows)
    by_rec = defaultdict(list)
    for (s, r), c in counts.items():
        by_rec[r].append((s, c))
    guesses = []
    for m in rows:
        rec = m["recipient"]
        cand = by_rec.get(rec, [])
        if cand:
            top = max(cand, key=lambda x: x[1])[0]
            guesses.append({"msg_id": m["msg_id"], "guessed_sender": top, "guessed_recipient": rec, "confidence": 0.6})
        else:
            guesses.append({"msg_id": m["msg_id"], "guessed_sender": None, "guessed_recipient": rec, "confidence": 0.0})
    return guesses

def extract_features_for_pair(event, candidate_sender, sender_history):
    last_ts = None
    times = sender_history.get(candidate_sender, [])
    if times:
        prior = [t for t in times if t <= event["delivered_timestamp"]]
        last_ts = prior[-1] if prior else times[0]
    time_diff = abs(event["delivered_timestamp"] - (last_ts if last_ts is not None else event["delivered_timestamp"]))
    size_diff = abs(event["padded_size"] - event.get("padded_size", event.get("size", 0)))
    return {"time_diff": time_diff, "size_diff": size_diff, "padded_size": int(event["padded_size"])}

def build_ml_dataset(rows, ground_truth):
    gt_map = {g["msg_id"]: g["sender"] for g in ground_truth}
    senders = sorted({r["sender"] for r in rows})
    sender_history = defaultdict(list)
    for r in rows:
        sender_history[r["sender"]].append(r["delivered_timestamp"])
    X, y, meta = [], [], []
    K = 3
    for event in rows:
        true_sender = gt_map.get(event["msg_id"])
        if true_sender is None:
            continue
        feat = extract_features_for_pair(event, true_sender, sender_history)
        X.append([feat["time_diff"], feat["size_diff"], feat["padded_size"]])
        y.append(1)
        meta.append((event["msg_id"], true_sender))
        negs = [s for s in senders if s != true_sender]
        random.shuffle(negs)
        for s in negs[:K]:
            f = extract_features_for_pair(event, s, sender_history)
            X.append([f["time_diff"], f["size_diff"], f["padded_size"]])
            y.append(0)
            meta.append((event["msg_id"], s))
    return X, y, meta

def attacker_ml(rows, ground_truth, params):
    try:
        from sklearn.ensemble import RandomForestClassifier
    except Exception:
        return []
    X, y, meta = build_ml_dataset(rows, ground_truth)
    if len(set(y)) < 2:
        return []
    clf = RandomForestClassifier(n_estimators=50, random_state=42)
    clf.fit(X, y)
    messages = defaultdict(list)
    for (msg_id, cand), x in zip(meta, X):
        prob = float(clf.predict_proba([x])[0][1])
        messages[msg_id].append((cand, prob))
    guesses = []
    for msg_id, cand_list in messages.items():
        cand_list.sort(key=lambda t: -t[1])
        top, prob = cand_list[0]
        row = next((r for r in rows if r["msg_id"] == msg_id), None)
        guesses.append({"msg_id": msg_id, "guessed_sender": top, "guessed_recipient": row["recipient"] if row else None, "confidence": float(prob)})
    return guesses

def compute_linkability(guesses, ground_truth):
    gt_map = {g["msg_id"]: g["sender"] for g in ground_truth}
    total = 0
    correct = 0
    for g in guesses:
        msg = gt_map.get(g["msg_id"])
        if msg is None:
            continue
        total += 1
        if g.get("guessed_sender") == msg:
            correct += 1
    pct = (correct / total * 100.0) if total > 0 else 0.0
    return round(pct, 3)

def save_guesses(out_dir, attacker_name, guesses):
    ensure_dir(out_dir)
    path = os.path.join(out_dir, f"guesses_{attacker_name}.json")
    save_json(path, guesses)

def run_all_attacks(metadata_csv, ground_csv, out_dir, attack_param_list=None):
    rows = load_csv_rows(metadata_csv)
    ground = load_ground_truth(ground_csv)
    if not attack_param_list:
        attack_param_list = [
            {"name": "size_time_default", "type": "size_time", "params": {"timestamp_window_s": 0.2, "size_tolerance_bytes": 0}},
            {"name": "batch_anchor_default", "type": "batch_anchor", "params": {"recipient_batch_window_s": 1.0}},
            {"name": "freq_inter_default", "type": "frequency_intersection", "params": {}},
            {"name": "ml_attacker", "type": "ml", "params": {}}
        ]

    results = {}
    for atk in attack_param_list:
        name = atk.get("name")
        t = atk.get("type")
        params = atk.get("params", {})
        print(f"[+] Running attacker: {name} (type={t})")
        if t == "size_time":
            guesses = attacker_size_time(rows, params)
        elif t == "batch_anchor":
            guesses = attacker_batch_anchor(rows, params)
        elif t == "frequency_intersection":
            guesses = attacker_frequency_intersection(rows, params)
        elif t == "ml":
            guesses = attacker_ml(rows, ground, params)
        else:
            print(f"  -> Unknown attacker type: {t}, skipping")
            continue

        link = compute_linkability(guesses, ground)
        results[name] = {"linkability_pct": link, "num_guesses": len(guesses)}
        print(f"  -> linkability: {link}%")
        save_guesses(out_dir, name, guesses)

    ensure_dir(out_dir)
    save_json(os.path.join(out_dir, "attack_summary.json"), results)
    return results
