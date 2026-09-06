# Direct ChatGPT OAuth — Yellow Label and White Label

In **The Katana → Model Providers**, add or edit an OpenAI provider and select
**Connect with ChatGPT (direct OAuth + PKCE)**. Save, then complete sign-in in
your browser. Open Shogun through localhost on the machine running its backend.
The existing API-key, workload-identity, and Codex app-server options remain available.

If the sign-in browser cannot return automatically, paste the **entire matching
localhost callback URL** into the masked Callback URL field and select
**Complete secure connection**. The panel retains an **Open sign-in** link when
automatic browser opening fails. Callback ports 1455 and 1457 are tried; occupied
ports leave manual recovery available. Never share callback URLs or tokens.

**Cancel sign-in** retires the attempt and preserves any previous connection.
Saving an existing OAuth provider starts a reconnect; failed replacement consent
also preserves the previous credentials. **Disconnect OAuth** removes the local
grant and pending attempts. It does not revoke all sessions in your OpenAI account.

**Test connection** checks subscription metadata without generating text or
submitting prompts. It reports subscription limits separately from successful
authentication. Enter exact model IDs supported by your subscription in Active
Models; Platform `/models` discovery is deliberately unavailable for direct OAuth.
Sign-in does not change model selection or routing profiles, and does not promise
access to every configured model. Existing explicit routing fallbacks still apply.

## Authentication and transport

This follows the supplied Alpha Studio integration knowledge item. Authorization
Code + S256 PKCE uses `auth.openai.com`, scopes `openid profile email offline_access`,
and fresh ten-minute, process-bound attempts. State hashes are compared in constant
time. Verifiers and saved access/refresh tokens use Shogun's existing Fernet encryption.
Tokens are never imported from browser cookies or another application's credential files.

The public client identifier can be overridden with `OPENAI_OAUTH_CLIENT_ID` or
the provider's optional client-ID field. It is not a secret and does not require a
client secret. The default matches the inspected Alpha Studio client identifier.
Confirm the provider-supported client/distribution arrangement before distributing
an integration under a different product registration.

Subscription requests go only to `https://chatgpt.com/backend-api/codex/responses`,
with the account routing ID obtained from the token response. Local JWT decoding
is used for routing metadata, not as proof of user identity. Test uses
`https://chatgpt.com/backend-api/wham/usage`, retries one 401 after coordinated
refresh, and requires a subscription metadata structure to report success.
These backend endpoints are implementation dependencies, not public Platform API contracts.

The adapter preserves text, image inputs, function calls/results, structured-output
settings, and reasoning effort for Shogun's existing chat workflows. It translates
Responses SSE into Shogun's chat-completion format. It does not add image/video
generation features or grant subscription access to Platform media endpoints.
No API-key fallback is silently substituted by authentication or transport.

## Concurrency and operations

Provider management and refresh share asynchronous and local OS file locks under
`VAULT_PATH/oauth-locks`. Workers sharing a database must share that directory;
do not delete active lock files. Refresh reloads committed credentials and commits
rotation in a separate short authentication transaction, so a caller rollback does
not lose rotated tokens. Rejected grants require reconnect; temporary failures
retain credentials. Disconnect, removal, and authentication changes invalidate stale jobs.

Resolve credentials **before flushing unrelated writes** in the same SQLite database.
The execution router refreshes before its routing-audit writes. The auth service
never commits a generation caller's unrelated work. This local design is not a
distributed identity service: browser callbacks and pending attempts must reach the
same server process. A crash between remote rotation and durable local storage may
still require reconnect.

Only the new loopback callback is authenticated by its one-use OAuth state;
provider management retains Shogun's administrator-header requirement. Callback
query strings are redacted from Uvicorn access logs. Result redirects and pages use
no-store/no-referrer headers and display no token/code parameters.

No database schema migration or new package dependency is required. Restart the
backend and rebuild/reload the frontend after installing. Protect the database,
vault configuration, and backups as credential-bearing material.

## Validation

`tests/test_chatgpt_oauth.py` exercises isolated SQLite databases and synthetic
HTTP responses, including callback races, recovery validation, cancellation,
replacement failure, encrypted storage, refresh coordination and durability,
disconnect, subscription metadata checks, and transport conversion. Existing
OAuth, Codex app-server, routing, and tool-call tests provide regression coverage.
No real-account consent or live generation is performed by these tests.

Reference: [OpenAI authentication documentation](https://learn.chatgpt.com/docs/auth)
distinguishes subscription sign-in from usage-based Platform API authentication.
