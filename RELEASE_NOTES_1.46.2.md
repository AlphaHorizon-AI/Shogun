# Shogun 1.46.2

## Fixed

- Fixed upgraded desktop installations failing during legacy database repair with an opaque Uvicorn exit code 3.
- Preserved Uvicorn loggers while Alembic migrations run so future startup failures retain their actionable traceback.

## Security contributors

Thank you to @wstlima for the security and deployment review incorporated into this hardening series.
