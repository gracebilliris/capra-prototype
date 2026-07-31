#!/usr/bin/env python3
"""
04_collect_evidence.py
Compute deltas between two Mongo snapshots and sample 1 fresh doc per collection.
Also pulls recent n8n executions for the CAPRA workflow from the SQLite DB
(via `docker exec n8n` so we never touch the 3.9 GB file directly).

Usage:
    python3 04_collect_evidence.py <pre_label> <post_label>
    # e.g.  python3 04_collect_evidence.py pre_student_e2e post_student_e2e

Writes a Markdown evidence block to files/test_artefacts/evidence/<post_label>.md
and JSON deltas to evidence/<post_label>.json.
"""
import os, sys, json, pathlib, subprocess, datetime, glob
import certifi
from pymongo import MongoClient

WORKFLOW_ID = "XUSBdhyaqrZVIXqp"
HERE = pathlib.Path(__file__).parent
SNAP_DIR = HERE / "snapshots"
OUT_DIR = HERE / "evidence"
OUT_DIR.mkdir(exist_ok=True)

CLUSTERS = {
    "clusterA": os.environ.get("CAPRA_MONGO_A", "mongodb+srv://<user>:<pw>@<clusterA-host>.mongodb.net/?appName=Cluster0"),
    "clusterB": os.environ.get("CAPRA_MONGO_B", "mongodb+srv://<user>:<pw>@<clusterB-host>.mongodb.net/?appName=Cluster0"),
}


def latest_snapshot(label):
    matches = sorted(SNAP_DIR.glob(f"snapshot_{label}_*.json"))
    if not matches:
        raise SystemExit(f"No snapshot found for label '{label}'")
    return json.loads(matches[-1].read_text()), matches[-1].name


def compute_deltas(pre, post):
    deltas = {}
    for cluster, dbs in post["clusters"].items():
        deltas[cluster] = {}
        for db, cols in dbs.items():
            deltas[cluster][db] = {}
            for col, post_cnt in cols.items():
                pre_cnt = pre["clusters"].get(cluster, {}).get(db, {}).get(col, 0)
                deltas[cluster][db][col] = {"pre": pre_cnt, "post": post_cnt, "delta": post_cnt - pre_cnt}
    return deltas


def sample_recent_doc(cluster, db_name, col):
    uri = CLUSTERS[cluster]
    client = MongoClient(uri, serverSelectionTimeoutMS=15000, tlsCAFile=certifi.where())
    try:
        doc = client[db_name][col].find_one(sort=[("_id", -1)])
        if doc is not None:
            # _id -> str, all bson types -> json safe
            doc["_id"] = str(doc["_id"])
        return doc
    finally:
        client.close()


def fetch_n8n_executions(since_iso):
    """Pull recent executions of the target workflow from inside the n8n container."""
    js = f"""
    const sqlite3=require('/usr/local/lib/node_modules/n8n/node_modules/sqlite3');
    const db=new sqlite3.Database('/home/node/.n8n/database.sqlite',sqlite3.OPEN_READONLY);
    db.all(
      "SELECT id,workflowId,status,mode,startedAt,stoppedAt,finished FROM execution_entity WHERE workflowId=? AND (startedAt>=? OR createdAt>=?) ORDER BY id DESC LIMIT 200",
      ['{WORKFLOW_ID}', '{since_iso}', '{since_iso}'],
      (e,r)=>{{ if(e){{console.error(e);process.exit(1);}} console.log(JSON.stringify(r)); db.close(); }}
    );
    """
    out = subprocess.check_output(["docker", "exec", "n8n", "node", "-e", js], text=True)
    return json.loads(out.strip().splitlines()[-1])


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    pre_label, post_label = sys.argv[1], sys.argv[2]
    pre, pre_file = latest_snapshot(pre_label)
    post, post_file = latest_snapshot(post_label)

    deltas = compute_deltas(pre, post)

    # Sample one fresh doc per collection that grew
    samples = {}
    for cluster, dbs in deltas.items():
        for db, cols in dbs.items():
            for col, d in cols.items():
                if d["delta"] > 0:
                    try:
                        samples[f"{cluster}/{db}/{col}"] = sample_recent_doc(cluster, db, col)
                    except Exception as e:
                        samples[f"{cluster}/{db}/{col}"] = {"_error": str(e)}

    # n8n executions since pre snapshot
    since = pre["taken_at_utc"]
    try:
        execs = fetch_n8n_executions(since)
    except Exception as e:
        execs = [{"_error": str(e)}]

    out_json = OUT_DIR / f"{post_label}.json"
    out_json.write_text(json.dumps({
        "pre_snapshot": pre_file,
        "post_snapshot": post_file,
        "deltas": deltas,
        "samples": samples,
        "n8n_executions": execs,
    }, indent=2, default=str))

    # Markdown summary
    md = [f"# Evidence — {post_label}", "",
          f"- pre snapshot: `{pre_file}`",
          f"- post snapshot: `{post_file}`",
          f"- generated: `{datetime.datetime.utcnow().isoformat()}Z`",
          "", "## Collection deltas", "",
          "| Cluster | DB | Collection | Pre | Post | Δ |",
          "|---|---|---|---:|---:|---:|"]
    for cluster, dbs in deltas.items():
        for db, cols in dbs.items():
            for col, d in cols.items():
                md.append(f"| {cluster} | {db} | {col} | {d['pre']} | {d['post']} | {d['delta']:+d} |")
    md += ["", "## n8n executions since pre snapshot", "",
           "| id | mode | status | startedAt | stoppedAt | finished |",
           "|---|---|---|---|---|---|"]
    for e in execs:
        if "_error" in e:
            md.append(f"| ERROR | | {e['_error']} | | | |")
        else:
            md.append(f"| {e.get('id')} | {e.get('mode')} | {e.get('status')} | {e.get('startedAt')} | {e.get('stoppedAt')} | {e.get('finished')} |")
    md.append("")
    md.append(f"## Sample documents (one per grown collection)")
    for k, v in samples.items():
        md.append(f"\n### `{k}`\n```json\n{json.dumps(v, indent=2, default=str)[:4000]}\n```")
    (OUT_DIR / f"{post_label}.md").write_text("\n".join(md))
    print(f"Wrote {out_json}")
    print(f"Wrote {OUT_DIR / (post_label + '.md')}")


if __name__ == "__main__":
    main()
