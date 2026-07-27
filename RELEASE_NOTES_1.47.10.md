# Shogun 1.47.10

## AI provider credential editing

- Fixed provider edits that could remove a stored API key when the edit changed models or other non-secret settings.
- Katana no longer places the redacted `********` value into the API-key input or sends it back as credential data.
- The edit form now clearly indicates whether a protected credential is stored and whether it will be retained or replaced.
- Newly entered replacement credentials are trimmed, encrypted, saved, and used for the provider's Authorization header.
- Editing legacy one-model provider records now preserves their model selection instead of writing an empty model list and disabling routing eligibility.
