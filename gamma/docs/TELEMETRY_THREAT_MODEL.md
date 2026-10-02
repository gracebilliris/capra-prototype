# Gamma telemetry privacy threat model

This threat model records design risks; it is not evidence that privacy is
protected.

| Risk | Data/layer | Gamma control and test | Residual risk / boundary |
|---|---|---|---|
| Aggregation and re-identification | source/context, DFL/CL | allowlist, token-like synthetic application ID, role-gated detail | combinations may still identify in real data |
| Insider access | all detailed evidence, HIL/CL | explicit roles; unauthorised-action and detailed-view tests | prototype roles are not enterprise IAM |
| Secondary use | telemetry, DFL | required business purpose and policy version | declared purpose may be false |
| Excessive retention | all stores, CL | expiry, legal hold, deletion receipt test | durations are demonstration values |
| Cross-border transfer | context, CL/RIL | processing/data-subject locations and candidate obligations | no legal applicability determination |
| Prompt/provider disclosure | assessment, RIL | deterministic local rules; provider ID contains no secret | external-model route is not tested here |
| Log/screenshot disclosure | evidence, all layers | minimised JSON; payload-free public view | free-form future fields require review |
| Model-provider exposure | assessment, RIL | no external provider in authoritative Gamma run | does not validate other providers |

Evidence artefacts are synthetic. Detailed views require a demonstration role;
the public view contains identifiers and stage metadata only, without source
payloads.
