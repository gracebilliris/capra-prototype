#!/usr/bin/env python3
"""Summarise n8n execution outcomes from a copied SQLite database.

Reads the workflow execution table directly so that the reviewer route does not
need an n8n API key. Prints a JSON object with per-status counts and the nodes
that produced errors inside the observation window.

Usage:
    python3 reviewer/scripts/summarise_executions.py database.sqlite 2026-09-02T10:00:00Z
"""

from __future__ import annotations

import collections
import json
import sqlite3
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: summarise_executions.py DB [SINCE_ISO]"}))
        return 1

    db_path = sys.argv[1]
    since = sys.argv[2].replace("T", " ").replace("Z", "") if len(sys.argv) > 2 else None

    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = connection.execute(
            "SELECT status, startedAt, stoppedAt FROM execution_entity "
            "WHERE (? IS NULL OR startedAt >= ?)",
            (since, since),
        ).fetchall()
    except sqlite3.Error as error:
        print(json.dumps({"error": str(error)}))
        return 1

    statuses = collections.Counter(row[0] for row in rows)
    durations = [
        row for row in rows if row[1] and row[2]
    ]
    summary = {
        "total": len(rows),
        "by_status": dict(statuses),
        "window_start": since,
        "with_start_and_stop": len(durations),
    }
    print(json.dumps(summary))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
