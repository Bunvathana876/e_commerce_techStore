# Management login CORS investigation

Investigation date: 2026-11-08. Changes are local only. No deployment, commit,
push, environment update, production database mutation, or migration was performed.

## Findings and evidence

The reported preview failure is not yet fully diagnosed: its exact browser origin
and the corresponding Render request/error log were not supplied. Browser automation
was unavailable. No preview hostname was guessed or added to the allowlist.

Credential-free probes against `https://blue-panda-api-demo.onrender.com` returned:

| Probe | Result |
| --- | --- |
| `OPTIONS /api/auth/login`, production Management Origin, requested POST and `content-type,authorization` | 200; `Access-Control-Allow-Origin: https://blue-panda-management.vercel.app`; credentials allowed |
| `OPTIONS /api/v1/auth/login`, production Management Origin | 200; matching allow-origin header |
| `POST /api/auth/login`, production Management Origin, JSON `{}` | 422; matching allow-origin header; missing-field validation response |
| `POST /api/auth/login`, production Management Origin, valid-shaped generated nonexistent email and dummy input | **500 `Internal Server Error`; no allow-origin header** |
| Login preflight from synthetic `https://untrusted-preview.vercel.app` | 400 `Disallowed CORS origin`; no allow-origin header |
| `GET /health` | 200 healthy |
| `GET /readyz` | 200 ready; database connected (read-only `SELECT 1`) |
| Production Management `/login` | 200; CSP permits connections to the Render API |

The production Management origin is already allowed on the live backend. Adding it
again alone will not resolve an origin mismatch on a different preview URL.
Readiness verifies connectivity, not the login query, table schema, password
verification, or token issuance. The generated nonexistent-account probe confirms
that an underlying login 500 occurs even with an allowed production origin, and
that its response is masked by missing CORS headers. The precise server exception
is still unknown without Render logs. The inspected nonexistent-account path only
queries users, then rejects login before account/session writes. An empty POST
does not exercise that query. Real-account login was not attempted and no real
credentials or tokens were read or displayed.

`management/src/lib/config.ts` selects `NEXT_PUBLIC_API_URL`, with the supplied
Render `/api` URL as its production fallback, and strips trailing slashes.
`management/src/lib/api.ts` sends JSON POST to `${API_BASE_URL}/auth/login`.
It includes `Content-Type: application/json` and attaches an existing bearer token
when present; either JSON or Authorization requires a browser preflight.
The deployed production login JavaScript contains the correct Render `/api` base
URL and `/auth/login` endpoint. Its CSP also names that backend. The failing
preview's built bundle and settings remain unverified.

`backend/app/core/config.py` parses `CORS_ORIGINS` into a trimmed list. It accepts
comma-separated strings and JSON arrays, including supported surrounding quotes.
The `list[str] | str` field lets CSV input reach the validator instead of failing
environment-source JSON decoding. Tests exercise both actual process environment
variables and temporary dotenv files. No parser change is needed for these formats.
Production rejects empty lists, the `*` origin, and origins with paths/trailing slashes.
There is no `allow_origin_regex`: Vercel domains receive exact string matching.

## Confirmed local defect and fix

Before the fix, an injected unhandled login exception produced a generic HTTP 500
without an allow-origin header, even for explicitly trusted origins. Four regression
cases failed across production/fixture-preview origins and both API prefixes.
Such a response can appear as a browser CORS error and `Failed to fetch`.
The separate live nonexistent-account probe also returned 500 without CORS headers.
The middleware fix addresses this error masking, not the unknown exception causing
the live login failure. Production's allowlist is therefore not the only issue.

`backend/app/main.py` now wraps the complete FastAPI application in CORSMiddleware,
outside ServerErrorMiddleware. Its explicit origin allowlist, credentials setting,
methods, headers, and preflight cache duration are unchanged. Trusted origins can
receive the generic 500 response; untrusted origins still get no allow-origin header.
Exceptions remain errors and retain normal server logging/re-raising behavior.
No exception details are exposed to the client.

The factory now returns the CORS ASGI wrapper; its `.app` is the inner FastAPI
instance. Uvicorn continues using `app.main:app`. Existing repository callers use
the returned application through ASGI/TestClient.

