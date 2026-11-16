# Theona runs

Use the configured `OS_URL` and `Authorization: Bearer $OS_API_KEY` for every
call. Begin with `GET /tools/theona/agents?search=<task>` and choose a current
agent by its described capability and required inputs.

| Action | Route | Body / query |
|---|---|---|
| Start | `POST /tools/theona/runs` | `{"agentId":"<selected-id>","input":"<task and bounded inputs>"}` |
| Status/result | `GET /tools/theona/runs/<runId>` | Optional `wait=true` for long polling |
| Follow-up | `POST /tools/theona/runs/<runId>/input` | `{"input":"<requested information>"}` |
| Cancel | `POST /tools/theona/runs/<runId>/cancel` | — |
| Batch | `POST /tools/theona/runs/batch` | `{"agentId":"<selected-id>","inputs":["<task A>","<task B>"]}` |

Retain the returned `runId` (each handle under `runs` for a batch) and poll
rather than starting the same task again. Supply follow-up input only when the
run requests it. Report completion from the returned terminal state and result,
not from successful submission. A batch consumes one run unit per input; use
only the authorized work and budget.

On 429 check `/me/limits?resource=theona` and honor any retry delay. On a timeout
or uncertain create result, do not blindly resubmit: it may already be running.
`theona_run_ownership_unconfirmed` requires Egbe team recovery, not another
create. Reads can be retried after transient failures. A 404 means no run is
available to this project; an old unregistered handle needs Egbe team recovery.
Missing provider configuration or OAuth access is a platform blocker.
