# Shogun 1.46.4

## Fixed

- A second desktop launch now reuses an already-running Shogun instance instead of failing with Uvicorn exit code 3.
- Port conflicts with unrelated applications are reported before database startup begins.
- The per-install control-plane token is no longer displayed in terminal startup output.

## Security contributors

Thank you to @wstlima for the security and deployment review incorporated into this hardening series.
