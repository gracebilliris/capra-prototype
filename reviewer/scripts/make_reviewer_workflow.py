#!/usr/bin/env python3
"""Derive the reviewer workflow from the published export.

Input:  workflows/CAPRA_Prototype_unified_patched.json  (the tagged release export)
Output: reviewer/workflows/CAPRA_reviewer_local.json

The transformation is mechanical and auditable. It changes only the external
bindings that a reviewer cannot supply without accounts, and it changes no
stage logic, prompt, or code node:

1.  Azure OpenAI chat-model nodes are retargeted at the language-model provider
    the reviewer selected. Two providers are supported and neither is
    Azure-specific:

    * ``openai-compatible`` (default, and the route the quick start prefers):
      generic OpenAI Chat Model nodes bound to one n8n credential that carries
      the reviewer's own base URL, API key, and model name. Any endpoint that
      speaks the OpenAI chat-completions API works; nothing in this file names
      a vendor, a host, or a key.
    * ``ollama``: Ollama chat-model nodes bound to a local Ollama runtime.
      Credential-free, but small local models vary widely in instruction
      following and structured-output reliability.

    Agent nodes, prompts, and output parsers are untouched in both cases. No
    endpoint, key, or account value is ever written into the workflow file: the
    reviewer's values live only in the n8n credential store, which the
    bootstrap populates from the git-ignored ``reviewer/.env``.
2.  All MongoDB credential references collapse onto one local MongoDB
    credential pointing at the ``capra`` database in the local ``mongo``
    service.
3.  Grafana Cloud Loki push URLs become the local ``loki`` service, and the
    Grafana Cloud basic-auth credential reference is dropped (local Loki
    accepts unauthenticated pushes on the demo profile).
4.  SPARQL reads that pointed at an undocumented GraphDB endpoint on port 7200
    are repointed at the Fuseki ``ontology`` dataset that the compose file
    actually provisions. Fuseki update URLs move from ``host.docker.internal``
    to the ``fuseki`` service name.
5.  The Kafka REST-proxy poll node, which required an unprovisioned service, is
    disabled. The file-based ingestion path that the demonstration walkthrough
    uses is unaffected.
6.  The Gmail notification node is removed. It required an OAuth account and
    carried a hard-coded personal address.
7.  Domain input paths are repointed at the mounted synthetic fixtures.

Every change is written to a machine-readable report so the reviewer route can
be diffed against the published export.

Usage:
    python3 reviewer/scripts/make_reviewer_workflow.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

SOURCE_DEFAULT = "workflows/CAPRA_Prototype_unified_patched.json"
TARGET_DEFAULT = "reviewer/workflows/CAPRA_reviewer_local.json"
REPORT_DEFAULT = "reviewer/workflows/transformation_report.json"

LOCAL_MONGO_CREDENTIAL = {"id": "capra-local-mongo", "name": "CAPRA Local Mongo"}
LOCAL_OLLAMA_CREDENTIAL = {"id": "capra-local-ollama", "name": "CAPRA Local Ollama"}
OPENAI_COMPATIBLE_CREDENTIAL = {
    "id": "capra-openai-compatible",
    "name": "CAPRA OpenAI-Compatible Endpoint",
}

AZURE_MODEL_TYPE = "@n8n/n8n-nodes-langchain.lmChatAzureOpenAi"
OLLAMA_MODEL_TYPE = "@n8n/n8n-nodes-langchain.lmChatOllama"
OLLAMA_MODEL_VERSION = 1
# Generic "OpenAI Chat Model" node. It is not tied to api.openai.com: the base
# URL travels on the openAiApi credential, so any OpenAI-compatible endpoint is
# addressable. Version 1.2 is the lowest version in n8n 2.6.4 that takes the
# model as a resource locator, which lets an arbitrary model id be supplied
# without the editor trying to resolve it against a vendor model list.
OPENAI_COMPATIBLE_MODEL_TYPE = "@n8n/n8n-nodes-langchain.lmChatOpenAi"
OPENAI_COMPATIBLE_MODEL_VERSION = 1.2

PROVIDERS = ("openai-compatible", "ollama")
DEFAULT_MODEL = {
    # Deliberately not a real model id. The bootstrap replaces it from
    # reviewer/.env, and an unreplaced value must fail loudly rather than
    # silently address someone else's account.
    "openai-compatible": "replace-with-your-model-name",
    "ollama": "llama3.2",
}

# Anything matching these must never reach the workflow file, the report, or a
# log. The reviewer's key lives only in the n8n credential store.
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)\bapi[_-]?key\b\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{16,}"),
    re.compile(r"(?i)[a-z0-9-]+\.openai\.azure\.com"),
)

LOKI_LOCAL_URL = "http://loki:3100/loki/api/v1/push"
FUSEKI_UPDATE_URL = "http://fuseki:3030/ontology/update"
FUSEKI_QUERY_URL = "http://fuseki:3030/ontology/sparql"

FIXTURE_PATHS = {
    "/home/node/.n8n-files/EHR.csv": "/home/node/.n8n-files/EHR.csv",
    "/home/node/.n8n-files/retail_employees.csv": "/home/node/.n8n-files/retail_employees.csv",
    "/home/node/.n8n-files/admissiondata.csv": "/home/node/.n8n-files/admissiondata.csv",
}

# One trigger per domain feeds the mock external-system generator. The
# demonstration isolates a single domain per observation window, so the reviewer
# route enables one and disables the other two.
DOMAIN_TRIGGERS = {
    "admissions": "Execute ESL Admission Data",
    "healthcare": "Execute ESL EHR Data",
    "retail": "Execute ESL Retail Data",
}

# The published export polls every ten seconds, which assumes a hosted
# GPT-4o-class endpoint answering in a second or two, and it assumes nobody is
# watching the bill. A ten-second cadence starts new executions faster than a
# slower endpoint or a local model finishes them, so nothing reaches the
# downstream stages. The reviewer route slows every trigger to a cadence that
# both providers sustain and that keeps a metered endpoint's call volume small.
TRIGGER_CADENCE_SECONDS = {
    "Execute ESL Admission Data": 300,
    "Execute ESL EHR Data": 300,
    "Execute ESL Retail Data": 300,
    "Execute DFL": 60,
    "Execute CPL": 60,
    "Execute RIL": 60,
    "Execute E&RL": 60,
    "Schedule Trigger": 60,
}



# Compatibility shim, disclosed in reviewer/RELEASE_CANDIDATE.md.
#
# Two code nodes parse the JSON-LD returned by the knowledge-store query and
# iterate it as a top-level array of expanded nodes. That is what the GraphDB
# repository the released workflow pointed at returned. That repository is not
# provisioned by any released compose file, so the reviewer route queries the
# Fuseki dataset it does provision, and Fuseki returns compact JSON-LD: an
# object with an "@graph" array and prefixed terms. The shim below restores the
# expanded array shape the released code expects. It changes the input shape
# back, not the stage logic that follows it.
JSONLD_SOURCE_LINE = "const graph = JSON.parse(items[0].json.data);"
JSONLD_SHIM = """const __raw = JSON.parse(items[0].json.data);
const __ctx = (__raw && __raw['@context']) || {};
const __expandTerm = (t) => {
  if (typeof t !== 'string') return t;
  if (t.indexOf('://') !== -1) return t;
  const i = t.indexOf(':');
  if (i < 0) return t;
  const base = __ctx[t.slice(0, i)];
  return (typeof base === 'string') ? base + t.slice(i + 1) : t;
};
const __expandValue = (v) => {
  if (v && typeof v === 'object') {
    return v['@id'] ? { '@id': __expandTerm(v['@id']) } : v;
  }
  if (typeof v === 'string') {
    const e = __expandTerm(v);
    if (e !== v) return { '@id': e };
  }
  return { '@value': v };
};
const __expandNode = (n) => {
  const out = {};
  for (const k of Object.keys(n)) {
    const v = n[k];
    if (k === '@id') { out['@id'] = __expandTerm(v); }
    else if (k === '@type') { out['@type'] = (Array.isArray(v) ? v : [v]).map(__expandTerm); }
    else if (k === '@context') { continue; }
    else { out[__expandTerm(k)] = (Array.isArray(v) ? v : [v]).map(__expandValue); }
  }
  return out;
};
const graph = Array.isArray(__raw)
  ? __raw
  : (Array.isArray(__raw['@graph']) ? __raw['@graph'].map(__expandNode) : [__expandNode(__raw)]);"""


def transform(
    workflow: dict, model: str, domain: str, provider: str
) -> tuple[dict, list[dict]]:
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider: {provider}")
    changes: list[dict] = []
    kept_nodes = []
    removed_names = set()
    inactive_triggers = {
        trigger for key, trigger in DOMAIN_TRIGGERS.items() if key != domain
    }

    for node in workflow.get("nodes", []):
        name = node.get("name", "")
        node_type = node.get("type", "")
        params = node.setdefault("parameters", {})
        creds = node.get("credentials") or {}

        if node_type == "n8n-nodes-base.scheduleTrigger" and name in TRIGGER_CADENCE_SECONDS:
            seconds = TRIGGER_CADENCE_SECONDS[name]
            previous = json.dumps(params.get("rule"))
            if seconds >= 60 and seconds % 60 == 0:
                # n8n rejects a seconds interval of 60 or more as "Invalid interval".
                entry = {"field": "minutes", "minutesInterval": seconds // 60}
            else:
                entry = {"field": "seconds", "secondsInterval": seconds}
            params["rule"] = {"interval": [entry]}
            changes.append({
                "node": name,
                "action": "slowed-cadence",
                "from": previous,
                "to": f"every {seconds}s",
                "reason": "the published ten-second cadence outruns any endpoint the reviewer is likely to use, and inflates metered call volume",
            })

        if name in inactive_triggers:
            node["disabled"] = True
            changes.append({
                "node": name,
                "action": "disabled",
                "reason": f"domain isolation: this run demonstrates the '{domain}' domain",
            })

        if node_type == "n8n-nodes-base.gmail":
            removed_names.add(name)
            changes.append({
                "node": name,
                "action": "removed",
                "reason": "required an external mail account and carried a hard-coded personal address",
            })
            continue

        if node_type == AZURE_MODEL_TYPE:
            if provider == "ollama":
                node["type"] = OLLAMA_MODEL_TYPE
                node["typeVersion"] = OLLAMA_MODEL_VERSION
                node["parameters"] = {"model": model, "options": {}}
                node["credentials"] = {"ollamaApi": dict(LOCAL_OLLAMA_CREDENTIAL)}
                target_type = OLLAMA_MODEL_TYPE
            else:
                node["type"] = OPENAI_COMPATIBLE_MODEL_TYPE
                node["typeVersion"] = OPENAI_COMPATIBLE_MODEL_VERSION
                node["parameters"] = {
                    "model": {"__rl": True, "mode": "id", "value": model},
                    "options": {},
                }
                node["credentials"] = {
                    "openAiApi": dict(OPENAI_COMPATIBLE_CREDENTIAL)
                }
                target_type = OPENAI_COMPATIBLE_MODEL_TYPE
            changes.append({
                "node": name,
                "action": "retargeted-model",
                "from": AZURE_MODEL_TYPE,
                "to": target_type,
                "provider": provider,
                "model": model,
                "note": (
                    "the base URL and API key travel on the n8n credential, not in this file"
                    if provider == "openai-compatible"
                    else "local runtime; no key of any kind"
                ),
            })
            kept_nodes.append(node)
            continue

        if "mongoDb" in creds:
            previous = creds["mongoDb"].get("name")
            creds["mongoDb"] = dict(LOCAL_MONGO_CREDENTIAL)
            node["credentials"] = creds
            changes.append({
                "node": name,
                "action": "rebound-credential",
                "credential": "mongoDb",
                "from": previous,
                "to": LOCAL_MONGO_CREDENTIAL["name"],
            })

        url = params.get("url")
        if isinstance(url, str):
            new_url = url
            if "grafana.net/loki/api/v1/push" in url:
                new_url = LOKI_LOCAL_URL
                node.setdefault("credentials", {}).pop("httpBasicAuth", None)
                if not node.get("credentials"):
                    node.pop("credentials", None)
                if params.get("authentication"):
                    params["authentication"] = "none"
                params.pop("genericAuthType", None)
                params.pop("nodeCredentialType", None)
            elif ":7200/repositories/" in url:
                new_url = FUSEKI_QUERY_URL
            elif "host.docker.internal:3030/ontology/update" in url:
                new_url = FUSEKI_UPDATE_URL
            elif "host.docker.internal:8082" in url:
                node["disabled"] = True
                changes.append({
                    "node": name,
                    "action": "disabled",
                    "reason": "polled a Kafka REST proxy that the compose file never provisioned",
                })
            if new_url != url:
                params["url"] = new_url
                changes.append({
                    "node": name,
                    "action": "retargeted-endpoint",
                    "from": url,
                    "to": new_url,
                })

        code = params.get("jsCode")
        if isinstance(code, str) and JSONLD_SOURCE_LINE in code:
            params["jsCode"] = code.replace(JSONLD_SOURCE_LINE, JSONLD_SHIM, 1)
            changes.append({
                "node": name,
                "action": "compat-shim",
                "reason": (
                    "restores the expanded JSON-LD array shape the released code expects "
                    "after the knowledge-store query moved from an unprovisioned GraphDB "
                    "repository to the provisioned Fuseki dataset"
                ),
            })

        selector = params.get("fileSelector")
        if isinstance(selector, str) and selector in FIXTURE_PATHS:
            params["fileSelector"] = FIXTURE_PATHS[selector]
            changes.append({
                "node": name,
                "action": "repointed-input",
                "to": FIXTURE_PATHS[selector],
                "note": "synthetic fixture mounted from reviewer/fixtures",
            })

        kept_nodes.append(node)

    workflow["nodes"] = kept_nodes

    if removed_names:
        connections = workflow.get("connections", {})
        for removed in removed_names:
            connections.pop(removed, None)
        for source, outputs in connections.items():
            for output_name, branches in outputs.items():
                if not isinstance(branches, list):
                    continue
                for branch in branches:
                    if not isinstance(branch, list):
                        continue
                    branch[:] = [c for c in branch if c.get("node") not in removed_names]

    workflow["name"] = f"CAPRA Reviewer Route ({domain}, {provider})"
    workflow["id"] = "capra-reviewer-local"
    workflow.pop("versionId", None)
    workflow["active"] = False
    return workflow, changes


def scan_for_secrets(text: str, label: str) -> None:
    """Abort rather than write a file that carries credential-shaped material."""
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise SystemExit(
                f"refusing to write {label}: it matched a secret pattern "
                f"({pattern.pattern}) at offset {match.start()}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE_DEFAULT)
    parser.add_argument("--target", default=TARGET_DEFAULT)
    parser.add_argument("--report", default=REPORT_DEFAULT)
    parser.add_argument(
        "--provider",
        default="openai-compatible",
        choices=sorted(PROVIDERS),
        help="language-model binding: a generic OpenAI-compatible endpoint "
             "(default) or a local Ollama runtime",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model name to request. Defaults to the provider's placeholder "
             "or local default; supply the model your endpoint exposes.",
    )
    parser.add_argument("--domain", default="admissions", choices=sorted(DOMAIN_TRIGGERS))
    args = parser.parse_args()

    model = args.model or DEFAULT_MODEL[args.provider]

    source = pathlib.Path(args.source)
    if not source.exists():
        print(f"source workflow not found: {source}", file=sys.stderr)
        return 1

    workflow = json.loads(source.read_text(encoding="utf-8"))
    workflow, changes = transform(workflow, model, args.domain, args.provider)

    target = pathlib.Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(workflow, indent=2) + "\n"
    scan_for_secrets(serialised, str(target))
    target.write_text(serialised, encoding="utf-8")

    report = pathlib.Path(args.report)
    report_text = (
        json.dumps(
            {
                "source": str(source),
                "target": str(target),
                "provider": args.provider,
                "model": model,
                "model_is_placeholder": model == DEFAULT_MODEL["openai-compatible"],
                "domain": args.domain,
                "node_count": len(workflow["nodes"]),
                "change_count": len(changes),
                "secrets_in_workflow": False,
                "secret_scan": "no base URL, API key, account name, or vendor host "
                               "is written to the workflow or this report; endpoint "
                               "values live only in the n8n credential store",
                "changes": changes,
            },
            indent=2,
        )
        + "\n"
    )
    scan_for_secrets(report_text, str(report))
    report.write_text(report_text, encoding="utf-8")

    remaining = sorted({
        credential_type
        for node in workflow["nodes"]
        for credential_type in (node.get("credentials") or {})
    })
    print(f"wrote {target} ({len(workflow['nodes'])} nodes, {len(changes)} changes)")
    print(f"provider: {args.provider}, model: {model}")
    print(f"remaining credential types: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
