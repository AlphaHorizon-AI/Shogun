# Shogun on macOS

## Yellow Label and White Label

The Mac hardware requirements and launcher fixes apply to both editions. They
remain separate distributions: this repository is Yellow Label; White Label
has its own source checkout, installer, and macOS CI workflow. Neither edition
is selected or unlocked with a runtime environment variable.

Yellow Label's CI checks its fixed feature exclusions. White Label's CI checks
that Team mode, Flow Stack, Gensui integration, and the product-identity/licence
gates remain intact, as well as the common installation and runtime tests.
White Label's private repository requires an access token. Use the installer
provided with that edition; the public download installs Yellow Label.

The downloaders refuse to overwrite a detected installation of the other
edition. `SHOGUN_INSTALL_DIR` can select a separate destination. Use separate
user accounts/homes for side-by-side acceptance testing so desktop shortcuts
and default ports do not collide. This is not the Yellow-to-White upgrade flow;
that flow remains a separately controlled feature.

## Supported installation target

The native desktop installer targets Apple Silicon, including M3, M4, and M5,
with macOS 14 (Sonoma) or newer. Use a native arm64 Python; a Python running under
Rosetta resolves Intel dependencies and cannot install this application's
required PyTorch version. Python 3.12 and Node.js 22.12+ within major 22 are the
reference configuration. The installer also accepts the project's declared
Python 3.10+ and Node.js `>=22.12 <25` ranges, but not every interpreter version
has been tested with every future dependency release.

The OS minimum follows [Playwright's system requirements](https://playwright.dev/python/docs/intro).
Shogun requires `torch>=2.4`; [PyTorch ended Intel macOS wheels after 2.2.x](https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690).
Intel Macs should use [Shogun Server mode](docker.md) with Docker instead of
the native desktop installer. Server mode cannot control the host desktop.

## Install and launch

Install Python and Node.js first. With an existing Homebrew installation:

```bash
brew install python@3.12 node@22
export PATH="$(brew --prefix node@22)/bin:$PATH"
python3.12 -c 'import platform; print(platform.machine())'
node --version
bash ~/Downloads/Shogun-Install.command
```

The architecture command must print `arm64`. Run Terminal without Rosetta.
The installer does not install Homebrew, Python, or Node.js itself. It searches
for versioned Python executables and the usual Homebrew installation directories.
An explicit interpreter can be selected with
`PYTHON_CMD=/absolute/path/to/python3.12 bash ~/Downloads/Shogun-Install.command`.

Browser downloads generally do not carry executable permissions. Launch the
download with `bash` as above. The generated Desktop `Shogun.app` contains an
executable `.command` launcher and opens Terminal for later launches. The app
bundle is not signed or notarized; Finder and macOS privacy prompts still need
manual verification on a real Mac. Do not disable Gatekeeper to install Shogun.

The installer stops when dependency installation, Chromium installation,
database bootstrap, or frontend building fails. Review the terminal error,
correct its cause, then rerun the installer. An existing unusable `venv` must be
moved aside before retrying. Application data and the environment's credentials
are separate from the virtual environment.

For unattended installation from a source checkout:

```bash
bash install.sh --telemetry=off --ronin=off --no-start
bash start.sh
```

Use `--ronin=on` to install optional desktop-control dependencies. Redirected
input defaults to declining optional Ronin installation and telemetry. Both
the standalone downloader and `install.sh` accept these options. The first
interactive launch uses the same restart supervisor as later launches.

## Feature scope

| Capability | macOS status |
| --- | --- |
| Tenshu, setup, API, SQLite, scheduling and configured model providers | Native Python/browser implementation; native CI includes startup and setup smoke tests. Provider calls require separate credentials and service access. |
| Embedded Qdrant and semantic memory | arm64 dependencies resolve; native CI checks real embedding, write, search and reopen. Initial model download requires internet access. |
| Mado browser automation | Playwright Chromium; the native CI also checks the setup UI in WebKit. WebKit testing does not replace a Safari application check. |
| Ronin screenshots, mouse and keyboard | Optional dependencies plus macOS permissions; requires interactive validation, including Retina scaling and multiple monitors. |
| Ronin window listing/focus, application launch/close, UI control inspection | Not implemented by the current Mac adapter. Installing dependencies does not add these capabilities. |
| Office document file editing | Cross-platform libraries are installed through the `office` extra. |
| Live Office App Mode / COM / Outlook automation | Windows-only. The detector reports App Mode unavailable on macOS. |
| Built-in Windows OCR integration | Unavailable on macOS; ordinary PDF text extraction is separate. |

For Ronin, grant the launching terminal **Accessibility** and **Screen Recording**
permissions under System Settings → Privacy & Security. macOS may also request
Input Monitoring or Automation permission. Dependency detection alone cannot
prove that permissions have been granted. Restart the launching terminal after
changing permissions if macOS requests it.

## Automated and manual verification

The `macOS compatibility` workflow installs the application into a directory
containing spaces on `macos-14` and `macos-26` arm64 runners, using the actual
installer, Python 3.12, and Node.js 22. It runs:

- The real application/Office/Ronin dependency installation and `pip check`.
- Shell regression tests with macOS `/bin/bash`, BSD utilities, and isolated
  command substitutes for installer failure scenarios and downloader upgrades.
- Real Chromium and WebKit setup-page checks, database startup, embedding and
  embedded-memory persistence, and an API-requested supervised restart.
- Backend launcher, environment protection, updates, and Ronin security tests.
- Edition identity and edition-specific feature boundaries.

This workflow must pass for the exact revision being released. Adding the
workflow does not establish that it has run. GitHub's standard arm64 runners
use M1 hardware according to [the runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
so successful CI is architecture coverage, not an M3/M4/M5 hardware certification.

Before declaring a release verified on M3–M5, use a disposable Mac installation
and record chip, OS, Python architecture/version, Node version, and source SHA:

1. Download and run the installer in a fresh user account; complete setup and
   make a chat request with a configured provider.
2. Launch `Shogun.app` from Finder, including after reboot with a minimal PATH.
3. Check the Tenshu in Safari and Chrome, reload setup, and confirm credentials
   disappear from the URL fragment without appearing in logs.
4. Store and retrieve memory; create and reopen an Office document file.
5. If Ronin is required, check denied permissions first, grant the necessary
   permissions, then test screenshots and a harmless mouse/keyboard action on
   Retina and external displays. Confirm the documented unsupported actions.
6. Apply an update, request restart, and verify setup, credentials, databases,
   and memories survive. Do this only in the disposable installation.
7. Run `bash /absolute/path/to/Shogun/uninstall.sh` from an unrelated directory;
   confirm only the disposable installation and shortcut are removed.

The native smoke tests are deliberately opt-in because they start and restart
the installed application. Run them only in the disposable installation after
installing pytest and Playwright WebKit:

```bash
venv/bin/python -m pip install pytest pytest-asyncio
venv/bin/python -m playwright install webkit
SHOGUN_MACOS_SMOKE=1 venv/bin/python -m pytest -q tests/test_macos_native.py
```
