# Blue Panda first administrator approval plan

Status: prepared for review; **no administrator account has been created**.

## Inspection findings (2026-11-06)

- `app/models/user.py` stores application accounts in `public.users`, including a bcrypt password hash, one role string, and active status. This is application authentication, not Supabase Auth account creation.
- `app/core/security.py` provides the existing bcrypt `hash_password` and `verify_password` functions. The bootstrap uses these functions directly.
- Backend authorization checks the exact `admin` role. The Management client accepts an active `admin` account and uses `/auth/login` and `/auth/me`. No `super_admin` or seller record is required.
- Public registration always creates a `customer`. Existing `POST /api/users` provisioning requires an authenticated administrator, so it cannot provision the first administrator.
- The only existing command that creates an initial admin is `app/db/seed_data.py`. It uses fixed demo credentials and creates other demo accounts/data. It is unsuitable for this operation and will not be run.
- Read-only inspection of the Supabase database configured in `.env.supabase` found **0 users, 0 active administrators, and 0 inactive administrators**. The authenticated connection role owns the database and users table. The users table has its expected columns, ID primary key and usable sequence, a unique email index, no custom triggers/rules, and no RLS policies enabled on the table. The bootstrap does not alter any of these settings.
- The deployed API returned `200` at `/health`; unauthenticated `/api/auth/me` and `/api/v1/auth/me` returned `401`. The Management login page returned `200`.
- Render's private environment configuration was not accessed. Its connection to this exact Supabase database will be checked by the post-creation login and identity verification; it has not yet been independently confirmed.

## Proposed changes

Add a local command, its security tests, and this plan. No deployed application code, routes, schema, environment files, dependencies, existing accounts, or authorization policies change.

After explicit approval, `scripts/bootstrap_admin.py` will:

1. Connect only to the configured Supabase PostgreSQL owner session-pooler target using TLS. Suppress raw database errors and parameter logging.
2. Require the approved plan hash, an interactive terminal, and the typed owner authorization phrase `AUTHORIZE FIRST ADMIN`.
3. Prompt locally for a display name, chosen email, password, and repeated password using hidden terminal input. Never accept credentials as command arguments or through chat. Refuse any fallback that would echo input.
4. Normalize email as the backend does, apply the existing password policy plus a 16-character admin minimum, and enforce bcrypt's maximum of 72 UTF-8 bytes. Hash and verify the password with the backend's existing functions. The password bytes are not normalized or truncated before hashing, matching existing login behavior.
5. In one bounded transaction, lock users writes, recheck ownership and schema, compare the approved plan, and refuse if any active or inactive administrator exists. Refuse an email already belonging to any user, including case/whitespace variants. Never update, reactivate, or elevate an existing user.
6. Insert exactly one new user with the locally entered name/email and password hash, `role="admin"`, and `is_active=true`. Leave optional contact fields unset. No additional role, seller profile, or Supabase identity is created.
7. Commit, then call `POST https://blue-panda-api-demo.onrender.com/api/auth/login` and `GET /api/auth/me`. Check that both identify the new user by ID, email, exact role, and active status. Keep the returned access token in process memory; never print it or save it. Disable HTTP redirects and environment proxies for these credential-bearing requests.

An existing administrator disables this bootstrap, including an inactive administrator. Account recovery requires a separately approved procedure. Concurrent bootstrap attempts and ordinary user writes are serialized by the PostgreSQL table lock. Any changed plan requires fresh review. Inserts that fail before commit roll back; the sequence may still advance. Nothing invokes application startup, migrations, demo seeding, or a public admin-registration route.

If verification fails after commit, the command returns a failure and explicitly reports that the account remains created. It does not delete the account or attempt another creation. Check the Management login and deployment database configuration before any further action. A connection failure during commit can leave the outcome uncertain; run the read-only check before considering a retry.

## Approval scope

Approve **one new active application administrator**, using the email and password you choose in the local terminal. Approval grants no permission to change an existing user or create additional administrators.

Reviewed read-only plan hash:

```text
7e2a1be4c03cd3f5bd9dc668bb6b5aec9ab5df583ddd66b80213b6c87bb9525a
```

Run from `backend/` to inspect again without writing:

```sh
rtk proxy .venv/bin/python -m scripts.bootstrap_admin
```

**Only after explicit owner approval**, run locally:

```sh
rtk proxy .venv/bin/python -m scripts.bootstrap_admin --apply --approved-plan 7e2a1be4c03cd3f5bd9dc668bb6b5aec9ab5df583ddd66b80213b6c87bb9525a
```

Enter the authorization phrase and your credentials at the prompts. Do not paste the password into chat, shell arguments, environment files, or logs. Hidden input shows no characters. If any plan detail changes, stop and review the new read-only plan before applying it.

## Verification

Security tests use isolated temporary SQLite databases for inserts and rollback, mocks for PostgreSQL ownership checks, and mock HTTP responses for the deployed login flow. They do not create accounts in Supabase. The actual Supabase plan was executed with a read-only transaction. No live authenticated verification has been run because account creation awaits approval.

Validation completed: `rtk proxy .venv/bin/python -m pytest tests/test_admin_bootstrap.py tests/test_authorization.py -q --tb=short` — **365 passed**, with two existing dependency deprecation warnings. Syntax and whitespace checks passed for all three added files.

After successful creation, open https://blue-panda-management.vercel.app/login, enter your locally chosen credentials, and confirm the administrator dashboard loads. The command's preceding API verification confirms the deployed backend identity and role independently of client-side navigation.
