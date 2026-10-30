# CoreDent API — Production Hardening Task Tracker

## Objective
Bring the CoreDent dental-practice backend (`D:\coredentist\coredent-api`, FastAPI + SQLAlchemy 2 sync models / async endpoints, alembic = schema source of truth, SQLite memory for tests / Postgres prod, coverage gate 60%) to a production-hardening baseline. Frontend is `D:\coredentist\coredent-style-main` (React + TS, `vitest run`, `eslint`, `tsc --noEmit`).

## Important Details (carry-over)
- JWT `iat` is second-precision; `password_changed_at` keeps microseconds → comparisons must truncate via `replace(microsecond=0)` (see `app/api/deps.py` `get_current_user`).
- Open decisions resolved with safe defaults: (11) subscription paywall fails open + warning banner (no lockout); (14) `/marketing` gated behind honest "not implemented".
- `require_role(*roles)` lives in `app/api/deps.py:160`; returns a `role_checker` that depends on `get_current_user` (so it replaces `get_current_user` in a signature). `UserRole` enum in `app/models/user.py:17`. Dominant pattern: `current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN))` + `_csrf: bool = Depends(verify_csrf)` on mutations; reads use `get_current_user` only.
- `get_current_practice` == `get_current_practice_id` (deps.py:225) — just returns `current_user.practice_id`.
- CSRF is globally bypassed in tests (`tests/conftest.py:82` `dependency_overrides[verify_csrf] = _bypass_csrf`); rate limiter disabled (`_limiter.enabled = False`); `get_db` overridden to `TestingSessionLocal`.
- Test DB = `sqlite+aiosqlite:///:memory:` with `StaticPool` (conftest). `auth_headers` fixture logs in an OWNER `test_user`; `db_session` fixture rolls back at teardown; `setup_database` truncates tables per test.
- `get_sync_db` uses a SEPARATE sync `SessionLocal`/engine (`app/core/database.py:55`) for the sync communications endpoints.

## Work State

### Completed
**Task 15 — ruff baseline (DONE + verified)**
- Baseline was 38 errors → reduced to 0 (auto-fixed F401/F841/F541; manually fixed E712 `== True`→`.is_(True)` in `booking.py`/`migrate_password_reset_tokens.py`; hoisted mid-file imports: `patient_portal.py` `limiter`/`log_audit_event`, `referrals.py` `UUID`/`text`, `communication_queue.py` `shared_task`; added `# noqa: E402` to `conftest.py:28` + `test_integration.py`). Full suite green.

**Task 7 — role guards on edi.py + communications.py (DONE + verified)**
- `edi.py`: imported `require_role`/`UserRole`; all 3 endpoints (`check_eligibility`, `submit_claim`, `get_claim_status`) now `require_role(UserRole.OWNER, UserRole.ADMIN)`; removed now-unused `get_current_user` import.
- `communications.py`: imported `require_role`/`UserRole`; all write endpoints (templates CRUD, messages send/update, reminders CRUD, conversations CRUD, conversation-message send) gated `OWNER,ADMIN`. Reads left as `get_current_user` (practice-scoped, matches `billing.py` list_payments).
- Tests: `tests/test_edi.py` `TestEDIRoleGuards` (3 DENTIST→403), `tests/test_communications.py` `TestCommunicationsRoleGuards` (2 DENTIST→403). `auth_headers` fixture uses OWNER so existing tests stay green.
- 40 new tests pass; full suite green.

**Task 8 — config hardening cliff (DONE + verified)**
- `app/core/config_simple.py`: added `_LOCAL_ENVIRONMENTS = frozenset({"development","dev","test","testing","local"})`. The production safety net (was gated on `ENVIRONMENT == "production"`) now fires for ANY non-local env (closes the staging/preview/UAT cliff that booted on committed dev `SECRET_KEY`/`ENCRYPTION_KEY`). `DEBUG` now defaults off outside local envs. Error message names the environment.
- Tests added in `tests/test_config.py` `TestNonLocalEnvironmentCliff`: non-local envs (staging/uat/prod/preview/production) with dev defaults → `ConfigError`; valid config boots; local envs (development/dev/test/testing/local) exempt. 27 config tests pass.

**Task 5 — missing write routes (chairs/appointment types) (DONE + verified)**
- `app/schemas/reference.py`: added `ChairCreate`/`ChairUpdate`/`AppointmentTypeCreate`/`AppointmentTypeUpdate`.
- `app/api/v1/endpoints/references.py` (router mounted at `/api/v1`, no prefix): added `POST /chairs`, `PUT /chairs/{id}`, `DELETE /chairs/{id}`, `POST /appointment-types`, `PUT /appointment-types/{id}`, `DELETE /appointment-types/{id}` — all `require_role(OWNER, ADMIN)` + CSRF. Deletes are SOFT (`is_active=False`) to preserve FK refs from appointments. Note: `Chair` model has NO `description` column (schema `ChairRef.description` is always `None`); appointment-type create uses `name/duration/color/description/is_active`.
- Tests: `tests/test_references_write.py` (9 tests: create/list/update/soft-delete for both, DENTIST→403). 9 pass.

### Active
- Task 6: repair test harness (IN PROGRESS, partial). Sub-items done: CSRF bypass + limiter-off + create_all already present in conftest; tightened `requires_auth` assertions (`== 401`) in `test_edi.py`/`test_communications.py`.
  - BLOCKER: the "27 permissive assertions" tightening is blocked by a genuine harness flake. `test_communications.py` validation-error tests (valid token + empty body) return `422` in isolation but intermittently `401` when run in-suite. Root cause: `StaticPool` funnels all sessions through ONE shared in-memory connection; `db_session` fixture `rollback()` at teardown tangles transaction state so a `auth_headers` login commit is intermittently invisible to a later request's `get_current_user` lookup.
  - Attempted fix: switch test DB to a temp FILE (`sqlite+aiosqlite:///<tmp>/coredent_test.db`) — produced `sqlite3.OperationalError: database is locked` because the sync `SessionLocal` (communications) and async engine contend on the same file. Reverted to `:memory:`+`StaticPool`. The proper fix (independent connections without file-lock contention, e.g. correct per-test transaction/savepoint management, or a file DB with a pool that serializes writers) is risky/low-priority — leave validation-error assertions permissive (`in (422, 401, 403)`) for now.

### Blocked
- (none beyond the Task 6 harness flake noted above)

## Next Move
1. Task 6 remaining (low priority): only after a safe harness fix — do NOT chase the flake by tightening validation-error assertions (they are harness-flaky, not a code bug). If a harness fix lands, tighten the `in (422, 401, 403)` / `in (401, 403)` assertions to exact codes.
2. Confirm the in-flight full-suite background run (`bgp_018e59fe2001hIS3IcHJAEUEnu`) is green (expected ~724 passed, ~15 min). If it fails, triage.

## Relevant Files
- `app/api/v1/endpoints/edi.py`, `app/api/v1/endpoints/communications.py`: Task 7 role guards.
- `app/core/config_simple.py`: Task 8 `_LOCAL_ENVIRONMENTS` + broadened safety net.
- `app/api/v1/endpoints/references.py`, `app/schemas/reference.py`: Task 5 write routes.
- `tests/test_edi.py`, `tests/test_communications.py`, `tests/test_config.py`, `tests/test_references_write.py`: new/updated tests.
- `tests/conftest.py`: test harness (StaticPool + :memory: — DO NOT change without addressing the lock/isolation tradeoff).
