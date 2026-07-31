// CAPRA Risk Register — one-shot Grafana Cloud installer
//
// Usage:
//   1. Open https://gracebilliris.grafana.net in Chrome
//   2. Log in
//   3. Chrome → View → Developer → Developer Tools → Console
//   4. Paste this ENTIRE file. Press Enter.
//
// Uses your active session cookie — no token needed.
// Idempotent: running twice overwrites the same dashboard (uid=capra-risk-register).

(async () => {
  const DASH_URL = 'https://raw.githubusercontent.com/placeholder/dashboards/risk_register.json'; // fallback
  // Embedded dashboard JSON below (source of truth: ~/Projects/capra-prototype/dashboards/risk_register.json)

  const dashboard = {
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": {
          "type": "grafana",
          "uid": "-- Grafana --"
        },
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "description": "CAPRA \u2014 live register of privacy risks detected by the pipeline. Shows severity distribution, per-severity counts, and a filterable detail table with the explanation the LLM emitted alongside each risk. Powered by the same Loki log stream used by every other CAPRA dashboard (job=risk_intelligence_layer).",
  "editable": true,
  "graphTooltip": 0,
  "liveNow": false,
  "panels": [
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 0
      },
      "id": 20,
      "panels": [],
      "title": "Overview",
      "type": "row"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Number of Critical-severity risks in the selected time range.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "fixed",
            "fixedColor": "red"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 0,
        "y": 1
      },
      "id": 1,
      "options": {
        "colorMode": "background",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.4.0",
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum(count_over_time({job=\"risk_intelligence_layer\", severity=\"CRITICAL\"} | json | risk_id != \"\"[$__range]))",
          "queryType": "instant",
          "refId": "A"
        }
      ],
      "title": "Critical",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Number of High-severity risks in the selected time range.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "fixed",
            "fixedColor": "orange"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "orange",
                "value": null
              }
            ]
          },
          "unit": "short"
        }
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 6,
        "y": 1
      },
      "id": 2,
      "options": {
        "colorMode": "background",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum(count_over_time({job=\"risk_intelligence_layer\", severity=\"HIGH\"} | json | risk_id != \"\"[$__range]))",
          "queryType": "instant",
          "refId": "A"
        }
      ],
      "title": "High",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Number of Medium-severity risks in the selected time range.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "fixed",
            "fixedColor": "yellow"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "yellow",
                "value": null
              }
            ]
          },
          "unit": "short"
        }
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 12,
        "y": 1
      },
      "id": 3,
      "options": {
        "colorMode": "background",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum(count_over_time({job=\"risk_intelligence_layer\", severity=\"MEDIUM\"} | json | risk_id != \"\"[$__range]))",
          "queryType": "instant",
          "refId": "A"
        }
      ],
      "title": "Medium",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Number of Low-severity risks in the selected time range.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "fixed",
            "fixedColor": "green"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "short"
        }
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 18,
        "y": 1
      },
      "id": 4,
      "options": {
        "colorMode": "background",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum(count_over_time({job=\"risk_intelligence_layer\", severity=\"LOW\"} | json | risk_id != \"\"[$__range]))",
          "queryType": "instant",
          "refId": "A"
        }
      ],
      "title": "Low",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Distribution of risks by severity over the selected time range.",
      "fieldConfig": {
        "defaults": {
          "custom": {
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            }
          },
          "mappings": []
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "CRITICAL"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "red"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "HIGH"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "orange"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "MEDIUM"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "yellow"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "LOW"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "green"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 5
      },
      "id": 5,
      "options": {
        "displayLabels": [
          "percent",
          "name"
        ],
        "legend": {
          "displayMode": "list",
          "placement": "right",
          "showLegend": true,
          "values": [
            "value"
          ]
        },
        "pieType": "donut",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum by (severity) (count_over_time({job=\"risk_intelligence_layer\"} | json | risk_id != \"\"[$__range]))",
          "legendFormat": "{{severity}}",
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "Risks by Severity (Donut)",
      "type": "piechart"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Detected risks over time, grouped by severity.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": false,
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 60,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "normal"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "unit": "short"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "CRITICAL"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "red"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "HIGH"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "orange"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "MEDIUM"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "yellow"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "LOW"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "green"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 5
      },
      "id": 6,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "sum by (severity) (count_over_time({job=\"risk_intelligence_layer\"} | json | risk_id != \"\"[$__interval]))",
          "legendFormat": "{{severity}}",
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "Risks Detected Over Time",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Full risk detail. Filter with the dropdowns above. The 'explanation' column contains the LLM-generated rationale for each risk. Click any row to expand.",
      "fieldConfig": {
        "defaults": {
          "custom": {
            "align": "auto",
            "cellOptions": {
              "type": "auto",
              "wrapText": true
            },
            "filterable": true,
            "inspect": false
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          }
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "severity"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 100
              },
              {
                "id": "mappings",
                "value": [
                  {
                    "type": "value",
                    "options": {
                      "CRITICAL": {
                        "color": "red",
                        "index": 0,
                        "text": "CRITICAL"
                      }
                    }
                  },
                  {
                    "type": "value",
                    "options": {
                      "HIGH": {
                        "color": "orange",
                        "index": 1,
                        "text": "HIGH"
                      }
                    }
                  },
                  {
                    "type": "value",
                    "options": {
                      "MEDIUM": {
                        "color": "yellow",
                        "index": 2,
                        "text": "MEDIUM"
                      }
                    }
                  },
                  {
                    "type": "value",
                    "options": {
                      "LOW": {
                        "color": "green",
                        "index": 3,
                        "text": "LOW"
                      }
                    }
                  }
                ]
              },
              {
                "id": "custom.cellOptions",
                "value": {
                  "type": "color-background",
                  "mode": "gradient"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "Time"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 170
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "risk_id"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 130
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "domain"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 110
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "layer"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 90
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "actor"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 160
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "target"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 160
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "risk"
            },
            "properties": [
              {
                "id": "custom.width",
                "value": 220
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "explanation"
            },
            "properties": [
              {
                "id": "custom.cellOptions",
                "value": {
                  "type": "auto",
                  "wrapText": true
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 14,
        "w": 24,
        "x": 0,
        "y": 13
      },
      "id": 7,
      "options": {
        "cellHeight": "sm",
        "footer": {
          "countRows": false,
          "fields": "",
          "reducer": [
            "sum"
          ],
          "show": false
        },
        "showHeader": true,
        "sortBy": [
          {
            "desc": true,
            "displayName": "Time"
          }
        ]
      },
      "pluginVersion": "10.4.0",
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "{job=\"risk_intelligence_layer\", severity=~\"$severity\", domain=~\"$domain\", layer=~\"$layer\"} | json",
          "maxLines": 500,
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "Risk Register (detail)",
      "transformations": [
        {
          "id": "extractFields",
          "options": {
            "format": "auto",
            "keepTime": true,
            "replace": false,
            "source": "Line"
          }
        },
        {
          "id": "organize",
          "options": {
            "excludeByName": {
              "Line": true,
              "id": true,
              "labels": true,
              "labelTypes": true,
              "tsNs": true
            },
            "indexByName": {
              "Time": 0,
              "severity": 1,
              "domain": 2,
              "layer": 3,
              "risk_id": 4,
              "risk": 5,
              "actor": 6,
              "target": 7,
              "explanation": 8
            },
            "renameByName": {
              "Time": "Time",
              "severity": "severity",
              "domain": "domain",
              "layer": "layer",
              "risk_id": "risk_id",
              "risk": "risk",
              "actor": "actor",
              "target": "target",
              "explanation": "explanation"
            }
          }
        }
      ],
      "type": "table"
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "grafanacloud-logs"
      },
      "description": "Raw JSON stream for the risk register. Useful when triaging a specific event.",
      "gridPos": {
        "h": 10,
        "w": 24,
        "x": 0,
        "y": 27
      },
      "id": 8,
      "options": {
        "dedupStrategy": "none",
        "enableLogDetails": true,
        "prettifyLogMessage": true,
        "showCommonLabels": false,
        "showLabels": false,
        "showTime": true,
        "sortOrder": "Descending",
        "wrapLogMessage": true
      },
      "targets": [
        {
          "datasource": {
            "type": "loki",
            "uid": "grafanacloud-logs"
          },
          "expr": "{job=\"risk_intelligence_layer\", severity=~\"$severity\", domain=~\"$domain\", layer=~\"$layer\"} | json | risk_id != \"\"",
          "maxLines": 200,
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "Risk Register (raw log stream)",
      "type": "logs"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "tags": [
    "capra",
    "risk",
    "privacy"
  ],
  "templating": {
    "list": [
      {
        "current": {
          "selected": false,
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "loki",
          "uid": "grafanacloud-logs"
        },
        "definition": "",
        "hide": 0,
        "includeAll": true,
        "label": "Severity",
        "multi": true,
        "name": "severity",
        "options": [],
        "query": {
          "label": "severity",
          "refId": "LokiVariableQueryEditor-VariableQuery",
          "stream": "{job=\"risk_intelligence_layer\"}",
          "type": 1
        },
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      },
      {
        "current": {
          "selected": false,
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "loki",
          "uid": "grafanacloud-logs"
        },
        "definition": "",
        "hide": 0,
        "includeAll": true,
        "label": "Domain",
        "multi": true,
        "name": "domain",
        "options": [],
        "query": {
          "label": "domain",
          "refId": "LokiVariableQueryEditor-VariableQuery",
          "stream": "{job=\"risk_intelligence_layer\"}",
          "type": 1
        },
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      },
      {
        "current": {
          "selected": false,
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "loki",
          "uid": "grafanacloud-logs"
        },
        "definition": "",
        "hide": 0,
        "includeAll": true,
        "label": "Layer",
        "multi": true,
        "name": "layer",
        "options": [],
        "query": {
          "label": "layer",
          "refId": "LokiVariableQueryEditor-VariableQuery",
          "stream": "{job=\"risk_intelligence_layer\"}",
          "type": 1
        },
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      }
    ]
  },
  "time": {
    "from": "now-24h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "Australia/Sydney",
  "title": "CAPRA \u2014 Risk Register",
  "uid": "capra-risk-register",
  "version": 1,
  "weekStart": ""
};

  // Fetch Loki datasource UID (needed to bind panels)
  const dsResp = await fetch('/api/datasources', { credentials: 'include' });
  if (!dsResp.ok) {
    console.error('Failed to list datasources', dsResp.status, await dsResp.text());
    return;
  }
  const datasources = await dsResp.json();
  const loki = datasources.find(d => d.type === 'loki');
  if (!loki) { console.error('No Loki datasource in this Grafana. Aborting.'); return; }
  console.log('Using Loki datasource:', loki.name, 'uid=', loki.uid);

  // Replace every "${DS_LOKI}" or placeholder datasource with real uid
  const patched = JSON.parse(JSON.stringify(dashboard).replace(/\$\{DS_LOKI\}/g, loki.uid));
  // Also stamp uid so overwrite works
  patched.uid = 'capra-risk-register';
  // Grafana wants panel-level ds.uid too — walk panels
  function fix(o) {
    if (Array.isArray(o)) return o.forEach(fix);
    if (o && typeof o === 'object') {
      if (o.datasource && typeof o.datasource === 'object' && o.datasource.type === 'loki') {
        o.datasource.uid = loki.uid;
      }
      Object.values(o).forEach(fix);
    }
  }
  fix(patched);

  const resp = await fetch('/api/dashboards/db', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dashboard: patched, overwrite: true, message: 'CAPRA Risk Register auto-install' })
  });
  const body = await resp.json();
  if (!resp.ok) { console.error('Install failed', resp.status, body); return; }
  console.log('✅ Installed. Open:', location.origin + body.url);
})();
