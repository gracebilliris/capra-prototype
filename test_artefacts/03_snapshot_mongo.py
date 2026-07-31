#!/usr/bin/env python3
"""
03_snapshot_mongo.py
Capture per-collection document counts across CAPRA MongoDB Atlas clusters.
Output: JSON snapshot at test_artefacts/snapshots/snapshot_<label>_<utc>.json

Fill in your own Atlas connection strings before running. Never commit real
credentials to the repository — use an environment variable or a local .env
file that is git-ignored.

Usage:
    export CAPRA_MONGO_A="mongodb+srv://<user>:<pw>@<clusterA>.mongodb.net/?appName=Cluster0"
    export CAPRA_MONGO_B="mongodb+srv://<user>:<pw>@<clusterB>.mongodb.net/?appName=Cluster0"
    python3 03_snapshot_mongo.py <label>
"""
import os, sys, json, datetime, pathlib
import certifi
from pymongo import MongoClient

CLUSTERS = [
    ("clusterA",
     os.environ.get("CAPRA_MONGO_A", "mongodb+srv://<user>:<pw>@<clusterA-host>.mongodb.net/?appName=Cluster0"),
     ["local_db", "telemetry_db", "risk_intelligence_db"]),
    ("clusterB",
     os.environ.get("CAPRA_MONGO_B", "mongodb+srv://<user>:<pw>@<clusterB-host>.mongodb.net/?appName=Cluster0"),
     ["feedback_and_refinement_db"]),
]

OUT_DIR = pathlib.Path(__file__).parent / "snapshots"
OUT_DIR.mkdir(exist_ok=True)


def snapshot():
    snap = {"taken_at_utc": datetime.datetime.utcnow().isoformat() + "Z", "clusters": {}}
    for cname, uri, dbs in CLUSTERS:
        client = MongoClient(uri, serverSelectionTimeoutMS=15000, tlsCAFile=certifi.where())
        snap["clusters"][cname] = {}
        for db_name in dbs:
            db = client[db_name]
            db_snap = {}
            for col in db.list_collection_names():
                db_snap[col] = db[col].count_documents({})
            snap["clusters"][cname][db_name] = db_snap
        client.close()
    return snap


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    snap = snapshot()
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"snapshot_{label}_{ts}.json"
    out.write_text(json.dumps(snap, indent=2))
    print(f"Snapshot written: {out}")
    for cluster, dbs in snap["clusters"].items():
        for db, cols in dbs.items():
            for col, cnt in cols.items():
                print(f"  {cluster}/{db}/{col}: {cnt}")


if __name__ == "__main__":
    main()
