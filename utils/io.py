
import os
import pandas as pd
import json

def ensure_dir(path):
    """Ensure directory exists."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def save_csv(path, list_of_dicts):
    """Save list of dicts to CSV file."""
    ensure_dir(os.path.dirname(path))
    df = pd.DataFrame(list_of_dicts)
    df.to_csv(path, index=False)

def save_json(path, obj):
    """Save a Python object to JSON file."""
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

def load_json(path):
    """Load JSON from a file."""
    with open(path, "r") as f:
        return json.load(f)
