import random
import os
import copy
import pandas as pd
from utils.io import ensure_dir, save_csv, save_json

def _parse_range(value):
    """Parse a [min, max] list, tuple, or 'min-max' string into (min, max)."""
    if value is None:
        return (0.05, 0.15)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (float(value[0]), float(value[1]))
    if isinstance(value, str) and "-" in value:
        parts = value.split("-")
        return (float(parts[0]), float(parts[1]))
    return (float(value), float(value))

def _pad_size(size, buckets):
    """Round message size up to the nearest bucket (e.g., 256, 512, 1024)."""
    for b in sorted(buckets):
        if size <= b:
            return int(b)
    return int(sorted(buckets)[-1])

def apply_privacy_policy(events, policy, seed=None):
    """Apply enhanced privacy protections"""
    if seed is not None:
        random.seed(seed)

    padding_buckets = list(policy.get("padding_buckets", [256, 512, 1024]))
    dummy_prob = float(policy.get("dummy_prob", 0.35))
    relay_prob = float(policy.get("relay_prob", 0.4))
    pad_noise_frac = float(policy.get("pad_noise_frac", 0.15))
    
    ml_noise_ts = float(policy.get("ml_noise_ts", 0.5))
    ml_noise_size = float(policy.get("ml_noise_size", 0.15))
    
    delivered = []
    for event in events:
        out = dict(event)
        
        base_ts = float(event["timestamp"])
        noise = random.uniform(-ml_noise_ts, ml_noise_ts)
        out["delivered_timestamp"] = base_ts + noise
        
        base_size = int(event.get("size", 0))
        size_noise = random.uniform(-ml_noise_size, ml_noise_size)
        padded = _pad_size(int(base_size * (1 + size_noise)), padding_buckets)
        out["padded_size"] = padded
        
        delivered.append(out)
        
        if random.random() < dummy_prob:
            dummy = dict(
                msg_id=f"dummy_{len(delivered):04d}",
                sender=event["sender"],
                recipient=random.choice([e["recipient"] for e in events]),
                timestamp=base_ts,
                delivered_timestamp=base_ts + random.uniform(0.1, 0.8),
                size=random.choice(padding_buckets),
                padded_size=random.choice(padding_buckets),
                is_dummy=True
            )
            delivered.append(dummy)
    
    return delivered


def run_privacy_layer(input_csv, output_dir, policy, seed=None):
    """
    Load raw metadata, apply the privacy layer, and save transformed results.
    """
    df = pd.read_csv(input_csv)
    events = df.to_dict(orient="records")
    transformed = apply_privacy_policy(events, policy, seed=seed)

    ensure_dir(output_dir)
    save_csv(os.path.join(output_dir, "metadata_privacy.csv"), transformed)

    stats = {
        "input_count": len(events),
        "output_count": len(transformed),
        "dummy_count": sum(1 for e in transformed if e.get("is_dummy")),
        "policy": policy
    }

    save_json(os.path.join(output_dir, "privacy_stats.json"), stats)
    print(f"[OK] Privacy layer applied. Output messages: {len(transformed)} (dummies: {stats['dummy_count']})")
    return transformed
