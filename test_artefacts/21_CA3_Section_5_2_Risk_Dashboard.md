# CA3 Report — §5.2 Risk Dashboard evidence (paste-ready)

Drop the following paragraph, caption and figure into CA3 §5.2 (or wherever
Figure 5.7 is introduced). All references are internal to `test_artefacts/`.

---

## §5.2 Risk Dashboard (paragraph)

The Risk Intelligence Layer's inference output is surfaced end-to-end in a
dedicated **CAPRA — Risk Dashboard** (Grafana Cloud, UID
`capra-risk-register`). Whereas the per-layer dashboards used elsewhere in
this report measure *pipeline health* (Success %, latency, error counts),
this dashboard measures the *substantive risk output* — the LLM's identified
risk, the qualitative severity label, and the plain-English explanation for
each inference. Severity is derived deterministically from RIL's integer
`severity_score` (`0 → LOW`, `1 → MEDIUM`, `2 → HIGH`, `3+ → CRITICAL`) rather
than from the LLM's free-form `severity` string, which was found to default to
`"CRITICAL"` regardless of the numeric score (see `15_Layer_Report_RIL.md`
§12.4 for the full iteration history). Records marked `status="skipped"` and
records with `risk=""` — RIL heartbeats emitted when the LLM produced no risk
for a scenario — are filtered from every panel query so that headline counts
reflect substantive risks only, while the un-filtered stream remains
available in the "raw log stream" panel for pipeline-health review.

Figure 5.7 shows the dashboard over the reference evidence window **26 Jul
2026, 21:10–22:25 AEST** (75 min, immediately following the integer-severity
patch). In that window RIL produced **396 substantive risk records**
distributed **30% CRITICAL, 49% HIGH, 15% MEDIUM, 6% LOW**. Per-domain
attribution is not surfaced on the dashboard because the current CPL prompt
does not propagate a `domain` label to RIL; per-domain evidence is instead
obtained by pushing each domain's telemetry in a distinct time window and
filtering by absolute time range (§5.2.3).

## Figure 5.7 (caption)

> **Figure 5.7.** CAPRA — Risk Dashboard (Grafana UID `capra-risk-register`)
> rendered over the reference window 26 Jul 2026, 21:10–22:25 AEST. Top row:
> Critical/High/Medium/Low headline counts. Middle: severity donut and
> risks-over-time timeseries. Bottom: detail table with risk name, LLM
> explanation and message; raw JSON stream (not shown at this zoom level).
> Source: `dashboard_screenshots/RiskDashboard_20260731_101000.png`
> (1600 × 1200 PNG, rendered via Grafana Cloud Render API in kiosk mode).

## Figure reference (Markdown)

```markdown
![Figure 5.7 — CAPRA Risk Dashboard](dashboard_screenshots/RiskDashboard_20260731_101000.png)
```

## Optional supporting figures for §5.2 sub-sections

If §5.2.1 / §5.2.2 want a closer look, the panel-solo renders are stand-alone:

| Ref | Panel | File |
|---|---|---|
| Fig 5.7a | Severity donut | `dashboard_screenshots/RiskDashboard_panel5_donut_20260731_101000.png` |
| Fig 5.7b | Risks over time | `dashboard_screenshots/RiskDashboard_panel6_timeseries_20260731_101000.png` |
| Fig 5.7c | Detail table with `risk`, `explanation` | `dashboard_screenshots/RiskDashboard_panel7_detail_table_20260731_101000.png` |

## Data-lineage note (for a footnote or methods appendix)

Loki record shape after the patch:

```
labels: job=risk_intelligence_layer, service_name, severity,
        relative_severity, relative_likelihood
body:   message, risk_id, risk, severity, explanation, actor, target,
        confidence, status, simulation_run_id, scenario_id,
        totalCount, ingestCount, transformSuccess, errorCount,
        latencyMs, pipeline_latency_ms, severity_score, likelihood_score,
        risk_type_1, contributing_factor_1
```

`actor`, `target` and CPL `domain` are always `unknown` in the current build
(the LLM is not prompted with those fields) and `traceID` is not emitted;
these columns are therefore hidden from the dashboard table
(`15_Layer_Report_RIL.md` §12).
