# Shogun 1.47.7

## Restart control

- Added a **Restart Shogun** button to the Updates page with an explicit confirmation step.
- Performs a graceful application shutdown so managed Mado browsers, schedulers, pollers, telemetry, Office workers, and database engines run their normal cleanup.
- Restarts desktop installations through the Windows/macOS/Linux launcher and reopens Tenshu when ready.
- Supports supervised server deployments while refusing unsafe shutdown when no restart supervisor is configured.
- Prevents duplicate restart requests and avoids launching a replacement process before the previous server exits.
