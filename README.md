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

If you later need to manage several Shogun installations, add **Gensui**, the optional fleet-management platform. Install Shogun first, then Gensui.

## Start here

| I want to… | Install |
|---|---|
| Run my own governed AI command center | [Shogun and The Tenshu](#install-shogun-and-the-tenshu) |
| Let one administrator serve several people through Telegram or Teams | [Shogun in Team mode](#single-user-and-team-mode) |
| Run Shogun continuously in containers on a server or NAS | [Shogun Server mode](#server-mode-docker) |
| Centrally manage multiple Shogun installations | [Gensui](#gensui--agent-fleet-management) after installing Shogun |

## Shogun and The Tenshu

**Shogun** is the primary AI agent and orchestrator. It remembers context, delegates to specialized Samurai agents, selects models, runs governed tools, and coordinates long-running work.

**The Tenshu** is Shogun's mission-control interface. It provides chat, memory, model and tool configuration, Agent Flows, Flow Stacks, security controls, audit logs, skills, integrations, and system administration without requiring terminal commands.

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

1. Language, Single-user or Team mode, and user identity
2. Local data directory
3. Shogun identity and behavior
4. Constitution and mandate
5. AI model providers
6. Model-routing profile
7. Fallback models
8. Optional Ronin desktop control
9. Security and incident-reporting information, with an explicit acknowledgement
10. Configuration review and activation

Changing the language updates translated wizard content immediately. Shogun provides
15 language packs; mandatory security and legal wording remains in canonical English
where reviewed localized wording is not yet available.

### Single-user and Team mode

Choose the operating mode during installation:

| Mode | How it works |
|---|---|
| **Single-user mode** | One Primary Admin uses Shogun and The Tenshu personally. |
| **Team mode** | One Primary Admin operates The Tenshu. Team members communicate with Shogun through Telegram or Microsoft Teams. |

In Team mode:

- The Primary Admin is the only person with platform and administrative authority.
- Any number of team members can be configured during setup.
- Each member is mapped to a Telegram or Microsoft Teams identity.
- Shogun maintains a separate identity and pinned-memory context for each member.
- Private member context is isolated and is not disclosed to other members.
- Team members cannot invoke Primary Admin-only operations such as HARAKIRI.

### Server mode (Docker)

Server mode runs Shogun and The Tenshu continuously in containers with dedicated PostgreSQL and Qdrant services. It is the recommended deployment for an always-on Team-mode installation.

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
bootstrap link (and opens it automatically on Windows). Use that link to select
Single-user or Team mode. The infrastructure credential follows `#` in the URL:
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
intentionally cannot authorize Server mode. Team members communicate through
Telegram or Microsoft Teams; they do not receive access to The Tenshu.

Privileged Gensui connection and Nexus peer-invitation actions reuse the
infrastructure authorization established by the bootstrap link for that tab.
If the tab session ends, print and open the private bootstrap link again; the
explicit token fields remain available for deliberate session reauthorization.
See the [outbound destination security guide](docs/security/outbound-destination-policy.md).

> **Secure by default:** Do not change `SHOGUN_BIND_ADDRESS` to a public interface without placing The Tenshu behind an authenticated HTTPS reverse proxy. For remote administration, prefer a VPN or SSH tunnel.

> **Important — Ronin does not work in Server mode:** A container cannot safely access the server's physical desktop. Ronin screenshots, mouse and keyboard control, native application control, and host-desktop sessions are therefore disabled and rejected by the server. Selecting the Torii posture named RONIN does not override this container boundary. Use a normal desktop installation when Ronin Desktop Control is required.

Mado browser automation still works because its managed Chromium browser runs inside the container. Agent Flows, Flow Stacking, Telegram, Teams, Nexus, memory, ToolGate, HARAKIRI, and externally hosted local-model services such as Ollama remain available.

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
| **Flow Stacking** | Chain multiple Agent Flows into one governed, long-horizon execution plan. |
| **Stack Orchestrator** | Plan and supervise Flow Stacks with checkpoints, verification gates, approval modes, retries, state recovery, execution trees, and artifact capture. |
| **Scheduled and autonomous work** | Run approved tasks on schedules or through governed autonomous loops. |
| **ALE Benchmark** | Execute headless agent evaluations with trajectory, artifact, and verification exports. |

Flow Stacking is available from **Flow Stack** in The Tenshu. A single Agent Flow handles one pipeline; a Flow Stack coordinates several flows as a persistent plan. The Stack Orchestrator can pause, resume, recover, retry, and verify that plan while retaining an auditable execution history.

### Communication and integrations

| Feature | Description |
|---|---|
| **Telegram** | Communicate with Shogun remotely with streaming responses and identity-aware Team mode. |
| **Microsoft Teams** | Connect organization members to their own governed Shogun identity and memory context. |
| **Email and calendar** | Use IMAP/SMTP mail and CalDAV calendars from the command center. |
| **Nexus** | Connect Shogun peers and external enterprise agents through A2A, webhook, and MCP adapters. |
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
| **HARAKIRI** | Fail-closed emergency stop for active Telegram, Teams, Agent Flow, Flow Stack, and approval work. |
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
| **Flow Stack** | Composition of several Agent Flows |
| **Stack Orchestrator** | Persistent planning, checkpoints, verification, retry, and recovery |
| **Mado** | Governed browser automation |
| **Ronin** | Governed desktop automation |
| **Nexus** | Shogun-to-Shogun and enterprise-agent interoperability |
| **Gensui** | Optional central fleet management for multiple Shogun installations |

## Gensui — Agent Fleet Management

Gensui is not required to run Shogun. It is a separate command-and-control platform for organizations that operate multiple Shogun installations.

Install and configure each Shogun first. Add Gensui when you need centralized fleet visibility, enrollment, security policy, audit, and emergency control.

### What Gensui provides

| Capability | Description |
|---|---|
| **Fleet dashboard** | Monitor online state, versions, agents, workflows, and health across enrolled Shogun instances. |
| **Network topology** | Visualize fleet membership, Nexus peers, and external enterprise agents. |
| **Discovery and rogue detection** | Scan the LAN for enrolled, unenrolled, and unknown Shogun services. |
| **Enrollment tokens** | Issue, approve, reject, and revoke secure enrollment credentials. |
| **Groups and posture management** | Organize instances and distribute group or instance-level security policies. |
| **Remote HARAKIRI** | Trigger the governed-operation gate and request best-effort cancellation on supported connected paths; verify external processes separately. |
| **Central audit** | Aggregate available HMAC-chained events, telemetry, governance-evidence summaries, and SIEM-ready exports. |
| **Enterprise identity configuration** | Stage reserved service-account and SSO provider records. These records are not accepted for API or SSO authentication in the current release. |

### Install Gensui

Download one installer from the [latest GitHub release](https://github.com/AlphaHorizon-AI/Shogun/releases/latest):

| Deployment | Installer | Run it |
|---|---|---|
| **Windows desktop** | [⬇️ Gensui-Install.bat](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Install.bat) | Double-click the downloaded file |
| **macOS desktop** | [⬇️ Gensui-Install.command](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Install.command) | Double-click the downloaded file |
| **Linux/macOS Docker server** | [⬇️ Gensui-Docker-Install.sh](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Docker-Install.sh) | Run `bash Gensui-Docker-Install.sh` |
| **Windows Docker server** | [⬇️ Gensui-Docker-Install.bat](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Docker-Install.bat) | Double-click the downloaded file |

Gensui opens at [http://localhost:8787](http://localhost:8787). The Docker
installers generate a random initial administrator password in the protected
`.env` file; rotate it after first login.

<details>
<summary><strong>Developer installation for Gensui</strong></summary>

```bash
git clone https://github.com/AlphaHorizon-AI/Shogun.git
cd Shogun/gensui

# Windows
install.bat

# macOS or Linux
chmod +x install.sh
./install.sh
```

For an always-on server, use the Docker Compose configuration in `gensui/`. The server profile adds Nginx, TLS termination, security headers, rate limiting, and health checks.

</details>

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
```

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
| Fleet deployment | Docker, Docker Compose, and Nginx |

## Guides and downloads

- [YouTube video guides](https://www.youtube.com/@ShogunAIAgents)
- [Latest release and installers](https://github.com/AlphaHorizon-AI/Shogun/releases/latest)
- [OpenClaw College](https://www.openclawcollege.com)
- [VS Code bridge documentation](bridge/vscode/README.md)
- [Microsoft Teams bridge documentation](bridge/teams/README.md)
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
