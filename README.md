<p align="center">
  <img src="Assets/shogun-afm-logo.png" alt="Shogun AFM Logo" width="200" />
</p>

<h1 align="center">🏯 Shogun AFM — Your AI Command Center</h1>

<p align="center">
  <strong>Shogun is an AI agent control plane with persistent memory, multi-agent orchestration, and full governance. Build, manage, and evolve agents via GUI—no terminal required. Powered by Qdrant, skill systems, and secure, inspectable autonomy.</strong>
</p>

<p align="center">
  <a href="https://github.com/AlphaHorizon-AI/Shogun/releases/latest"><img src="https://img.shields.io/github/v/release/AlphaHorizon-AI/Shogun?style=flat-square&label=Version&color=d4a017" alt="Version" /></a>
  <a href="#-14-supported-languages"><img src="https://img.shields.io/badge/Languages-14-blue?style=flat-square" alt="Languages" /></a>
  <a href="#-install-shogun-one-click"><img src="https://img.shields.io/badge/Install-One_Click-green?style=flat-square" alt="Install" /></a>
  <a href="https://www.youtube.com/@ShogunAIAgents"><img src="https://img.shields.io/badge/YouTube-Video_Guides-red?style=flat-square&logo=youtube" alt="YouTube" /></a>
</p>

---

## 📺 Complete Video Guide

New to Shogun? **Watch the full walkthrough series** on our YouTube channel — from installation to advanced workflows:

### **[▶️ youtube.com/@ShogunAIAgents](https://www.youtube.com/@ShogunAIAgents)**

---

## ⚡ Why Shogun?

Most AI tools give you a chat box. Shogun gives you an **entire operating system for AI agents**.