This follows [Starlette's global CORS enforcement guidance](https://www.starlette.dev/middleware/#corsmiddleware-global-enforcement).
Authentication, authorization, hashing, sessions, rate limits, database settings,
and schemas were not changed.

## Exact manual resolution steps

Perform these steps yourself after review; none were executed remotely by the agent.

1. Open the failing preview. In DevTools Network, select the login request and copy
   only Request URL, Request Method, status, and the `Origin` request header.
   Alternatively, evaluate `window.location.origin` in that page's Console.
   Do not share request bodies, Authorization headers, cookies, tokens, or an
   unredacted HAR. Record whether OPTIONS failed or POST actually ran.
2. In the Vercel `blue-panda-management` project, locate that exact URL under
   Deployments. Verify the expected owner/team, repository, branch, and commit.
   Trust it only if the code is reviewed and approved to access this backend.
   A project-like hostname or `.vercel.app` suffix is insufficient. An unknown,
   forked, or unreviewed preview must remain denied. Generated URLs are listed in
   [Vercel's deployment overview](https://vercel.com/docs/deployments/generated-urls).
3. If only production access is needed, use
   `https://blue-panda-management.vercel.app/login`; its origin already passes
   live preflight. No additional preview origin is required for that URL.
4. For an approved preview, open Render Dashboard, select the backend service for
   `blue-panda-api-demo.onrender.com`, and open Environment. Edit `CORS_ORIGINS` by
   **merging** the exact approved preview origin into the existing trusted list.
   Retain the production Management member
   `https://blue-panda-management.vercel.app` and all other existing approved client
   origins. Use a JSON array or CSV. For example, the required Management-only
   member is `["https://blue-panda-management.vercel.app"]`; this example is not a
   replacement for a live list that also serves other clients. Origins contain
   scheme and host (plus a non-default port if applicable), with no path or trailing
   slash. Do not add a Vercel wildcard/regex. Remove temporary entries when their
   preview access is no longer approved. Save/apply the environment change and let
   Render restart/redeploy when you are ready. Keep existing database and auth
   configuration unchanged. Merely broadening CORS cannot fix a backend exception.
5. In Vercel Project Settings -> Environment Variables, verify
   `NEXT_PUBLIC_API_URL=https://blue-panda-api-demo.onrender.com/api` for Production
   and, only for previews approved to use this demo backend, Preview. Check any
   branch-specific override. Set the value without surrounding quotes or an extra
   `/api`, and verify `NEXT_PUBLIC_STOREFRONT_URL` remains configured as required by
   the existing build. Production is already serving the correct API URL. If a
   preview should use a separate staging API, use that staging URL and allow its
   approved browser origin on that API instead. A changed `NEXT_PUBLIC_*` value
   requires a new build/deployment because Next.js embeds it in browser JavaScript;
   see [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser).
6. After reviewing the local backend fix, release it through your normal process
   when ready. This patch requires no database migration. A configuration-only
   origin correction can be applied independently, but will not fix masked 500s.
7. After applying changes, open a fresh browser session, visit the approved URL,
   and verify OPTIONS is 200 with an allow-origin value exactly equal to the page's
   origin. Confirm the POST targets the Render `/api/auth/login` endpoint without
   redirects. Use your own account privately: a valid active account should log in;
   an incorrect password should produce a readable 401; disabled accounts should
   produce 403; repeated attempts should still produce 429. An empty JSON body
   should produce a readable 422. Check `/api/v1` too if validating mobile parity.
8. The live generated-account POST already returned 500. Correlate the failure
   timestamp with Render Logs and inspect the sanitized exception type and stack
   location before attempting a server-side fix. Do not consider login resolved
   until that exception is diagnosed and fixed. A successful `/readyz` does not
   rule out login-specific schema or runtime
   failures. Do not modify production Supabase, run migrations, rotate credentials,
   or alter auth flags as a speculative CORS fix. Infrastructure-generated 502/503
   responses may also lack app CORS headers and require separate availability work.

For a credential-free production check, run:

```bash
rtk proxy curl -i --max-time 60 -X OPTIONS \
  'https://blue-panda-api-demo.onrender.com/api/auth/login' \
  -H 'Origin: https://blue-panda-management.vercel.app' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type,authorization'

rtk proxy curl -i --max-time 60 \
  'https://blue-panda-api-demo.onrender.com/api/auth/login' \
  -H 'Origin: https://blue-panda-management.vercel.app' \
  -H 'Content-Type: application/json' \
  --data '{}'
```

Expect 200 with a matching allow-origin header for OPTIONS and 422 with that header
for the empty POST. To test the verified preview, replace only the Origin value with
its exact approved origin. Curl reports HTTP headers; it does not enforce browser
CORS. A synthetic unrelated origin should receive preflight 400 without an
allow-origin header. Production and preview hosts are different origins even when
they serve the same deployment.

## Verification

New coverage in `backend/tests/test_cors_security.py` checks process/dotenv parsing,
trusted production and explicit fixture-preview preflights, unrelated/unreviewed
Vercel and lookalike-origin denial, successful login, 401/403/422/429 responses, and
generic 500 visibility only for trusted origins, under both `/api` and `/api/v1`.

Executed from `backend/` using the existing virtual environment:

```bash
rtk proxy .venv/bin/python -m pytest tests/test_cors_security.py tests/test_config_security.py tests/test_auth_sessions.py tests/test_auth_rollout_defaults.py tests/test_rate_limiting.py -q
# 130 passed, 2 skipped

rtk proxy .venv/bin/python -m pytest -q
# 702 passed, 2 skipped
```

The two skipped checks require a test Redis server on localhost port 6389, which
was unavailable. Both runs reported two existing Starlette/httpx/AnyIO deprecation
warnings. No dependencies were installed or upgraded. Root and backend
`rtk git diff --check` passed. Diff/status review found only the two intended
backend edits plus this new report; pre-existing changes elsewhere were preserved.

All database-writing checks use the existing pytest isolation: temporary SQLite
database and uploads directory, generated test JWT secret, and AUTO_INIT_DB=false.
Successful login/token creation happens only against these test fixtures.
No Next.js or Flutter files changed, so their build/lint/analyze checks are not
required for this backend patch. Browser login from the failing preview remains
unverified pending its URL and sanitized Render exception evidence.
