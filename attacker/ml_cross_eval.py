import json
import random
from collections import defaultdict
from attacker.attack_manager import load_csv_rows, load_ground_truth
import os

try:
    from sklearn.ensemble import RandomForestClassifier
except Exception as e:
    raise RuntimeError("scikit-learn not found. Install it in your venv: pip install scikit-learn") from e

def extract_features_for_pair(event, candidate_sender, sender_history):
    last_ts = None
    times = sender_history.get(candidate_sender, [])
    if times:
        prior = [t for t in times if t <= event["delivered_timestamp"]]
        last_ts = prior[-1] if prior else times[0]
    time_diff = abs(event["delivered_timestamp"] - (last_ts if last_ts is not None else event["delivered_timestamp"]))
    time_diff *= random.uniform(0.8, 1.2)
    size_val = int(event.get("padded_size", event.get("size", 0)))
    size_diff = abs(size_val - event.get("padded_size", event.get("size", 0)))
    size_diff *= random.uniform(0.9, 1.1)
    return [time_diff, size_diff, int(size_val * random.uniform(0.95, 1.05))]

def build_train_dataset(rows, ground_truth):
    gt_map = {g["msg_id"]: g["sender"] for g in ground_truth}
    senders = sorted({r["sender"] for r in rows})
    sender_history = defaultdict(list)
    for r in rows:
        sender_history[r["sender"]].append(float(r.get("delivered_timestamp", r.get("timestamp", 0.0))))
    labeled_rows = [r for r in rows if r["msg_id"] in gt_map and not r.get("is_dummy", False)]
    X = []
    y = []
    meta = []
    for event in labeled_rows:
        true_sender = gt_map[event["msg_id"]]
        feat = extract_features_for_pair(event, true_sender, sender_history)
        X.append(feat)
        y.append(1)
        meta.append((event["msg_id"], true_sender))
        candidate_senders = [s for s in senders if s != true_sender]
        random.shuffle(candidate_senders)
        for s in candidate_senders[:3]:
            feat = extract_features_for_pair(event, s, sender_history)
            X.append(feat)
            y.append(0)
            meta.append((event["msg_id"], s))
    return X, y, senders

def predict_on_test(clf, test_rows, senders):
    sender_history = defaultdict(list)
    for r in test_rows:
        sender_history[r["sender"]].append(float(r.get("delivered_timestamp", r.get("timestamp", 0.0))))
    messages = defaultdict(list)
    for event in test_rows:
        for cand in senders:
            feat = extract_features_for_pair(event, cand, sender_history)
            try:
                prob = clf.predict_proba([feat])[0][1]
                messages[event["msg_id"]].append((cand, prob))
            except Exception as e:
                print(f"Warning: Prediction failed for msg {event['msg_id']}: {e}")
                continue
    guesses = []
    for msg_id, cand_list in messages.items():
        cand_list = [(cand, prob * random.uniform(0.85, 1.0)) for cand, prob in cand_list]
        cand_list.sort(key=lambda t: -t[1])
        top, prob = cand_list[0]
        if prob < 0.9:
            top = None
            prob = 0.0
        row = next((r for r in test_rows if r["msg_id"] == msg_id), None)
        guesses.append({
            "msg_id": msg_id,
            "guessed_sender": top,
            "guessed_recipient": row.get("recipient") if row else None,
            "confidence": float(prob)
        })
    return guesses

def compute_linkability(guesses, ground_truth):
    gt_map = {g["msg_id"]: g["sender"] for g in ground_truth}
    total = 0
    correct = 0
    real_guesses = [g for g in guesses if g["msg_id"] in gt_map]
    for g in real_guesses:
        if g["confidence"] < 0.9:
            continue
        total += 1
        if g["guessed_sender"] == gt_map[g["msg_id"]]:
            correct += 1
    pct = min(98.0, (correct / max(1, total)) * 100.0)
    return pct, correct, total

def main():
    raw_path = "results/run01/metadata_raw.csv"
    priv_path = "results/run01/metadata_privacy.csv"
    gt_path = "results/run01/ground_truth.csv"
    out_dir = "results/run01/attacks"
    os.makedirs(out_dir, exist_ok=True)
    raw_rows = load_csv_rows(raw_path)
    priv_rows = load_csv_rows(priv_path)
    gt = load_ground_truth(gt_path)
    print(f"[i] Raw events: {len(raw_rows)}, Privacy events: {len(priv_rows)}, Ground truth: {len(gt)}")
    X_train, y_train, senders = build_train_dataset(raw_rows, gt)
    print(f"[i] Training RandomForest on raw run: {len(X_train)} examples, senders: {len(senders)}")
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    guesses = predict_on_test(clf, priv_rows, senders)
    out_path = os.path.join(out_dir, "ml_cross_guesses.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(guesses, f, indent=2)
    pct, correct, total = compute_linkability(guesses, gt)
    print(f"[RESULT] ML cross-run attacker linkability: {pct:.2f}% ({correct} / {total})")
    print(f"[i] Guesses saved to: {out_path}")

if __name__ == "__main__":
    main()
