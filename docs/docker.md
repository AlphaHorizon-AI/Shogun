# Docker telemetry

Docker telemetry is disabled by default. State persists in `shogun_configs`.
To opt in, set both:

```env
SHOGUN_TELEMETRY=on
SHOGUN_TELEMETRY_NOTICE_VERSION=1.0
```

`on` without notice version `1.0` fails closed. Set telemetry to `off` and restart
to apply a central prohibition. Manage withdrawal and deletion from **Privacy &
Telemetry** with the infrastructure administrator token.

Cloning the configuration volume may duplicate a random installation ID. The
server detects a different random nonce and the client rotates identity without
using a machine fingerprint.
