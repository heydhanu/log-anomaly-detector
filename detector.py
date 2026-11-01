import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest

random.seed(42); np.random.seed(42)
start = pd.Timestamp("2026-11-01 08:00")
users = ["alice", "bob", "carol", "dave", "eve"]

# 1. Generate normal logs
rows = []
for i in range(2000):
    rows.append({
        "time": start + pd.Timedelta(seconds=i * 20 + random.randint(0, 15)),
        "user": random.choice(users),
        "event": random.choices(["login_ok", "login_fail"], [0.93, 0.07])[0],
        "bytes": int(np.random.normal(5000, 1500)),
    })

# 2. Inject attacks
atk = start + pd.Timedelta(minutes=300)          # brute-force burst
for i in range(40):
    rows.append({"time": atk + pd.Timedelta(seconds=i * 2), "user": "admin",
                 "event": "login_fail", "bytes": int(np.random.normal(500, 100))})
for i in range(5):                                # data exfiltration
    rows.append({"time": start + pd.Timedelta(minutes=500 + i), "user": "bob",
                 "event": "login_ok", "bytes": int(np.random.normal(90000, 5000))})

df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
df.to_csv("logs.csv", index=False)

# 3. Per-minute features
df["minute"] = df["time"].dt.floor("min")
agg = df.groupby("minute").agg(
    events=("event", "size"),
    fails=("event", lambda s: (s == "login_fail").sum()),
    bytes=("bytes", "sum"),
).reset_index()

# 4. Detection: Isolation Forest + rule
model = IsolationForest(contamination=0.02, random_state=42)
agg["ml_flag"] = model.fit_predict(agg[["events", "fails", "bytes"]]) == -1
agg["rule_flag"] = agg["fails"] > 5
agg["anomaly"] = agg["ml_flag"] | agg["rule_flag"]

print(agg[agg["anomaly"]][["minute", "events", "fails", "bytes", "ml_flag", "rule_flag"]])

# 5. Plot
fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
for a, col, title in zip(ax, ["fails", "bytes"], ["Failed logins per minute", "Bytes transferred per minute"]):
    a.plot(agg["minute"], agg[col], lw=1, label="normal")
    flagged = agg[agg["anomaly"]]
    a.scatter(flagged["minute"], flagged[col], color="red", zorder=3, label="flagged")
    a.set_title(title); a.legend()
plt.tight_layout()
plt.savefig("anomalies.png", dpi=150)