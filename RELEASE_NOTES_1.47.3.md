# Shogun 1.47.3

## AgentFlow reliability

- AgentFlow now decrypts protected model-provider API credentials before constructing provider requests.
- OpenRouter-backed primary and fallback models receive the configured Authorization header again.
- This prevents valid encrypted credentials from producing repeated HTTP 401 fallback alerts instead of the intended AgentFlow output.
