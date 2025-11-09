import json, os, collections
import pandas as pd

ATT_DIR = "results/run01/attacks/debug_prototype"
GT_PATH = "results/run01/ground_truth.csv"

def load_gt(path):
    df = pd.read_csv(path)
    return {r["msg_id"]: r["sender"] for r in df.to_dict("records")}

def load_guesses(path):
    return json.load(open(path, "r", encoding="utf-8"))

def evaluate(guesses_path, gt_map, top_n_examples=5):
    guesses = load_guesses(guesses_path)
    total = 0
    correct = 0
    per_sender = collections.Counter()
    for g in guesses:
        msg = g.get("msg_id")
        guessed = g.get("guessed_sender")
        true = gt_map.get(msg)
        if true is None:
            continue
        total += 1
        if guessed == true:
            correct += 1
            per_sender[true] += 1
    pct = 100.0 * correct / total if total else 0.0
    print(f"File: {os.path.basename(guesses_path)} -> {correct}/{total} correct = {pct:.2f}%")
    print("Top senders correct-count:", per_sender.most_common(10))
    print()

if __name__ == "__main__":
    gt = load_gt(GT_PATH)
    for fname in os.listdir(ATT_DIR):
        if fname.startswith("guesses_") and fname.endswith(".json"):
            evaluate(os.path.join(ATT_DIR, fname), gt)
