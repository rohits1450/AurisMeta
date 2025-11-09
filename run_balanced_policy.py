import yaml
from privacy.layer import run_privacy_layer

with open("config/policy_balanced.yaml") as f:
    policy = yaml.safe_load(f)

run_privacy_layer(
    "results/run01/metadata_raw.csv",  
    "results/run01",                   
    policy,
    seed=123                           
)
