# Shogun installation telemetry

Shogun installation telemetry is a voluntary, pseudonymous adoption signal. It is
disabled by default and is separate from Shogun's licence, operational logging,
model-routing metrics, and College analytics.

No request is made to `telemetry.alphahorizon.io` until an administrator explicitly
accepts consent notice `1.0`. Blocking that hostname has no effect on Shogun.

## Exact version-one data

Registration sends:

| Field | Values |
|---|---|
| `schema_version` | `1` |
| `installation_id` | Random UUIDv4, generated locally |
| `instance_nonce` | Independent random UUIDv4 for clone detection |
| `consent_notice_version` | `1.0` |
| `shogun_version` | Product version |
| `build_id` | Published build number |
| `release_channel` | `stable`, `beta`, or `development` |
| `distribution_channel` | Approved distribution enum |
| `platform_family` | `windows`, `linux`, `macos`, or `other` |
| `architecture` | Normalized architecture enum |
| `install_type` | `native`, `docker`, `headless_server`, or `development` |
| `operation_mode` | `single_user` |

Events send the same product/platform dimensions plus `event_id`, `event_type`,
and `occurred_at`. `update_completed` may include `previous_version`. The
installation token is sent only in the HTTPS Authorization header.

The only event types are `install_completed`, `update_completed`,
`active_heartbeat`, `consent_revoked`, and `telemetry_test` (only when the
administrator presses the test button).

There is no generic metadata field. Unknown fields and enum values are rejected
by both client and server. Event bodies are limited to 4 KB; batches are limited
to ten events and 32 KB.

## Never collected

Telemetry never reads or sends prompts, responses, files, filenames, paths,
memory, messages, contacts, email, calendars, user or organization identities,
agent or workflow names, tool inputs or outputs, URLs, browser history,
screenshots, hostnames, machine identifiers, MAC addresses, serial numbers,
credentials, secrets, API keys, detailed OS versions, or IP addresses as
application telemetry fields.

The HTTP edge necessarily sees a source network address while serving a request.
The application does not persist or correlate it. Production proxy access logs
must omit or irreversibly redact it.

## Frequency and offline behavior

An opted-in installation sends one lifecycle event and no more than one counted
heartbeat per seven days. Heartbeats have random jitter of plus or minus 12 hours.
Missed heartbeats do not accumulate. The local queue holds at most five strict
events, one heartbeat, and expires entries after 30 days.

DNS, TLS, firewall, timeout, proxy, database, and telemetry-service failures are
silent and cannot block Shogun startup or operation. HTTPS certificate validation
is mandatory, redirects are refused, environment proxy credentials are ignored,
and there is no plaintext fallback.

## Enable, disable, preview, and delete

Use **The Tenshu → Privacy & Telemetry**. In desktop mode the local administrator
may change the setting. In Server mode, a valid infrastructure-administrator
token is required.

Unattended native installation:

```bash
./install.sh --telemetry=on --accept-telemetry-notice=1.0
```

Docker:

```env
SHOGUN_TELEMETRY=on
SHOGUN_TELEMETRY_NOTICE_VERSION=1.0
```

Setting `SHOGUN_TELEMETRY=on` without the exact accepted notice version fails
closed. Production builds cannot override the ingestion endpoint.

Disabling stops scheduling immediately, clears the token and queue, and attempts
one revocation event. “Delete my telemetry data” additionally requests removal of
the installation record and raw events. A failed remote deletion is reported in
Settings and is not retried indefinitely.

## Storage, retention, service, and dashboard

Client state is stored in `configs/telemetry.json` with restricted permissions.
The token is never shown or logged. The service stores an HMAC of the installation
ID and a SHA-256 hash of the opaque token, never the raw values.

Target retention is 90 days for raw events, 13 months for inactive installation
status, 24 months for consent history and aggregates, 90 days for security logs,
14 days for operational logs, and 35 days for backups. Run
`python -m telemetry_service.maintenance` to purge expired raw events.

The ingestion service is in `telemetry_service/`; its hardened template is
`telemetry-compose.yml`. Aggregate access requires a trusted SSO identity proxy
asserting a named account, approved Alpha Horizon group, MFA, and a separate
proxy secret. Access is audit logged. There is no individual timeline and no
remote-control response channel.

Repository code cannot itself prove EU hosting, WAF configuration, backup
execution, SSO-provider setup, legal approval, processor agreements, or
publication of the external privacy page. Those remain launch gates documented
in `telemetry_service/DEPLOYMENT.md`.
