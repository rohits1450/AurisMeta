import pandas as pd
df = pd.read_csv("results/run01/metadata_privacy.csv")
print("Total events:", len(df))
print("Padded_size unique:", sorted(df["padded_size"].unique()))
print(df["padded_size"].value_counts().to_dict())
df["latency"] = df["delivered_timestamp"] - df["timestamp"]
print("Latency stats:", df["latency"].describe().to_dict())
print("\nSample timestamps (first 20):")
print(df.sort_values("delivered_timestamp").head(20)[["msg_id","sender","recipient","timestamp","delivered_timestamp","padded_size","is_dummy"]].to_string(index=False))
