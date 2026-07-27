# Shogun 1.47.9

## Provider model discovery

- Restored live model-catalog scanning for OpenAI, Anthropic, Google Gemini, OpenRouter, and compatible custom providers in Katana.
- Discovered cloud models can once again be clicked to populate the provider's active model list.
- Restored click-to-add behavior for models returned by Ollama and LM Studio, so selected local models become eligible router candidates.
- Local filesystem discovery now expands Windows environment variables such as `%USERPROFILE%` and user-home paths.
- Cloud catalog requests are made server-side with protected provider credentials, HTTPS-only public destinations, DNS pinning, response-size limits, and redirects disabled.
