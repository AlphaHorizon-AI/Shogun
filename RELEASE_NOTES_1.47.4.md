# Shogun 1.47.4

## Explicit model management

- Katana providers now expose an explicit model selector with quick-add suggestions and exact custom model IDs.
- Empty selections are respected: a provider with no selected models contributes no routing candidates.
- Provider edits preserve unrelated provider configuration while updating the selected model list.
- The capability registry now identifies each model by its exact model ID and provider.
- Registry synchronization disables removed or disconnected models without overwriting an operator's manual model toggle.
- Balanced, Economy, Premium, and custom routing remain restricted to enabled models on connected providers.
