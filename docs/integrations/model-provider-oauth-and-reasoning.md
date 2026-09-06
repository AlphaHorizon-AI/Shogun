# Model Provider OAuth and Reasoning Controls

## Authentication boundary

Shogun keeps authentication separate from model-generation settings.

- OpenAI Platform model API access uses an API key or an administrator-provisioned workload identity bearer token. ChatGPT subscription connections use a separate transport: either the existing Codex app-server option or direct ChatGPT OAuth described below.
- Google Gemini supports OAuth 2.0. Shogun implements Authorization Code with PKCE, state validation, encrypted token storage, refresh-token rotation, and explicit disconnect.
- Custom OpenAI-compatible providers may use OAuth only when their authorization URL, token URL, scopes, and client registration are configured.
- Anthropic and OpenRouter remain API-key connections until a provider-specific OAuth contract is added and tested.

References: [OpenAI API authentication](https://developers.openai.com/api/reference/overview) and [Google Gemini OAuth](https://ai.google.dev/gemini-api/docs/oauth).

## Google OAuth setup

1. In Google Cloud, enable the API required by the Gemini endpoint and configure the OAuth consent screen.
2. Create an OAuth client suitable for the Shogun desktop installation.
3. Add Shogun’s callback URL to the client registration. By default it is `http://127.0.0.1:<SHOGUN_API_PORT>/api/v1/model-providers/oauth/callback`.
4. In **The Katana → Model Providers**, choose **Google Gemini** and **OAuth 2.0 (Authorization Code + PKCE)**.
5. Enter the OAuth client ID, optional client secret, and Google Cloud project ID. Leave scopes empty to use Shogun’s documented defaults, or provide the exact space-separated scopes required by the deployment.
6. Save. Shogun opens the Google consent page. The provider becomes connected only after the callback and token exchange succeed.

The Google project ID is sent as `x-goog-user-project` for OAuth-authenticated model requests and model discovery.

## Custom provider OAuth setup

Register Shogun’s callback URL with the provider, then enter the client ID, optional client secret, HTTPS authorization endpoint, HTTPS token endpoint, and space-separated scopes. Shogun rejects private-network and non-HTTPS OAuth endpoints to prevent server-side request forgery. Loopback HTTP is allowed only for Shogun’s local callback and UI return origin.

Pending OAuth state is one-use, expires after ten minutes, and is held only in the running Shogun process. Restarting Shogun cancels an unfinished consent flow.

## OpenAI setup

Choose one of these authentication modes:

- **API key** for ordinary OpenAI API access.
- **Workload identity bearer token** when an administrator has configured OpenAI workload identity federation and issued a short-lived token.

Do not paste a ChatGPT session token or attempt to reuse ChatGPT login cookies. They are not OpenAI model API credentials.

## Per-model reasoning

Reasoning choices are data-driven and appear only for models whose exact model ID is present in Shogun’s reasoning capability catalog.

1. Add or discover physical model IDs on a provider.
2. In **Active Models**, choose a provider-level reasoning default for each supported model, or leave it on **Provider default**.
3. In **Model Routing**, a custom routing profile may override reasoning independently for every primary or fallback model.
4. Preview the route to verify the selected model, temperature, and effective reasoning effort.

Provider defaults live in `model_providers.config.model_reasoning`. Profile overrides live in `model_routing_profiles.model_settings.<registry-id>.reasoning_effort`. The runtime validates both against the installed catalog before saving and again before building a request.

For OpenAI-compatible Chat Completions, Shogun sends `reasoning_effort`. When a non-`none` OpenAI reasoning effort is selected, incompatible sampling controls such as `temperature` and `top_p` are removed from that request. See the [OpenAI model guide](https://developers.openai.com/api/docs/guides/latest-model) for the current model-specific effort values.

## Adding future models

Update `shogun/resources/model_reasoning_capabilities.json`; do not hardcode model IDs in React components or runtime call sites. Each rule declares model patterns, supported effort values, and the provider default. Add validation and request-payload tests whenever the catalog changes.

For direct ChatGPT subscription sign-in, recovery, and operations, see [Direct ChatGPT OAuth](chatgpt-direct-oauth.md).
