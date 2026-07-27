# Shogun 1.47.8

## Custom model routing

- Fixed custom routing targets so model-registry selections resolve through their exact configured provider, endpoint, and protected credential.
- Added bearer-token and access-token credential support for compatible custom providers.
- Added multiple named custom routing profiles in Katana for focused policies such as Finance and Engineering.
- Each named profile maintains an independent, strict primary and fallback model order; models outside that profile cannot be selected.
- Empty named profiles now fail closed instead of silently considering all connected models.
- Fixed the corrupted encoding in model-error messages delivered through Telegram.
