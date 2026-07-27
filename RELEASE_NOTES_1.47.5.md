# Shogun 1.47.5

Security hardening release driven by the repository-wide CodeQL review.

## Security

- Prevented chat attachments from reading caller-selected local files; only server-managed visual artifacts are accepted.
- Hardened backup creation, deletion, and restore against filename traversal, ZIP Slip, symlinks, unsupported archive members, and decompression resource abuse.
- Enforced resolved-directory containment for frontend fallback files and Ronin screenshots.
- Removed exception details from user-facing API and streaming responses while retaining full server-side logging.
- Replaced unsafe or analyzer-hostile regular-expression logic with bounded, linear alternatives.
- Removed prototype-pollution-capable nested configuration setters.
- Rebuilt Guide printing without `document.write` or HTML-string injection.

## Validation

- Backend traversal, archive restore, and visual attachment security tests.
- Frontend production TypeScript build.
- Python bytecode compilation across backend and maintenance scripts.
