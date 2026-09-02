<p align="center">
  <img src="Assets/shogun-afm-logo.png" alt="Shogun AFM logo" width="200" />
</p>

<h1 align="center">🏯 Shogun — Your AI Command Center</h1>

<p align="center">
  <strong>A local-first AI agent operating system with persistent memory, multi-agent orchestration, visual workflows, and governed autonomy.</strong>
</p>

<p align="center">
  <a href="https://github.com/AlphaHorizon-AI/Shogun/releases/latest"><img src="https://img.shields.io/github/v/release/AlphaHorizon-AI/Shogun?style=flat-square&label=Version&color=d4a017" alt="Latest version" /></a>
  <a href="#languages"><img src="https://img.shields.io/badge/Languages-15-blue?style=flat-square" alt="15 languages" /></a>
  <a href="#install-shogun-and-the-tenshu"><img src="https://img.shields.io/badge/Install-One_Click-green?style=flat-square" alt="One-click installation" /></a>
  <a href="https://www.youtube.com/@ShogunAIAgents"><img src="https://img.shields.io/badge/YouTube-Video_Guides-red?style=flat-square&logo=youtube" alt="YouTube video guides" /></a>
</p>

Shogun is the AI orchestrator. **The Tenshu** is the browser-based command center where you configure, supervise, and communicate with it. Everything runs locally by default; no Docker or Shogun cloud account is required.

Shogun does not bundle, train, or supply a proprietary LLM or foundation model. Shogun is not itself an LLM, foundation model, or general-purpose AI (GPAI) model. It is model-agnostic orchestration software that connects to supported local or cloud-hosted models selected and configured by the deploying organisation. The organisation remains responsible for its model and provider selection, credentials, data, permissions, use cases, human oversight, infrastructure, and output validation. Third-party providers remain responsible for their respective models and services under their terms and applicable law; Alpha Horizon remains responsible for official Shogun code, defaults, connectors, and documentation to the extent required by applicable law.

## Start here

