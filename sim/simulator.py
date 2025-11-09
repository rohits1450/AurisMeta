import random
import numpy as np
import time
from utils.io import ensure_dir, save_csv, save_json
import os

def generate_events(num_users=10, duration_s=60, avg_msgs_per_min=10, seed=1):
    """
    Simulate message metadata between users.

    Returns:
      events: list of dicts with fields (msg_id, sender, recipient, timestamp, size)
      ground_truth: list of dicts mapping msg_id -> true sender, recipient
    """
    random.seed(seed)
    np.random.seed(seed + 42)

    users = [f"U{str(i).zfill(2)}" for i in range(1, num_users + 1)]
    total_msgs = int(num_users * (avg_msgs_per_min / 60.0) * duration_s)

    events = []
    ground_truth = []

    for i in range(total_msgs):
        sender = random.choice(users)
        recipient = random.choice([u for u in users if u != sender])
        timestamp = round(random.uniform(0, duration_s), 3)

        if random.random() < 0.7:
            size = int(np.random.normal(300, 80))
        else:
            size = int(np.random.normal(800, 200))
        size = max(50, size)  

        msg_id = f"m{str(i).zfill(5)}"
        events.append({
            "msg_id": msg_id,
            "sender": sender,
            "recipient": recipient,
            "timestamp": timestamp,
            "size": size
        })
        ground_truth.append({
            "msg_id": msg_id,
            "sender": sender,
            "recipient": recipient
        })

    events.sort(key=lambda e: e["timestamp"])
    return events, ground_truth


def simulate_run(
    outdir="results/run_sim",
    num_users=10,
    duration_s=60,
    avg_msgs_per_min=10,
    seed=1
):
    """Generate and save events + ground truth as CSV."""
    ensure_dir(outdir)
    events, gt = generate_events(
        num_users=num_users, duration_s=duration_s,
        avg_msgs_per_min=avg_msgs_per_min, seed=seed
    )

    save_csv(os.path.join(outdir, "metadata_raw.csv"), events)
    save_csv(os.path.join(outdir, "ground_truth.csv"), gt)

    summary = {
        "num_users": num_users,
        "duration_s": duration_s,
        "total_msgs": len(events),
        "avg_msgs_per_min": avg_msgs_per_min,
        "seed": seed
    }
    save_json(os.path.join(outdir, "summary.json"), summary)
    print(f"[✔] Simulation complete → {len(events)} messages generated.")
    print(f"Saved to: {outdir}")
    return summary
