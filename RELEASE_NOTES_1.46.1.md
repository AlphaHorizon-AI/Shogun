# Shogun 1.46.1

This follow-up closes the remaining authentication gaps from the red-team assessment.

- Desktop control-plane requests now require a random per-install credential, including loopback requests.
- The desktop launcher securely transfers the credential to the opened browser session and removes it from the URL immediately.
- All Gensui policy routes now require either authenticated member identity or an authorized administrator role.

## Security contributors

Thank you to [@wstlima](https://github.com/wstlima) for the security and deployment review whose accepted findings informed this release series.
