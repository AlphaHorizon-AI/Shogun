# Shogun 1.47.1

## Calendar reliability

- Google Calendar connections now use Google's supported CalDAV v2 event collection and resolve `primary` to the connected account's calendar ID.
- Existing Google CalDAV v1 configurations are migrated at runtime, so no account reconfiguration is required.
- OAuth bearer credentials are used when available while existing working CalDAV credentials remain compatible.

## Permission controls

- ToolGate's Comms policy is now the single authority for Mail and Calendar operations, including direct UI actions, AgentFlow sends, and heartbeat reads.
- The duplicate Account Scopes controls have been removed from Katana's Mail and Calendar setup.
- Calendar write permission consistently covers create, edit, and delete; Mail write permission covers send and delete.

## Security contributors

Thank you to @wstlima for the valuable security and deployment review that continues to inform Shogun's hardening work.
