# CAPRA — Risk Register dashboard

A Grafana dashboard that surfaces every privacy risk emitted by the CAPRA
pipeline: the severity mix at a glance, the trend over time, and a filterable
detail table showing the actor, target, and the LLM's explanation for each
risk.

The dashboard reads from Grafana Cloud Loki (no separate risk database
required). The pipeline pushes one log line per risk, and Grafana unpacks the
JSON body at query time.

## Files

| File | Purpose |
|---|---|
| `dashboards/risk_register.json` | Importable Grafana dashboard JSON. |
| `n8n_snippets/format_risk_for_grafana.js` | n8n Code node that wraps a risk record into the Loki push shape. |

## 1. Emit risks from n8n

Add two nodes on the success path immediately after whichever node produces the
final risk record. In practice this is the Evaluation & Refinement Layer's
`refined_risk` writer (post-approval), and optionally the Risk Intelligence
Layer's `risk_inference` writer if you also want unrefined risks in the ledger.

1. **Code node** — name: `Format Risk for Grafana`, mode: *Run Once For Each Item*.
   Paste the contents of `n8n_snippets/format_risk_for_grafana.js`.

2. **HTTP Request node** — name: `Push Risk to Loki`.
   * Method: `POST`
   * URL: `https://logs-prod-026.grafana.net/loki/api/v1/push`
   * Authentication: *Predefined Credential Type* → *Basic Auth* → `Grafana Credentials`
   * Send Body: on, Body Content Type: `JSON`, Specify Body: *Using JSON*
   * JSON: `{{ $json }}`
   * Expected success: `204 No Content`.

The upstream node's `$json` should include (all optional, but the richer the
better): `risk_id`, `risk`, `severity`, `explanation`, `actor`, `target`,
`domain`, `layer`, `confidence`, `task_id`.

### Label design (important)

Only four low-cardinality fields are used as Loki *labels*: `job`, `severity`,
`domain`, `layer`. Every other field (`risk_id`, `risk`, `explanation`,
`actor`, `target`, `confidence`, `task_id`, `ts`) is inside the JSON *body* of
the log line. This keeps active-stream count bounded and stays well under the
10 000-stream Grafana Cloud cap. The dashboard pulls the body fields out with
`| json` at query time.

## 2. Import the dashboard

1. Grafana → Dashboards → *New* → *Import*.
2. Upload `dashboards/risk_register.json` (or paste the JSON).
3. When prompted, map the Loki datasource to your Grafana Cloud Loki
   (`grafanacloud-logs`).
4. Set the time range to the window in which you'll trigger the workflow
   (default is `now-24h`).

## 3. What the dashboard shows

* **Four Stat panels** — count of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` risks in
  the selected range, colour-coded.
* **Donut** — proportion of risks by severity.
* **Timeseries** — risks detected over time, stacked by severity.
* **Risk Register (detail)** — a filterable table (severity / domain / layer
  dropdowns) with the full risk record, including the LLM `explanation`
  column. Severity cell is coloured to match.
* **Risk Register (raw log stream)** — pretty-printed JSON stream for
  triage / audit.

## 4. Verifying end to end

1. Import the dashboard.
2. Trigger the CAPRA workflow with a sample telemetry event that is known to
   produce at least one risk.
3. Refresh the dashboard: the Stat counters and the detail table should
   populate within a few seconds.

If nothing appears, run this ad-hoc query in *Explore* to confirm the push
side is working:

```logql
{job="risk_register"}
```

## 5. Where this appears in the report

Once the dashboard is verified against real data, capture a screenshot for
Section 5.2.2 of the CA3 report (append as Figure 5.7 — "Risk Register
observability view"). The caption should describe it as an *observability
data source* rather than by product name.