| | What You Get |
|---|---|
| 🧠 **Multi-Model Intelligence** | Connect OpenAI, Anthropic, Google, Perplexity, OpenRouter, or run local models via Ollama — all at once. Intelligent routing sends each task to the right brain. |
| 🥷 **Agent Fleet** | Deploy specialized sub-agents (Samurai) for research, coding, analysis, or any domain. The Shogun orchestrates them automatically. |
| 📚 **Persistent Memory** | Your AI remembers everything across sessions. Semantic search, salience scoring, and automatic memory consolidation — powered by embedded Qdrant. |
| 🌐 **Browser Automation (Mado)** | Your AI can browse the web, extract content, and take screenshots — all controlled through a secure Playwright layer. |
| 📧 **Email & Calendar** | Connect your IMAP/SMTP inbox and CalDAV calendar. Your Shogun can read, compose, and send emails — and manage your schedule. |
| 💬 **Telegram Integration** | Talk to your AI from your phone. Full streaming responses with live typing indicators. |
| 🔗 **Agent-to-Agent (Nexus)** | Connect multiple Shogun instances via peer-to-peer Nexus, **and** send/receive tasks with external enterprise agents (Microsoft 365, Salesforce, Google, ServiceNow) through the bidirectional Nexus External Gateway. Inbound A2A + outbound dispatch with governed security. |
| 🔄 **Visual Workflow Builder** | Design multi-step AI pipelines with a drag-and-drop canvas. Chain agents, approvals, logic gates, and browser actions into executable flows. |
| 📜 **Constitutional Governance** | Write YAML rules your AI can never break. Version-controlled, auditable, with enforcement modes (Block / Warn / Audit). |
| 🛡️ **5-Tier Security + ToolGate** | From SHRINE (zero-trust) to RONIN (unrestricted). **ToolGate** runtime enforcement inspects every tool call — risk-scoring parameters, blocking destructive patterns, and **human-in-the-loop confirmation modals** for high-risk operations (with 60s auto-deny timeout). **Quarantine** soft-deletes files to `.shogun_trash/` for 30-day recovery. **Prompt injection containment** wraps external content with boundary markers. Emergency kill switch (Harakiri) freezes everything instantly. |
| 📊 **Compliance Dashboard** | NIS2, SOC2, and EU AI Act-ready logging. Tamper-proof HMAC audit chain, trace reconstruction, and compliance exports. |
| 🎓 **4,000+ Skills (Dojo)** | Browse and certify your agents on specialized skills from [OpenClaw College](https://www.openclawcollege.com). Training literature, exams, and achievement tracking. |
| 🔄 **Self-Improvement (Bushido)** | Automated reflection cycles where the AI analyzes its own performance and generates optimization insights. |
| 📐 **Flow Stacking** | Chain multiple Agent Flows into governed, long-horizon execution pipelines with planning, checkpoints, verification gates, retries, and artifact capture — all managed by the Stack Orchestrator. |
| 📸 **Visual Intake** | Secure image upload and vision analysis — SHA-256 dedup, EXIF stripping, OCR, AI describe/inspect/compare, thumbnail generation, and governed cloud vs local vision permissions. |
| 💻 **VS Code IDE Mode** | Connect your VS Code editor via a governed WebSocket bridge. File reads, patches, terminal commands, Git operations, and diagnostics — all enforced server-side with posture gates, workspace boundaries, and protected file patterns. |
| 🧭 **Model Router** | Provider-agnostic, task-aware model selection with 5 built-in routing profiles (ultra_economy → premium). Model registry, routing decisions, usage telemetry, and per-task complexity scoring. |
| 🥋 **Active Skills** | Runtime skill retrieval from the Dojo — automatic selection, policy gating, LLM context injection, and outcome tracking. Skills are live during agent execution, not just catalog entries. |
| 📊 **Skill Trajectory Capture** | Structured evidence collection for every skill invocation — episodes, tool links, verification links, outcome scores, and improvement candidates for continuous skill optimization. |
| 🖥️ **Ronin Desktop Control** | Full desktop automation — screenshots, mouse, keyboard, window management, app trust levels, and Komainu guardian system. Requires the highest security tier. |
| 🔬 **ALE Benchmark** | Headless Agent-Level Evaluation harness for benchmarking Shogun in governed conditions — task validation, subprocess execution, trajectory/artifact export, and secret redaction. |
| 🧬 **SkillOpt** | Automated skill optimization pipeline — version management, training runs, candidate generation, validation scoring, and governed promotion/rejection. Evolve your skills through data-driven feedback loops. |
| 💾 **Backup & Auto-Updates** | Scheduled backups with configurable retention. One-click updates that preserve all your data and settings. |
| 🌍 **14 Languages** | The entire interface is fully translated. Switch anytime from the dashboard. |
| 🏗️ **Setup Wizard** | 8-step guided onboarding gets you operational in minutes. |

**No cloud account needed. No Docker required. Everything runs locally.**

---

## 🎖️ Gensui — Agent Fleet Management

<p align="center">
  <img src="Assets/shogun-afm-logo.png" alt="Shogun AFM Logo" width="200" />
</p>

<p align="center">
  <strong>Shogun AFM (Agent Fleet Management)</strong><br/>
  A dedicated central command platform for managing, monitoring, and securing fleets of Shogun AI agents across your organization.
</p>

When you move beyond a single Shogun instance, **Gensui** becomes your command-and-control hub. It provides real-time visibility into every agent in your fleet — whether that's 3 machines in a startup or 500+ across a global enterprise.

### What Gensui Does

| Capability | Description |
|---|---|
| 📡 **Real-Time Fleet Dashboard** | Live status of every enrolled Shogun instance — online/offline state, samurai count, active workflows, and version info. |
| 🗺️ **Interactive Network Topology** | Visual SVG map of your entire agent fleet with pan/zoom, hub-and-spoke layout, nexus peer connections, and **external enterprise agents** shown as diamond-shaped nodes with platform-specific colors. |
| 🔍 **LAN Network Scanner** | One-click scan of your local network to discover Shogun instances. Detects enrolled agents, unenrolled (rogue) agents, and unknown services on port 8000. |
| ⚠️ **Rogue Agent Detection** | Instantly spot unauthorized Shogun instances running on your network — critical for security compliance and preventing shadow AI. |
| 🎟️ **Enrollment Token System** | Generate secure enrollment tokens for new Shogun instances. Approve/reject enrollment requests with optional labels. **Revoke tokens** instantly to prevent unauthorized enrollments. |
| 🏷️ **Group Management** | Organize agents into logical groups (by team, environment, region). Apply policies and postures at the group level. |
| 🛡️ **Security Posture Management** | Full CRUD for security postures — create custom postures, edit built-in ones, delete custom postures. 14 permission flags + per-tool overrides (allow/confirm/block). Pushed to fleet members automatically. |
| 💀 **Remote Harakiri** | Emergency kill switch — instantly freeze any agent (soft freeze, hard stop, network isolate, or full terminate) from the Gensui dashboard. |
| 📋 **Centralized Audit Log** | Tamper-proof HMAC-chained audit trail across all managed agents. NIS2/SOC2/EU AI Act compliant. |
| 📊 **Fleet Audit Dashboard** | Multi-instance audit analytics with per-member breakdown, telemetry analytics (severity/category/event type), NIS2/SOC2/EU AI Act compliance reports, HMAC chain verification, and CSV export for SIEM integration. |
| 🔑 **Enterprise Identity** | Service accounts with API key management (create/rotate/revoke) for CI/CD and SIEM integrations. SSO/OIDC provider configuration (Keycloak, Auth0, Okta, Azure AD) with auto-provisioning, role mapping, and domain allowlisting. |
| 🔒 **Admin Authentication** | JWT-based admin portal with role-based access control (Owner, Admin, Auditor, Operator). Machine auth via `X-API-Key` header. |

### Install Gensui (One Click)

Download **one file** for your platform, double-click it, and you're done:

| Platform | Download | Instructions |
|----------|----------|-------------|
| **🪟 Windows** | [⬇️ **Gensui-Install.bat**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Install.bat) | **Click to download** → Double-click the file |
| **🍎 macOS** | [⬇️ **Gensui-Install.command**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Install.command) | **Click to download** → Double-click the file |
| **🐳 Docker (Server)** | [⬇️ **Gensui-Docker-Install.sh**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Docker-Install.sh) | **Click to download** → `bash Gensui-Docker-Install.sh` |
| **🪟 Docker (Windows)** | [⬇️ **Gensui-Docker-Install.bat**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Gensui-Docker-Install.bat) | **Click to download** → Double-click the file |

### Deployment Options (Advanced)

Gensui runs independently from Shogun instances and can also be deployed manually via Docker if you prefer not to use the one-click scripts:

| Deployment | Command | Best For |
|---|---|---|
| **🪟 Windows Desktop** | Double-click `gensui/install.bat` | Personal fleet on a Windows machine |
| **🍎 macOS / Linux Desktop** | `./gensui/install.sh` | Personal fleet on Mac or Linux |
| **🐳 Docker (Server)** | `docker compose up` | Production server, always-on |
| **🐳 Docker + TLS** | `docker compose --profile server up` | Production with Nginx reverse proxy, HTTPS, rate limiting |

<details>
<summary><strong>Quick Start — Local Install</strong></summary>

```bash
# Clone the repo
git clone https://github.com/AlphaHorizon-AI/Shogun.git
cd Shogun/gensui

# Windows
install.bat

# macOS / Linux
chmod +x install.sh && ./install.sh
```

Gensui starts at **http://localhost:8787**. Default credentials: `admin@gensui.local` / `changeme`.

</details>

<details>
<summary><strong>Quick Start — Manual Docker Server</strong></summary>

```bash
cd Shogun/gensui

# Setup config
cp .env.example .env
# Edit .env and change GENSUI_JWT_SECRET to a random 64-char string

# Basic (no TLS)
docker compose up -d

# Production with TLS (place certs in ./certs/gensui.crt and ./certs/gensui.key)
docker compose --profile server up -d
```

Includes Nginx reverse proxy with:
- TLS 1.2/1.3 termination
- Rate limiting (30 req/s API, 5 req/min auth)
- Security headers (HSTS, X-Frame-Options, CSP)
- Health checks

</details>

### How It Works

```
┌─────────────────────────────────────────────────┐
│                    GENSUI                       │
│              Agent Fleet Manager                │
│                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│   │ Dashboard │  │ Network  │  │ Enrollment│    │
│   │          │  │ Topology │  │ & Tokens  │    │
│   └──────────┘  └──────────┘  └──────────┘    │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│   │  Groups  │  │ Security │  │  Harakiri │    │
│   │          │  │ Postures │  │ Kill Switch│    │
│   └──────────┘  └──────────┘  └──────────┘    │
└────────────────────┬────────────────────────────┘
                     │ Heartbeat Protocol
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
    │ Shogun  │ │ Shogun  │ │ Shogun  │
    │ Alpha   │ │ Bravo   │ │ Charlie │
    │ (prod)  │ │ (prod)  │ │ (stage) │
    └────┬────┘ └────┬────┘ └─────────┘
         │           │
         └─── Nexus ─┘
        (peer-to-peer)
```

Each Shogun instance sends periodic heartbeats to Gensui with status, metrics, and version info. Gensui cross-references these against its enrollment database to classify every agent as enrolled, unenrolled, or unknown — providing instant visibility into your fleet's security posture.

---

## 🛡️ Safety & Security Architecture

Shogun implements a **6-phase security architecture** designed for NIS2, SOC 2, and EU AI Act compliance. Security decisions flow from Gensui (fleet-wide policy) down to each Shogun instance (runtime enforcement).

### Phase 1: ToolGate — Runtime Tool Enforcement

Every tool call passes through **ToolGate** before execution. It evaluates each call against the active security posture and returns one of three verdicts:

| Verdict | Behavior |
|---------|----------|
| ✅ `allow` | Tool executes immediately |
| ⚠️ `confirm` | **Human-in-the-loop** — shows a confirmation modal. User must approve/deny within 60s (auto-deny on timeout) |
| 🚫 `block` | Tool call is rejected. Reason logged to immutable audit chain |

**Evaluation order:** Tool-specific override → Permission flag check → Default allow.

**14 Permission Flags:** `allow_external_models`, `allow_local_models`, `allow_tool_execution`, `allow_mado`, `allow_memory_write`, `allow_memory_read`, `allow_agent_flow`, `allow_nexus`, `allow_samurai_delegation`, `allow_scheduled_triggers`, `allow_autonomous_loops`, `allow_external_web`, `allow_file_write`, `allow_external_api`.

### Phase 2: Quarantine — Soft-Delete Recovery

File deletions go to `.shogun_trash/` instead of permanent delete. Each entry stores: original path, timestamp, actor, size, and reason. Files can be restored or auto-purged after configurable retention (default: 30 days).

### Phase 3: Prompt Injection Containment

External content (web scrapes, emails, API responses) is automatically wrapped with `⚠ UNTRUSTED EXTERNAL DATA` boundary markers before entering the system prompt context. This prevents adversarial instructions embedded in external content from hijacking the AI agent.

### Phase 4: Gensui → Shogun Posture Push

When Gensui administrators modify security postures, updates are pushed to connected Shogun instances via the heartbeat protocol. **Scope hierarchy:** Individual posture > Group posture > Default fleet posture.

### Phase 5: Fleet Audit Dashboard

Multi-instance audit analytics with 5 tabs: Overview (fleet statistics, HMAC chain verification), Per-Member (audit/telemetry per instance), Telemetry (severity/category/event type breakdown), Compliance (NIS2/SOC2/EU AI Act report), and Raw Log (full audit trail with CSV export up to 50K entries).

### Phase 6: Enterprise Identity

SPIFFE/SPIRE trust domains, OIDC SSO (Keycloak, Auth0, Okta, Azure AD), and service accounts with API key management (create/rotate/revoke). Machine auth via `X-API-Key` header with rate limiting.

### Immutable Audit Chain

All security events are dual-written: **Layer 1** (operational SQLite, 90-day retention) for fast queries, and **Layer 2** (append-only HMAC-SHA256 chain, 7-year retention) for compliance. No updates, no deletes — tamper-evident by design.

### Built-in Security Postures

| Posture | Level | Description |
|---------|-------|-------------|
| PERMISSIVE | L5 | All flags enabled, no restrictions |
| STANDARD | L10 | Default — production-ready |
| RESTRICTED | L50 | External access disabled |
| LOCKDOWN | L90 | Most flags disabled |
| PARANOID | L100 | Maximum restriction |

---

## 🔗 Nexus External Gateway — Enterprise Agent Interoperability

Shogun isn't limited to its own agent ecosystem. The **Nexus External Gateway** lets enterprise agents from other platforms — Microsoft 365 Copilot agents, Salesforce Einstein agents, Google Vertex agents, ServiceNow virtual agents — send tasks directly into Shogun for execution, all governed by the same security policies as internal operations.

This is **not** about replacing enterprise agents. It's about letting Shogun serve as an independent execution and orchestration layer that works *alongside* them.

### Three Operating Modes

| Mode | Description |
|------|-------------|
| 🏯 **Standalone** | Shogun runs independently with local agents, models, browser control, and memory. No external connectivity needed. |
| 🔗 **Enterprise-Connected** | External enterprise agents submit tasks via A2A, webhooks, or MCP. Shogun executes and returns results. |
| 🛡️ **Governed Hybrid** | Both modes combined, with Gensui enforcing security postures, platform allowlists, and real-time policy checks on every inbound task. |

### How It Works

```
                     ┌─────────────────────────────────────┐
                     │    External Enterprise Agents        │
                     │  (M365 · Salesforce · Google · SNow) │
                     └────────────────┬────────────────────┘
                                      │ A2A / Webhook / MCP
                                      ▼
                     ┌────────────────────────────────────┐
                     │     Nexus External Gateway          │
                     │  auth_handler → request_handler     │
                     └────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    ┌──────────────────┐  ┌───────────────────────┐  ┌──────────────┐
    │   Policy Hooks   │  │   Capability Router   │  │ Audit Logger │
    │ Gensui posture + │  │  Match capability     │  │ L1 + L2      │
    │ platform rules   │  │  → best agent         │  │ dual write   │
    └────────┬─────────┘  └──────────┬────────────┘  └──────────────┘
             │                       │
             │ allowed?              ▼
             │              ┌──────────────────┐
             │              │  Internal Shogun │
             │              │    Adapter        │
             │              │  (LLM execution) │
             │              └────────┬─────────┘
             │                       │
             ▼                       ▼
    ┌──────────────┐      ┌──────────────────┐
    │   BLOCKED    │      │    COMPLETED     │
    │  (response)  │      │   (result sent   │
    │              │      │    via callback)  │
    └──────────────┘      └──────────────────┘
```

### Task Lifecycle

Every external task follows a strict 7-step execution pipeline:

1. **Authenticate** — Bearer token verified against the registered agent database
2. **Normalize** — Protocol adapter (A2A/Webhook/MCP) maps the payload to a standard `NexusTask`
3. **Persist** — Task saved to database with status `pending`
4. **Policy Check** — Platform allowlists, Gensui posture, and hardcoded blocks evaluated
5. **Route** — Capability registry matches the task to the best internal Shogun/Samurai agent
6. **Execute** — Internal adapter runs the task against the matched agent's LLM
7. **Respond** — Result packaged and returned; optional callback URL notified

### Security Model

Security is non-negotiable for external connectivity. Every task passes through **four enforcement layers** before execution:

| Layer | What It Checks |
|-------|-----------------|
| 🔐 **Bearer Authentication** | Each registered agent receives a unique API token. Invalid tokens get a `401` immediately. |
| 🚫 **Hardcoded Blocks** | `desktop.execute`, `ronin.stop`, `ronin.harakiri`, and `unrestricted_browser_control` are **permanently blocked** for all external agents — no override possible. |
| 📋 **Platform Allowlists** | Per-platform rules define exactly which capabilities each platform can access. Microsoft 365 agents can summarize documents but cannot touch local files. Salesforce agents can prepare CRM updates but cannot browse freely. |
| 🎖️ **Gensui Posture** | If Gensui is active, its real-time security posture can disable all Nexus communication, block Mado browser sessions, block Ronin desktop automation, or restrict file writes — fleet-wide. |

### Default Capabilities

Shogun exposes 9 capabilities through the gateway. Custom capabilities can be registered at runtime.

| Capability | Category | Description |
|------------|----------|-------------|
| `document.summarize` | document | Summarize text or PDF files |
| `spreadsheet.analyze` | spreadsheet | Analyze Excel or CSV spreadsheets locally |
| `email.draft` | email | Draft client or internal emails |
| `file.analyze` | file | Inspect and extract data from local files |
| `browser.research` | browser | Browse the web to gather research on a topic |
| `crm.prepare_update` | crm | Draft customer relationship update instructions |
| `local_model.reasoning` | local_model | Run reasoning tasks against local models |
| `workflow.execute` | workflow | Execute sequential workflows / agent flows |
| `desktop.execute` | desktop | Execute local desktop tasks (**blocked by default**) |

### API Endpoints

All endpoints live under `/api/v1/nexus`:

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `POST` | `/external/register-agent` | — | Register a trusted external agent, returns API token |
| `GET` | `/external/agents` | — | List all registered external agents |
| `GET` | `/capabilities` | — | Discover available Shogun capabilities |
| `POST` | `/external/a2a/task` | Bearer | Submit a task via A2A protocol |
| `GET` | `/external/task/{id}` | Bearer | Poll task status and result |
| `POST` | `/external/task/{id}/callback` | Bearer | Receive async callback updates |

### Example: A2A Task from Microsoft 365

```json
POST /api/v1/nexus/external/a2a/task
Authorization: Bearer <agent-token>

{
  "task_id": "m365-task-001",
  "action": "document.summarize",
  "input": {
    "content": "<document text or reference>"
  },
  "source_agent_id": "copilot-agent-42",
  "source_platform": "microsoft_365",
  "callback_url": "https://m365.example.com/callbacks/shogun"
}
```

Shogun processes the task, returns a result, and optionally `POST`s the result back to the `callback_url`.

### Supported Protocols

| Protocol | Status | Adapter |
|----------|--------|---------|
| **A2A** (Agent-to-Agent) | ✅ Implemented | `a2a_adapter.py` |
| **Internal Shogun** | ✅ Implemented | `internal_shogun_adapter.py` |
| **Webhook** | 🔧 Base structure | `webhook_adapter.py` |
| **MCP** (Model Context Protocol) | 🔧 Base structure | `mcp_adapter.py` |

### Audit Trail

Every gateway operation produces dual-logged audit events:

- **Layer 1 (Operational)** — Stored in the main SQLite database with 90-day retention for dashboards and debugging
- **Layer 2 (Immutable)** — Written to the HMAC-chained append-only audit database for NIS2/SOC2/EU AI Act compliance with 7-year retention

All events include: task ID, source agent, source platform, requested action, policy decision, execution result, latency, and timestamp.

### Connecting Enterprise Agents — Step by Step

The Nexus External Gateway is a **receiving** endpoint. External enterprise agents call **into** Shogun — Shogun doesn't reach out to them. No vendor SDKs, no platform lock-in. Just standard HTTP + Bearer tokens.

```
Enterprise Agent → HTTP POST → Shogun Nexus Gateway → Policy Check → Execute → Return Result
```

Every integration follows the same 3-step pattern:

1. **Register** the external agent in Shogun → receive an API token
2. **Configure** the enterprise platform to call Shogun's `/nexus/external/a2a/task` endpoint with that token
3. **Tasks flow in** automatically — authenticated, policy-checked, routed, executed, result returned

---

<details>
<summary><strong>🔵 Example: Microsoft 365 Copilot Agent</strong></summary>

Microsoft 365 Copilot uses **custom agent actions** (API plugins) that call external REST APIs. Here's how to wire it up:

**Step 1 — Register the M365 agent in Shogun:**

```
POST http://localhost:8000/api/v1/nexus/external/register-agent

{
  "name": "M365-Copilot-Research",
  "platform": "microsoft_365",
  "endpoint_url": "https://your-m365-callback.com/webhook"
}
```

Shogun returns an **API token** — save it for the M365 side.

**Step 2 — Create a Copilot Agent Action in the M365 Admin Center:**

In **Microsoft 365 Admin Center → Copilot → Agent Builder**, create a custom action:

| Setting | Value |
|---------|-------|
| Action Type | API Plugin (OpenAPI) |
| Base URL | `https://your-shogun.example.com/api/v1/nexus` |
| Authentication | Bearer token (the token from Step 1) |
| Endpoint | `POST /external/a2a/task` |

**Step 3 — When a user asks Copilot something it delegates to Shogun:**

The Copilot agent fires an HTTP request:

```json
POST /api/v1/nexus/external/a2a/task
Authorization: Bearer <token-from-step-1>

{
  "task_id": "copilot-req-8291",
  "action": "document.summarize",
  "input": { "content": "Summarize Q2 revenue trends from the attached report..." },
  "source_agent_id": "copilot-agent-42",
  "source_platform": "microsoft_365"
}
```

Shogun verifies the token, checks platform allowlists, routes to the best agent, executes via LLM, and returns the result.

**What Microsoft 365 agents CAN access:**

| ✅ Allowed | 🚫 Blocked |
|-----------|-----------|
| `document.summarize` | `desktop.execute` |
| `spreadsheet.analyze` | `browser.login` |
| `email.draft` | `finance.portal_access` |
| `file.analyze` | `ronin.harakiri` / `ronin.stop` |

</details>

---

<details>
<summary><strong>☁️ Example: Salesforce Agentforce (Einstein)</strong></summary>

Salesforce Agentforce uses **custom actions** that call external REST APIs. Same pattern:

**Step 1 — Register the Salesforce agent in Shogun:**

```json
POST /api/v1/nexus/external/register-agent

{
  "name": "Einstein-CRM-Assistant",
  "platform": "salesforce",
  "endpoint_url": "https://your-sf-instance.my.salesforce.com/callback"
}
```

**Step 2 — In Salesforce Setup → Agentforce → Custom Actions:**

Create an **External Service** (or Apex HTTP callout) pointing to Shogun's public URL with the bearer token from Step 1.

| Setting | Value |
|---------|-------|
| External Service URL | `https://your-shogun.example.com/api/v1/nexus` |
| Auth Header | `Authorization: Bearer <token>` |
| Method | `POST` |
| Path | `/external/a2a/task` |

**Step 3 — A sales rep asks Einstein to prepare a customer summary:**

```json
POST /api/v1/nexus/external/a2a/task
Authorization: Bearer <salesforce-token>

{
  "task_id": "sf-case-44021",
  "action": "crm.prepare_update",
  "input": {
    "customer_id": "ACME-001",
    "context": "Prepare renewal talking points based on support ticket history"
  },
  "source_agent_id": "einstein-agent-7",
  "source_platform": "salesforce"
}
```

Shogun processes the task, returns the result. The Salesforce agent displays it to the sales rep inside their CRM view.

**What Salesforce agents CAN access:**

| ✅ Allowed | 🚫 Blocked |
|-----------|-----------|
| `crm.prepare_update` | `local_file_access` |
| `customer.summary` | `desktop.execute` |
| `case.analysis` | `unrestricted_browser_control` |
| `document.summarize` | `ronin.harakiri` / `ronin.stop` |

</details>

---

<details>
<summary><strong>🌐 Other Platforms (Google, ServiceNow, Custom)</strong></summary>

Any platform that can make HTTP REST calls works with the same pattern:

1. Register the agent → get a token
2. `POST /api/v1/nexus/external/a2a/task` with the token as a Bearer header
3. Receive the result in the HTTP response, or via a callback URL

**Google Vertex AI Agents** — Use the "OpenAPI Tool" action type to call Shogun's endpoint.

**ServiceNow Virtual Agent** — Use a "REST Message" Integration Hub action pointing to Shogun.

**Custom / In-house agents** — Any HTTP client works. `curl`, Python `requests`, Node.js `fetch` — just POST to the endpoint with a valid token.

```bash
# Quick test from the command line
curl -X POST https://your-shogun.example.com/api/v1/nexus/external/a2a/task \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-001",
    "action": "document.summarize",
    "input": {"content": "Summarize this quarterly report..."},
    "source_agent_id": "my-agent",
    "source_platform": "custom"
  }'
```

</details>

---

### Networking: Making Shogun Reachable

Shogun runs on `localhost:8000` by default. For enterprise agents to reach it over the network, you need to expose it. Choose the approach that fits your environment:

| Approach | Complexity | Best For |
|----------|------------|----------|
| 🐳 **Gensui Docker + TLS** | Low | Production — already built into the project with Nginx, TLS 1.2/1.3, and rate limiting |
| 🔒 **Reverse proxy** (Nginx / Caddy) | Medium | Self-hosted production with custom domain |
| 🚇 **Tunnel** (ngrok / Cloudflare Tunnel) | Low | Development and testing |
| 🏢 **VPN / private network** | Medium | On-prem enterprise with no public exposure |

> ⚠️ **Security note:** Never expose the gateway without TLS and rate limiting in production. The Gensui Docker TLS profile handles this out of the box.

---

## 📐 Flow Stacking & Stack Orchestrator

Shogun's **Stack Orchestrator** is the persistent, governed runtime layer above the Agent Flow engine. While individual Agent Flows handle single-pipeline execution, Flow Stacking chains multiple flows into **long-horizon execution pipelines** with full lifecycle management.

### What the Stack Orchestrator Does

| Capability | Description |
|---|---|
| 🎯 **Goal-Driven Planning** | Describe an objective in natural language — the planner builds an execution plan from available flows |
| 💾 **Durable Checkpoints** | Context summaries and state snapshots after each step — resume where you left off after restarts |
| ✅ **Verification Gates** | Independent quality checks (deterministic + semantic model judging) before proceeding to the next phase |
| 🔄 **Governed Retries** | Automatic failure categorization (permission, runtime, verification, tool/flow) with configurable retry policies |
| ⏸️ **Pause / Resume** | Pause a running stack mid-execution and resume later — checkpoints preserve full context |
| 📦 **Artifact Capture** | Automatically collect and catalog outputs from each phase (files, reports, analysis results) |
| 📊 **Execution Trees** | Visual tree representation of multi-step execution with per-node status, timing, and model usage |
| 🧠 **Context Compaction** | Budget-aware context management for hand-offs between phases — keeps token usage under control |
| 🛡️ **Approval Policies** | Configurable human-in-the-loop gates — approve the plan, approve individual steps, or run fully autonomous |

### Four Operating Modes

| Mode | Description |
|------|-------------|
| `goal_driven` | Describe what you want — the planner selects and sequences flows automatically |
| `selected_stack` | Pick a specific Flow Stack to execute with governed lifecycle |
| `template` | Instantiate a stack from a reusable template |
| `benchmark` | Headless execution for ALE benchmark harness integration |

### API Endpoints

All endpoints live under `/api/v1/stacks/orchestrator`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/create` | Create a new stack run |
| `GET` | `/` | List all stack runs |
| `GET` | `/{id}` | Get run with steps |
| `GET` | `/{id}/tree` | Execution tree view |
| `GET` | `/{id}/checkpoints` | List checkpoints |
| `GET` | `/{id}/artifacts` | List artifacts |
| `GET` | `/{id}/verifications` | List verifications |
| `GET` | `/{id}/summary` | Final summary |
| `POST` | `/{id}/plan-decision` | Approve or reject the plan |
| `POST` | `/{id}/step-decision` | Approve or reject a step |
| `POST` | `/{id}/start` | Start execution |
| `POST` | `/{id}/pause` | Pause execution |
| `POST` | `/{id}/resume` | Resume from checkpoint |
| `POST` | `/{id}/cancel` | Cancel execution |
| `POST` | `/{id}/recover` | Recover from failure |

### Governed Workflow Permissions

The security posture system enforces workflow permissions at both the capability and per-invocation level:

| Permission | Required Posture | Controls |
|---|---|---|
| `agentflow_create` | Tactical+ | Creating and editing Agent Flows |
| `agentflow_execute` | Tactical+ | Running Agent Flows |
| `agentflow_autonomous` | Tactical+ | Autonomous flow operation |
| `flowstack_create` | Tactical+ | Creating and editing Flow Stacks |
| `flowstack_execute` | Tactical+ | Running Flow Stacks |
| `flowstack_autonomous` | Tactical+ | Autonomous stack operation |

---

## 📸 Visual Intake — Governed Image Analysis

The **Visual Intake** system provides secure, source-neutral image processing with full governance. Upload images from any source (chat, Telegram, email, browser) — Shogun normalizes, deduplicates, and analyzes them with configurable vision permissions.

### Capabilities

| Feature | Description |
|---|---|
| 📤 **Upload & Normalize** | Accept JPEG, PNG, WebP, GIF — normalize to WebP with automatic thumbnail generation |
| 🔍 **SHA-256 Dedup** | Same image uploaded twice? Reuses the existing artifact instead of duplicating |
| 🧹 **EXIF Stripping** | All EXIF metadata (GPS, camera info, timestamps) is automatically stripped for privacy |
| 🤖 **AI Describe** | Generate natural language descriptions of images using your configured vision model |
| 🔎 **AI Inspect** | Deep inspection with custom prompts — ask specific questions about image content |
| 📝 **OCR / Text Extract** | Extract text from screenshots, documents, and photos |
| ⚖️ **Compare** | Side-by-side comparison of two images with AI-generated analysis |
| 📌 **Pin** | Pin important images to prevent automatic retention expiry |
| 🔗 **Stack Attach** | Attach images as artifacts to Stack Orchestrator runs |

### API Endpoints

All endpoints live under `/api/v1/visual`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/intake` | Upload an image |
| `GET` | `/recent` | List recent images |
| `GET` | `/{id}` | Image metadata |
| `GET` | `/{id}/content` | Normalized WebP content |
| `GET` | `/{id}/thumbnail` | 640×640 thumbnail |
| `POST` | `/{id}/describe` | AI description |
| `POST` | `/{id}/inspect` | Custom prompt inspection |
| `POST` | `/{id}/extract-text` | OCR / text extraction |
| `POST` | `/compare` | Compare two images |
| `POST` | `/{id}/pin` | Pin image |
| `POST` | `/{id}/attach-to-stack/{run_id}` | Attach to stack run |
| `DELETE` | `/{id}` | Soft-delete image |

### Security

7 independent permission flags control Visual Intake behavior:

| Permission | Default | Purpose |
|---|---|---|
| `allow_image_intake` | ✅ On | Accept image uploads |
| `allow_local_vision` | ✅ On | Analyze with local models |
| `allow_cloud_vision` | ❌ Off | Analyze with cloud models (privacy-sensitive) |
| `allow_ocr` | ✅ On | Text extraction |
| `allow_attach_to_stack` | ✅ On | Link to stack runs |
| `allow_auto_memory` | ❌ Off | Auto-store analyses in memory (privacy-sensitive) |
| `allow_delete` | ✅ On | Soft-delete images |

---

## 💻 VS Code IDE Mode

The **IDE Mode** connects Shogun to your VS Code editor via a governed WebSocket bridge. Your AI agent can read files, apply patches, run terminal commands, execute Git operations, and access diagnostics — all enforced server-side with workspace boundaries and protected file patterns.

### How It Works

```
┌──────────────┐         WebSocket (localhost only)         ┌──────────────┐
│   VS Code    │ ◄──────────────────────────────────────── │   Shogun     │
│  Extension   │    One-time pairing token (SHG-*)          │  IDE Service │
│              │    File ops, terminal, git, diagnostics    │              │
└──────────────┘                                            └──────────────┘
```

### Capabilities

| Category | Operations |
|---|---|
| 📂 **File Operations** | Read, create, list, search, apply patches, delete (with automatic snapshots for rollback) |
| 💻 **Terminal** | Run approved commands (allowlisted per posture tier) |
| 🔀 **Git** | Status, diff, branch, create-branch, commit (push disabled by default) |
| 🔍 **Diagnostics** | Read VS Code errors, warnings, and info messages |
| 📋 **Editor Context** | Access currently open file, selection, and cursor position |
| ↩️ **Rollback** | Restore files to pre-edit snapshots |

### Security Model

| Layer | Enforcement |
|---|---|
| **Posture Gate** | Requires Campaign or Ronin tier + explicit `ide_enabled` flag |
| **Pairing Tokens** | `SHG-` prefixed, SHA-256 verified, 10-minute expiry, one-time use |
| **WebSocket Binding** | Localhost only (`127.0.0.1` / `::1`) — no remote connections |
| **Workspace Boundaries** | Operations restricted to approved workspace paths — path traversal blocked |
| **Protected Files** | `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`, `secrets.*` — always blocked |
| **Denied Directories** | `.ssh`, `.aws`, `.azure`, `.gnupg`, `.kube` — access forbidden |
| **Symlink Detection** | Symlinks that escape workspace boundaries are rejected |
| **Command Allowlist** | Campaign tier: `pytest`, `python`, `npm`, `npx`, `ruff`, `mypy`, `tsc`, `cargo`, `go` |
| **Git Restrictions** | Push disabled by default; mutations require Ronin + explicit approval |
| **File Snapshots** | Automatic SHA-256 snapshots before every write (rollback support) |
| **Kill Switch** | Emergency disable endpoint instantly terminates all IDE connections |

### VS Code Extension

Install the `shogun-ide-bridge` extension (`bridge/vscode/`):

| Setting | Default |
|---|---|
| `shogun.bridgeUrl` | `ws://127.0.0.1:8000/api/v1/ide/bridge` |

Commands: **Shogun: Connect**, **Shogun: Disconnect**, **Shogun: Open Dashboard**

---

## 🧭 Model Router — Intelligent Model Selection

The **Model Router** provides provider-agnostic, task-aware model selection. Instead of hardcoding which model handles each request, the router evaluates the task type, complexity, and your active routing profile to select the optimal model automatically.

### 5 Built-In Routing Profiles

| Profile | Strategy | Best For |
|---|---|---|
| `ultra_economy` | Strongly prefers local models, minimizes API calls | Cost-conscious, privacy-first |
| `economy` | Low-cost daily work, escalates only for complex tasks | General daily usage |
| `balanced` | Recommended balance of quality and cost (**default**) | Most users |
| `high_capability` | Uses stronger models earlier in the complexity curve | Development, coding |
| `premium` | Maximum quality, always picks the best available model | Critical tasks, production |

### Task Type Classification

The router classifies every request into one of 20+ task types across 5 complexity tiers:

| Tier | Example Task Types |
|---|---|
| **Simple** | `simple_chat`, `classification`, `extraction`, `memory_write` |
| **Moderate** | `summarization`, `productivity_task`, `browser_task`, `skill_selection` |
| **Complex** | `planning`, `coding_plan`, `coding_edit`, `stack_planning` |
| **Critical** | `complex_reasoning`, `test_failure_analysis`, `self_verification` |
| **Vision** | `visual_understanding`, `screenshot_analysis`, `photo_understanding` |

### API Endpoints

All endpoints live under `/api/v1/models`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/routing/profiles` | List all routing profiles |
| `GET` | `/routing/profiles/active` | Get active profile |
| `POST` | `/routing/profiles/active` | Set active profile |
| `GET` | `/registry` | List model registry |
| `POST` | `/registry` | Add model to registry |
| `POST` | `/registry/{id}/test` | Test model connection |
| `POST` | `/route` | Route a task (persisted) |
| `POST` | `/route/preview` | Preview routing (no persist) |
| `GET` | `/routing/decisions` | List routing decisions |
| `GET` | `/usage/summary` | Usage summary |
| `GET` | `/routing/task-types` | List known task types |

---

## 🖥️ Ronin — Desktop Automation

**Ronin** gives your AI agent full desktop control — screenshots, mouse clicks, keyboard input, window management, and application trust levels. It operates under the strictest security tier and includes the **Komainu** guardian system for continuous monitoring.

### Capabilities

| Feature | Description |
|---|---|
| 📸 **Screenshots** | Capture full-desktop or window-specific screenshots |
| 🖱️ **Mouse Control** | Click, drag, scroll at specific coordinates |
| ⌨️ **Keyboard Input** | Type text, press hotkeys, send key combinations |
| 🪟 **Window Management** | List windows, focus by title, manage window states |
| 🏷️ **App Trust Levels** | Classify applications as trusted, restricted, sensitive, or forbidden |
| 🐕 **Komainu Guardian** | Continuous monitoring system — watches for anomalies during desktop sessions |

### API Endpoints

All endpoints live under `/api/v1/ronin`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/status` | Ronin system status |
| `POST` | `/sessions` | Create desktop session |
| `GET` | `/sessions` | List sessions |
| `POST` | `/execute` | Execute Ronin action |
| `POST` | `/desktop/enable` | Enable desktop control |
| `POST` | `/desktop/disable` | Disable desktop control |
| `POST` | `/desktop/screenshot` | Take screenshot |
| `GET` | `/desktop/state` | Current desktop state |
| `GET` | `/desktop/windows` | List windows |
| `POST` | `/desktop/click` | Mouse click |
| `POST` | `/desktop/type` | Keyboard input |
| `POST` | `/desktop/hotkey` | Hotkey press |
| `POST` | `/desktop/scroll` | Scroll |
| `POST` | `/desktop/drag` | Drag operation |
| `POST` | `/desktop/focus-window` | Focus window by title |

### Security

Ronin requires the **highest security tier** (Ronin posture) and an explicit confirmation string to enable:

| Control | Description |
|---|---|
| **Posture Requirement** | Ronin tier only — not available in Campaign, Tactical, or lower |
| **Explicit Confirmation** | Must type `ENABLE RONIN DESKTOP CONTROL` to activate |
| **10+ Permission Flags** | `ronin_screenshots_enabled`, `ronin_mouse_enabled`, `ronin_keyboard_enabled`, `ronin_window_management_enabled`, `ronin_native_apps_enabled`, `ronin_require_verification`, `ronin_require_high_risk_approval`, `ronin_block_critical_actions`, `ronin_visible_indicator` |
| **Protected Applications** | Configurable list of apps that cannot be interacted with |
| **ToolGate Risk Rating** | `desktop_click` and `desktop_type` rated **high** risk — triggers confirmation modals |

---

## 🔬 ALE Benchmark Mode

The **ALE (Agent-Level Evaluation)** benchmark harness lets you evaluate Shogun's performance in headless, governed conditions. Run standardized tasks, capture trajectories and artifacts, and export results — all integrated with the Stack Orchestrator.

### API Endpoints

All endpoints live under `/api/v1/benchmark`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/config` | Benchmark configuration |
| `PATCH` | `/config` | Update benchmark settings |
| `GET` | `/runs` | List benchmark runs |
| `GET` | `/runs/{id}` | Get specific run |
| `POST` | `/validate` | Validate task + sandbox config |
| `POST` | `/runs` | Start benchmark run (subprocess) |
| `POST` | `/runs/{id}/cancel` | Cancel active run |

### Configuration

| Setting | Default | Description |
|---|---|---|
| `enabled` | `false` | Enable benchmark mode |
| `default_posture` | `tactical` | Security posture for benchmark runs |
| `default_model_profile` | `balanced` | Model routing profile |
| `max_runtime_minutes` | `30` | Maximum runtime per run |
| `trajectory_export` | `true` | Export execution trajectories |
| `artifact_export` | `true` | Export captured artifacts |
| `redact_secrets` | `true` | Redact secrets from exports |

---

## 🧬 SkillOpt — Automated Skill Optimization

**SkillOpt** closes the loop between skill usage and skill improvement. It captures how skills perform at runtime, generates optimized candidate versions, validates them against held-out tasks, and promotes successful candidates — all governed by the same security model as the rest of Shogun.

### The Optimization Pipeline

```
 Usage Events ──► Training Run ──► Candidate Generation ──► Validation ──► Promote / Reject
      │                                                          │               │
      └── Telemetry from Active Skill usage                      │               └── New active version
                                                                 └── Safety checks + scoring
```

### API Endpoints

All endpoints live under `/api/v1/skillopt`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/runs` | Start a training run |
| `GET` | `/skills/{id}/versions` | List all versions for a skill |
| `POST` | `/candidates/{id}/promote` | Promote candidate to active version |
| `POST` | `/candidates/{id}/reject` | Reject candidate with reason |
| `GET` | `/skills/{id}/usage` | Get usage events for a skill |

### Data Model

| Table | Purpose |
|---|---|
| `skill_versions` | Immutable snapshots — version number, content hash, validation score, status (candidate/active/retired) |
| `skill_usage_events` | Runtime telemetry — model, posture, task type, outcome, score |
| `skillopt_training_runs` | Parent record for optimization jobs — base version, optimizer model, target profile |
| `skillopt_candidates` | Proposed modifications — content diff, validation score, promotion/rejection status |
| `skillopt_eval_results` | Per-task validation outcomes — baseline vs candidate score, safety status, runtime cost |

### Katana Integration

The SkillOpt dashboard is accessible from the **Katana** configuration page as a dedicated tab. It provides:
- Real-time tracking of active optimization runs
- Interactive diff viewer for comparing candidate vs baseline content
- One-click promote/reject controls with loading states
- Metrics for average improvement scores

---

## 🥋 Active Skills & Trajectory Capture

### Active Skills at Runtime

When a Shogun agent processes a request, the **Active Skill** system automatically:

1. **Retrieves** relevant skills from the Dojo catalog based on the task context
2. **Gates** each skill against the current security posture and exam requirements
3. **Injects** skill content into the LLM context (advisory or context_block mode)
4. **Tracks** the outcome (success, partial, failed, not_used, blocked)

### Configuration

| Setting | Default | Description |
|---|---|---|
| `active_skill_usage_enabled` | `true` | Enable active skill retrieval |
| `active_skill_auto_activate` | `true` | Auto-activate matching skills |
| `active_skill_max_per_run` | `5` | Max skills per execution run |
| `active_skill_max_per_step` | `3` | Max skills per step |
| `active_skill_max_total_context_tokens` | `2500` | Total token budget for injected skills |
| `active_skill_require_exam_pass` | `true` | Only use skills the agent has passed exams for |
| `active_skill_preserve_during_compaction` | `true` | Keep skill content during context compaction |

### Trajectory Capture

Every skill invocation generates a structured evidence trail across 7 tables:

| Component | What It Records |
|---|---|
| **Candidate Retrievals** | Which skills were considered, their relevance scores, which were selected/rejected |
| **Episodes** | Full skill usage lifecycle — selection reason, injection mode, status, timestamps |
| **Trajectories** | Outcome with conservative scoring — contribution level and final score |
| **Tool Links** | Which tools were called during skill usage, with input/output summaries |
| **Verification Links** | How the outcome was verified — type, expected vs observed result |
| **Outcome Scores** | Per-skill scoring with deterministic scoring method and explanation |
| **Improvement Candidates** | Suggested improvements — issue type, observed problem, suggested fix, priority |

All trajectory data is **secret-redacted** (API keys, tokens, private keys, bearer tokens, env values are automatically stripped).

---

## 🛡️ Mado Browser Hardening

The Mado browser automation layer received significant hardening with governed reliability features:

| Feature | Description |
|---|---|
| **Profile Isolation** | Persistent browser profiles with exclusive per-profile locks and path sanitization |
| **Runtime State Tracking** | Per-session state: status, current URL, title, last action, retry count, timeline (last 200 events) |
| **Permission Guard** | Comprehensive checks: posture, kill switch, headless/visible mode, downloads/uploads, form operations, domain allowlist/blocklist |
| **Artifact Management** | JSON artifact storage with SHA-256 file descriptions, per-session listing |
| **Structured Observation** | JavaScript observer scripts for page content extraction + screenshot capture |
| **Page Verification** | Automated verification of page state after actions |
| **Secret Redaction** | All events and artifacts are scrubbed of sensitive data |
| **Domain Controls** | URL allowlist/blocklist enforcement, scheme restriction (http/https/file only) |
| **Upload/Download Validation** | Upload paths restricted to workspace; download paths restricted to Mado directory |

---

## 🚀 Install Shogun (One Click)

**Prerequisites:** [Python 3.10+](https://www.python.org/downloads/) and [Node.js v18+](https://nodejs.org/en/download) must be installed.

Download **one file** for your platform, double-click it, and you're done:

| Platform | Download | Instructions |
|----------|----------|-------------|
| **🪟 Windows** | [⬇️ **Shogun-Install.bat**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Install.bat) | **Click to download** → Double-click the file |
| **🍎 macOS** | [⬇️ **Shogun-Install.command**](https://github.com/AlphaHorizon-AI/Shogun/releases/latest/download/Shogun-Install.command) | **Click to download** → Double-click the file |

**The installer automatically:**
- ✅ Downloads Shogun from GitHub (no git needed)
- ✅ Sets up the Python environment and installs all dependencies
- ✅ Builds the interface
- ✅ Creates a **desktop shortcut** (⚔️ Shogun — The Tenshu)
- ✅ Opens the **Setup Wizard** in your browser

### What Happens Next

1. **Your browser opens** to the Setup Wizard
2. Walk through **8 guided steps**: pick your language (14 available), name your AI agent, connect a model provider (OpenAI, Anthropic, Google, etc.), and configure governance rules
3. **Done** — you're taken to The Tenshu, your mission control dashboard
4. **Next time**, just click the ⚔️ **Shogun** shortcut on your Desktop

> 📺 **Need help?** Watch the [complete setup walkthrough on YouTube](https://www.youtube.com/@ShogunAIAgents).

---

## 🖥️ After Installation

### Launching Shogun

| Platform | How to launch |
|----------|--------------| 
| **Windows** | Double-click **"Shogun — The Tenshu"** on your Desktop |
| **macOS** | Double-click **Shogun.app** on your Desktop |
| **Linux** | Double-click **shogun.desktop** on your Desktop |

Shogun opens at **http://localhost:8000** in your default browser. *(If your OS blocks the popup, type that address manually.)*

### 🧹 Uninstalling Shogun

Open your `Shogun` installation folder and run the uninstaller:

| Platform | How to uninstall |
|----------|-----------------| 
| **Windows** | Double-click **`uninstall.bat`** |
| **macOS/Linux** | Run **`./uninstall.sh`** |

*Removes the virtual environment, databases, memories, desktop shortcut, and the folder itself.*

---

## 🏗️ The Shogun Architecture

Shogun is built around a clear hierarchy of interconnected systems:

| Module | What It Does |
|--------|-------------|
| ⚔️ **Shogun** | Your primary AI orchestrator — the central brain that coordinates everything |
| 🥷 **Samurai** | Specialized sub-agents for domain-specific tasks (research, coding, analysis) |
| 🏯 **The Tenshu** | Mission control dashboard — the React UI you interact with |
| 💬 **Comms** | Direct chat with streaming responses, chat history, email client, and calendar |
| ⚔️ **The Katana** | Model providers, API tools, routing profiles, and Telegram integration |
| 📚 **Archives** | Persistent memory with semantic search, salience scoring, and vector embeddings |
| 📜 **Kaizen** | Constitutional governance — versioned YAML rules the AI must follow |
| 🔄 **Bushido** | Self-improvement engine with scheduled reflection cycles and insight generation |
| ⛩️ **The Torii** | 5-tier security gateway with fine-grained permissions and kill switch |
| 🥋 **The Dojo** | Skills system — 4,000+ certifiable capabilities from [OpenClaw College](https://www.openclawcollege.com) |
| 🪟 **Mado** | Browser automation layer — web browsing, screenshots, content extraction via Playwright |
| 🔗 **Nexus** | Agent-to-Agent collaboration — peer-to-peer shared workspaces **and** external enterprise agent gateway (A2A, Webhook, MCP) |
| 🔄 **Agent Flow** | Visual workflow builder — drag-and-drop multi-agent pipelines |
| 📐 **Stack Orchestrator** | Long-horizon Flow Stacking runtime — checkpoints, verification gates, retries, artifacts, and governed execution |
| 📸 **Visual Intake** | Secure image processing — upload, normalize, deduplicate, analyze, and govern vision operations |
| 💻 **IDE Mode** | VS Code integration via governed WebSocket bridge — file ops, terminal, Git, diagnostics |
| 🧭 **Model Router** | Task-aware, provider-agnostic model selection with routing profiles and usage telemetry |
| 🖥️ **Ronin** | Desktop automation — screenshots, mouse, keyboard, window management, with Komainu guardian |
| 🔬 **ALE Benchmark** | Headless agent evaluation harness with trajectory capture and artifact export |
| 🧬 **SkillOpt** | Automated skill optimization — versioning, training runs, candidate validation, and promotion |
| 🎖️ **Gensui** | Agent Fleet Management — central command for monitoring and securing fleets of Shogun agents |

---

## 🌍 14 Supported Languages

The entire interface — menus, labels, explainers, and system messages — is fully translated:

| | Language | Native Name | Code |
|---|----------|-------------|------|
| 🇬🇧 | English | English | `en` |
| 🇩🇪 | German | Deutsch | `de` |
| 🇮🇹 | Italian | Italiano | `it` |
| 🇫🇷 | French | Français | `fr` |
| 🇪🇸 | Spanish | Español | `es` |
| 🇵🇹 | Portuguese | Português | `pt` |
| 🇵🇱 | Polish | Polski | `pl` |
| 🇩🇰 | Danish | Dansk | `da` |
| 🇳🇴 | Norwegian | Norsk | `no` |
| 🇸🇪 | Swedish | Svenska | `sv` |
| 🇺🇦 | Ukrainian | Українська | `uk` |
| 🇨🇳 | Chinese | 中文 | `zh` |
| 🇯🇵 | Japanese | 日本語 | `ja` |
| 🇰🇷 | Korean | 한국어 | `ko` |

---

## 🧑‍💻 Developer Install (With Git)

<details>
<summary>Click to expand developer instructions</summary>

```bash
git clone https://github.com/AlphaHorizon-AI/Shogun.git
cd Shogun
```

| Platform | Command |
|----------|---------|
| **Windows** | Double-click `install.bat` |
| **macOS/Linux** | `chmod +x install.sh && ./install.sh` |

Or install manually:

```bash
python -m venv venv
source venv/bin/activate        # Linux / Mac
# venv\Scripts\activate         # Windows

pip install -e .
cd frontend && npm install && npm run build && cd ..
python -m shogun
```

**Endpoints:**
- **Tenshu UI**: http://localhost:8000/
- **Setup Wizard**: http://localhost:8000/setup
- **API Docs**: http://localhost:8000/docs
- **Reset Setup**: `POST /api/v1/setup/reset`

No Docker, no external services. SQLite + Qdrant embedded handles everything locally.

</details>

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI, SQLAlchemy 2.0 |
| Frontend | React, TypeScript, Vite |
| Database | SQLite (default) / PostgreSQL (optional) |
| Vector Memory | Qdrant (embedded) |
| Browser Automation | Playwright |
| Email | IMAP / SMTP |
| Calendar | CalDAV |
| Validation | Pydantic v2 |
| Scheduling | APScheduler |
| Embeddings | sentence-transformers |
| Fleet Management | Gensui (independent SQLite + React UI) |
| External Gateway | Nexus A2A/Webhook/MCP protocol adapters |
| Containerization | Docker, Docker Compose, Nginx |

---

## 📺 Resources

- **[YouTube — Video Guides](https://www.youtube.com/@ShogunAIAgents)** — Full walkthrough series from install to advanced
- **[OpenClaw College](https://www.openclawcollege.com)** — AI skills marketplace
- **[GitHub Releases](https://github.com/AlphaHorizon-AI/Shogun/releases)** — Download the latest version

---

## License

[Proprietary](LICENSE.md) — [AlphaHorizon AI](https://github.com/AlphaHorizon-AI)