| I want to… | Install |
|---|---|
| Run my own governed AI command center | [Shogun and The Tenshu](#install-shogun-and-the-tenshu) |
| Run Shogun continuously in containers on a server or NAS | [Shogun Server mode](#server-mode-docker) |

## Shogun and The Tenshu

**Shogun** is the primary AI agent and orchestrator. It remembers context, delegates to specialized Samurai agents, selects models, runs governed tools, and coordinates long-running work.

**The Tenshu** is Shogun's mission-control interface. It provides chat, memory, model and tool configuration, Agent Flows, security controls, skills, integrations, and system administration without requiring terminal commands.

### Install Shogun and The Tenshu

Download one installer from the [latest GitHub release](https://github.com/AlphaHorizon-AI/Shogun/releases/latest):

| Platform | Installer | Run it |
|---|---|---|
| **Windows** | [⬇️ Shogun-Install.bat](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Install.bat) | Double-click the downloaded file |
| **macOS** | [⬇️ Shogun-Install.command](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Install.command) | Double-click the downloaded file |

The installer downloads Shogun, creates the Python environment, installs dependencies, builds The Tenshu, creates a desktop shortcut, and opens the Setup Wizard.

On first desktop installation, Shogun generates an independent infrastructure
administrator credential in `<installation directory>/.env`. The file is
restricted to the installing Windows account plus SYSTEM and Administrators, or
mode `0600` on macOS/Linux. The launcher carries the credential to the Setup
Wizard only after `#` in the local URL; browser fragments are not sent in HTTP
requests, and The Tenshu removes the fragment before its first API request. The
credential is never included in installer telemetry or printed by the desktop
installer.

Shogun requires **Python 3.10+**. Frontend builds and CI use **Node.js 22.12+**;
`.nvmrc` and `.node-version` pin the supported major.

### Complete the Setup Wizard

The ten-step Setup Wizard guides you through:

1. Language and user identity
2. Local data directory
3. Shogun identity and behavior
4. Constitution and mandate
5. AI model providers
6. Model-routing profile
7. Fallback models
8. Optional Ronin desktop control
9. Security and incident-reporting information, with an explicit acknowledgement
10. Configuration review, bundled licence review and acceptance, then activation

Changing the language updates translated wizard content immediately. Shogun provides
15 language packs; mandatory security and legal wording remains in canonical English
where reviewed localized wording is not yet available.

### Server mode (Docker)

Server mode runs Shogun and The Tenshu continuously in containers with dedicated PostgreSQL and Qdrant services. It is the recommended deployment for an always-on installation.

**Prerequisite:** Install Docker Desktop on Windows/macOS, or Docker Engine with the Docker Compose plugin on Linux. The server installer downloads the Shogun source and builds the application image locally.

| Platform | Server installer | Run it |
|---|---|---|
| **Linux/macOS server** | [⬇️ Shogun-Server-Install.sh](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Server-Install.sh) | Run `bash Shogun-Server-Install.sh` |
| **Windows Server/Desktop** | [⬇️ Shogun-Server-Install.bat](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Server-Install.bat) | Double-click the downloaded file |

The Server installer:

- Generates independent application, vault-encryption, infrastructure-admin,
  and PostgreSQL secrets.
- Builds Shogun and The Tenshu as a non-root container.
- Starts PostgreSQL and Qdrant on an internal Docker network.
- Stores application data, memories, configuration, vault content, and logs in named volumes.
- Enables health checks and automatic restart.
- Preserves `.env.server` and Docker volumes during upgrades.
- Keeps The Tenshu bound to `127.0.0.1` by default.

After an interactive installation, the installer prints a private Primary Admin
bootstrap link (and opens it automatically on Windows). Use that link to complete
the single-user setup. The infrastructure credential follows `#` in the URL:
browser fragments are not sent in HTTP requests or referrer headers, and The
Tenshu removes it from the address bar before its first API request. It is then
kept only in that tab's `sessionStorage`.

Treat the full bootstrap link like a credential. Do not put it in a query string,
bookmark, screenshot, chat, issue, or shared log. When installer output is
redirected or running under CI, the credential-bearing link is withheld. From a
private operator terminal in the installation directory, print a fresh copy with:

```bash
docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun \
  python -m shogun.setup_link --origin http://127.0.0.1:8000
```

The bootstrap link contains the long-lived infrastructure administrator
credential and is not technically single-use; rotate
`SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN` if it is disclosed. A bare `/setup` URL
intentionally cannot authorize Server mode.

> **Secure by default:** Do not change `SHOGUN_BIND_ADDRESS` to a public interface without placing The Tenshu behind an authenticated HTTPS reverse proxy. For remote administration, prefer a VPN or SSH tunnel.

> **Important — Ronin does not work in Server mode:** A container cannot safely access the server's physical desktop. Ronin screenshots, mouse and keyboard control, native application control, and host-desktop sessions are therefore disabled and rejected by the server. Selecting the Torii posture named RONIN does not override this container boundary. Use a normal desktop installation when Ronin Desktop Control is required.

Mado browser automation still works because its managed Chromium browser runs inside the container. Agent Flows, Telegram, memory, ToolGate, HARAKIRI, and externally hosted local-model services such as Ollama remain available.

See the [Docker capability matrix and migration guide](docs/deployment/docker.md)
for the complete native-versus-headless scope.

<details>
<summary><strong>Start Server mode from a source checkout</strong></summary>

```bash
cp .env.server.example .env.server
# Replace every change-me value in .env.server.
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build

# Print the private Primary Admin bootstrap link to this terminal.
docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun \
  python -m shogun.setup_link --origin http://127.0.0.1:8000
```

Useful commands:

```bash
# Status
docker compose --env-file .env.server -f docker-compose.server.yml ps

# Shogun logs
docker compose --env-file .env.server -f docker-compose.server.yml logs -f shogun

# Stop containers without deleting persistent volumes
docker compose --env-file .env.server -f docker-compose.server.yml down
```

</details>

### Launch, update, and uninstall

| Platform | Launch Shogun |
|---|---|
| **Windows** | Double-click **Shogun — The Tenshu** on the Desktop |
| **macOS** | Open **Shogun.app** from the Desktop |
| **Linux developer install** | Open the generated `shogun.desktop` shortcut |

The launcher opens The Tenshu at [http://localhost:8000](http://localhost:8000)
with the local administrator credential in a temporary URL fragment. The
fragment is removed immediately and retained only in that browser tab's
`sessionStorage`.

Updates can be installed from The Tenshu while preserving configuration, databases, and memories. To uninstall, run `uninstall.bat` on Windows or `./uninstall.sh` on macOS/Linux from the Shogun installation directory.

> Uninstalling removes the environment, databases, memories, shortcut, and installation directory. Back up anything you need first.

## What Shogun can do

### Agents, models, and memory

| Feature | Description |
|---|---|
| **Multi-model orchestration** | Connect configured models from supported providers such as OpenAI, Anthropic, Google, Perplexity, OpenRouter, and local Ollama. |
| **Model Router** | Route each task by complexity and type using five built-in profiles, model fallbacks, and usage telemetry. |
| **Samurai agents** | Create specialized sub-agents for research, coding, analysis, and other domains. |
| **Persistent memory** | Semantic memory with salience scoring, consolidation, search, and embedded Qdrant storage. |
| **Active Skills** | Retrieve relevant skills at runtime, gate them by policy, inject them into context, and track outcomes. |
| **Dojo and OpenClaw College** | Browse, install, certify, and update thousands of agent skills. |
| **SkillOpt** | Generate, validate, compare, promote, or reject improved skill versions using captured outcomes. |

### Workflows and long-running execution

| Feature | Description |
|---|---|
| **Agent Flow** | Build visual multi-step workflows with agents, tools, approvals, conditions, and browser actions. |
| **Scheduled and autonomous work** | Run approved tasks on schedules or through governed autonomous loops. |
| **ALE Benchmark** | Execute headless agent evaluations with trajectory, artifact, and verification exports. |

### Communication and integrations

| Feature | Description |
|---|---|
| **Telegram** | Communicate with Shogun remotely with streaming responses. |
| **Email and calendar** | Use IMAP/SMTP mail and CalDAV calendars from the command center. |
| **VS Code IDE mode** | Govern file reads, patches, terminal commands, Git operations, and diagnostics through a workspace-bound bridge. |

### Browser, desktop, and visual work

| Feature | Description |
|---|---|
| **Mado browser automation** | Browse, extract content, fill forms, and capture screenshots through a secured Playwright layer. |
| **Ronin desktop control** | Govern screenshots, mouse, keyboard, windows, and application trust levels with the Komainu guardian. |
| **Visual Intake** | Normalize, deduplicate, strip EXIF data, OCR, inspect, compare, and govern uploaded images. |

### Governance, safety, and operations

| Feature | Description |
|---|---|
| **Constitution and mandate** | Define versioned rules, boundaries, and objectives that guide Shogun's behavior. |
| **Security postures** | Choose graduated security levels and fine-grained tool permissions. |
| **ToolGate** | Inspect each tool call, risk-score its parameters, and allow, confirm, or block execution. |
| **HARAKIRI** | Fail-closed emergency stop for active Telegram, Agent Flow, and approval work. |
| **Quarantine** | Soft-delete files to `.shogun_trash/` for recoverability instead of immediately destroying them. |
| **Prompt-injection containment** | Mark external content as untrusted before it enters model context. |
| **Audit and compliance support** | Maintain HMAC-chained audit records and compliance-oriented exports that support evidence collection and review; these controls do not by themselves establish conformity. |
| **Backup and updates** | Schedule backups, configure retention, and update without replacing user data. |

## Shogun architecture

| Module | Responsibility |
|---|---|
| **Shogun** | Primary AI orchestrator and central decision-maker |
| **The Tenshu** | Browser-based mission control and administration |
| **Samurai** | Specialized sub-agents |
| **Archives** | Persistent semantic memory |
| **Katana** | Models, providers, tools, routing, and integrations |
| **Kaizen** | Constitution and governance rules |
| **Bushido** | Reflection, insights, and self-improvement |
| **Torii** | Select the active built-in or custom security posture and access emergency controls |
| **ToolGate** | Create and maintain custom postures; configure and enforce runtime capability boundaries |
| **Dojo** | Skills, certification, OpenClaw College, and SkillOpt |
| **Agent Flow** | Visual workflow construction and execution |
| **Mado** | Governed browser automation |
| **Ronin** | Governed desktop automation |

## Languages

The Tenshu and Setup Wizard provide the following language packs. Coverage varies by
surface, and mandatory security or legal text can fall back to canonical English until
a reviewed translation is available.

| Language | Native name | Code |
|---|---|---|
| English | English | `en` |
| Danish | Dansk | `da` |
| German | Deutsch | `de` |
| Spanish | Español | `es` |
| French | Français | `fr` |
| Hindi | हिन्दी | `hi` |
| Italian | Italiano | `it` |
| Japanese | 日本語 | `ja` |
| Korean | 한국어 | `ko` |
| Norwegian | Norsk | `no` |
| Polish | Polski | `pl` |
| Portuguese | Português | `pt` |
| Swedish | Svenska | `sv` |
| Ukrainian | Українська | `uk` |
| Chinese | 中文 | `zh` |

## Developer installation

<details>
<summary><strong>Install Shogun from source</strong></summary>

```bash
git clone https://github.com/AlphaHorizon-AI/Shogun.git
cd Shogun
python scripts/configure_git_hooks.py
```

The repository hook performs the fast generated-catalog check before every
push. If Guide text changes, follow its repair command and commit the updated
catalogs before pushing.

| Platform | Command |
|---|---|
| **Windows** | Run `install.bat` |
| **macOS/Linux** | Run `chmod +x install.sh && ./install.sh` |

Manual installation:

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate       # Windows

pip install -e .
cd frontend
npm install
npm run build
cd ..
python -m shogun
```

| Endpoint | URL |
|---|---|
| The Tenshu | [http://localhost:8000](http://localhost:8000) |
| Setup Wizard | [http://localhost:8000/setup](http://localhost:8000/setup) |
| API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |

</details>

## Technology

| Area | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Local data | SQLite and embedded Qdrant |
| Optional database | PostgreSQL |
| Browser automation | Playwright |
| Scheduling | APScheduler |
| Email and calendar | IMAP/SMTP and CalDAV |
| Server deployment | Docker and Docker Compose |

## Guides and downloads

- [YouTube video guides](https://www.youtube.com/@ShogunAIAgents)
- [Latest release and installers](https://github.com/AlphaHorizon-AI/Shogun/releases/latest)
- [OpenClaw College](https://www.openclawcollege.com)
- [VS Code bridge documentation](bridge/vscode/README.md)
- [Security policy and private vulnerability reporting](SECURITY.md)
- [Roles, responsibilities, modified installations, and incident reporting](frontend/src/pages/Guide.tsx)

## Optional installation telemetry

Shogun's privacy-preserving installation telemetry is disabled by default. It
sends nothing until an administrator explicitly opts in, never collects
operational content or personal identity, and can be previewed, withdrawn, or
deleted from **Privacy & Telemetry** in The Tenshu. See the
[exact schema, frequency, firewall, Docker, and deletion documentation](docs/telemetry.md).

## License and distribution

Shogun is [source-available, not open source, under the Shogun AFM Free Use License](LICENSE.md). It is free to use only for the permitted purposes stated in that licence, and its redistribution, rebranding, hosted-service, production, at-scale, customer-facing, and commercial-use restrictions remain in force unless Alpha Horizon agrees otherwise in writing. The official free-use distribution is locally deployable, provided “as is,” is not a hosted SaaS service, and carries no service-level agreement unless separately agreed in writing.

[AlphaHorizon AI](https://github.com/AlphaHorizon-AI)
