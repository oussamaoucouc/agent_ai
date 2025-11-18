## Goals
- Short-lived access tokens for API calls, long-lived refresh tokens to keep users signed in securely.
- HttpOnly, Secure cookies for refresh tokens (not accessible to JavaScript).
- Token rotation on refresh with revocation tracking to prevent reuse.

## Approach Overview
- Access token: HMAC-signed, expires ~15 minutes, carried in `Authorization: Bearer <access>`.
- Refresh token: HMAC-signed, expires ~7–14 days, stored in an HttpOnly Secure cookie; used only at `/auth/refresh`.
- Rotation: on refresh, issue a new pair, mark the old refresh token as revoked and record `replaced_by`.

## Backend Implementation
- Token helpers (`afriprof_ai/auth.py`):
  - Add `issue_access_token(uid, role, ttl_seconds=900)` and `issue_refresh_token(uid, role, ttl_seconds=604800)`.
  - Include claims: `uid`, `role`, `exp`, `iat`, `jti`, `typ` ("access" or "refresh").
  - Add `verify_access_token(token)` and `verify_refresh_token(token)` that also enforce `typ`.
- Refresh token store (`afriprof_ai/users.py` or new module):
  - Create `refresh_tokens` table via SQLAlchemy with columns: `id (pk)`, `user_id`, `jti`, `issued_at`, `expires_at`, `revoked (bool)`, `replaced_by (nullable)`, `user_agent (optional)`, `ip (optional)`.
  - Helper functions: `store_refresh(uid, jti, expires_at, meta)`, `revoke_refresh(jti, replaced_by=None)`, `is_refresh_valid(jti)`.
- Endpoints:
  - `POST /users/login` (in `afriprof_ai/users.py`): after verifying credentials, issue access and refresh; set refresh in HttpOnly Secure SameSite=Lax cookie (e.g., `Set-Cookie: refresh_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/`); return JSON with `access_token`, `user`.
  - `POST /auth/refresh` (new in `afriprof_ai/api.py`): read refresh cookie, verify token and table entry, rotate (issue new access+refresh), revoke old by `jti`, set new cookie; return `access_token` JSON.
  - `POST /users/logout` (in `afriprof_ai/users.py`): read refresh cookie, revoke current jti, clear cookie.
- Authorization enforcement (`afriprof_ai/api.py`, existing changes retained):
  - All protected endpoints continue to require a valid access token; session ownership validated as implemented.
- Security policies:
  - Cookies: `Secure` in production, `SameSite=Lax`, `Path=/`.
  - Rotation: always revoke old refresh on successful refresh; detect and reject refresh token reuse (if a revoked `jti` is used again, treat as compromise and revoke all for that user).
  - Rate-limit refresh and login attempts.

## Frontend Implementation
- Storage (`ai-teacher-assistant/services/storageService.ts`): keep access token in memory/sessionStorage as today; do not store refresh token (only a cookie).
- API wrapper (`ai-teacher-assistant/services/apiService.ts`):
  - On 401 from any call, attempt a single refresh by `POST /auth/refresh` (no body; cookie is sent automatically). If refresh succeeds, update access token and retry original request once.
  - On refresh failure, force logout (clear sessionStorage) and show login page.
- Login flow (`ai-teacher-assistant/App.tsx`): save `access_token` from `/users/login` into storage; rely on backend-set cookie for refresh.
- Logout: call `/users/logout`, clear client state.

## Deployment & Configuration
- Env vars: `APP_ENV=production`, `APP_AUTH_SECRET=<strong random>`, `API_RELOAD=0`.
- HTTPS is required for `Secure` cookies; ensure your cloud service terminates TLS.
- CORS: restrict to your frontend domains in `afriprof_ai/api.py`.
- Cookie domain: if serving API on a different subdomain, set cookie `Domain` appropriately.

## Migration & Compatibility
- Existing users: no change required; login will issue new access/refresh pair.
- DB migration: create `refresh_tokens` table at startup if missing.
- Optional: rehash legacy passwords to PBKDF2 on next successful login.

## Verification
- Unit tests: token issue/verify, rotation logic, revocation checks.
- Manual: login → access works; clear access → 401 → refresh → access renewed; logout → refresh invalid; reuse old refresh → rejected.
- Logs: record login, refresh, logout events with `user_id` and `jti`.

## Deliverables
- New endpoints and helpers implemented.
- Frontend auto-refresh logic added.
- Deployment instructions with env vars and HTTPS requirement.

Confirm and I will implement the backend endpoints, token helpers, DB table, and the frontend 401→refresh logic, then validate locally.