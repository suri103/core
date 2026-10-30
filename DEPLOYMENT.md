# CoreDent deploy topology

One image, several roles selected by `PROCESS_TYPE` (see `coredent-api/start.py`):

| Role      | `PROCESS_TYPE` | Migrations        | Health probe                              |
|-----------|---------------|-------------------|-------------------------------------------|
| API/web   | `web` (default) | runs under Postgres advisory lock | `GET /health` via `healthcheck.py` |
| Worker    | `worker`      | never             | broker reachable + tasks registered        |
| Beat      | `beat`        | never (`RUN_MIGRATIONS_ON_START=false`) | broker reachable |
| Release   | `release`     | runs, then exits  | always healthy (one-shot job)              |

`railway.template.json` defines the three long-lived Railway services. Set each
service's `PROCESS_TYPE` variable to the matching role. The Dockerfile's
`HEALTHCHECK` invokes `healthcheck.py`, which switches probe by role — worker and
beat containers have no HTTP listener and would otherwise crash-loop on a dumb
curl of `/health`.

Rolling deploys are migration-safe: the web role acquires a Postgres
session-level advisory lock (`pg_advisory_lock`) so only one replica migrates;
peers block until done and then observe an already-current schema.
