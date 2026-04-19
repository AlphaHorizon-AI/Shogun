# 🏯 Shogun — AI Agent Framework

**Your personal AI command center.** Shogun is a GUI-first AI agent framework that gives you full control over autonomous AI agents — their identity, memory, behavior, governance, and model routing — all from a beautiful mission control interface called **The Tenshu**.

No cloud account needed. Everything runs locally on your machine.

---

## 🚀 Install Shogun (One Click)

Getting started takes **two steps**: install the prerequisites, then run the installer.

### Step 1: Install Prerequisites

You need two things installed on your computer (if you don't have them already):

| Prerequisite | Download | How to check |
|--------------|----------|-------------|
| **Python 3.10+** | [python.org/downloads](https://python.org/downloads) | Open a terminal, type `python --version` |
| **Node.js 18+** | [nodejs.org](https://nodejs.org) | Open a terminal, type `node --version` |

> 💡 **Windows users:** When installing Python, make sure to check ✅ **"Add Python to PATH"** during installation.
>
> 💡 **macOS users:** You can install both via Homebrew: `brew install python node`

### Step 2: Download & Run the Installer

Download **one file** for your platform, then double-click it:

| Platform | Download | Instructions |
|----------|----------|-------------|
| **🪟 Windows** | [⬇️ **Shogun-Install.bat**](https://raw.githubusercontent.com/AlphaHorizon-AI/Shogun/main/Shogun-Install.bat) | **Right-click the link → "Save link as..."** → Double-click the downloaded file |
| **🍎 macOS** | [⬇️ **Shogun-Install.command**](https://raw.githubusercontent.com/AlphaHorizon-AI/Shogun/main/Shogun-Install.command) | **Click to download** → Double-click the file → If prompted, click "Open" |

**That's it.** The installer will:
- ✅ Download Shogun automatically (no git needed)
- ✅ Set up a Python environment
- ✅ Install all dependencies
- ✅ Build the interface
- ✅ Create a **desktop shortcut** (⚔️ Shogun — The Tenshu)
- ✅ Open the **Setup Wizard** in your browser

### What Happens Next

1. **Your browser opens** to the Setup Wizard
2. Walk through **8 guided steps**: pick your language (14 available), name your AI agent, connect a model provider (OpenAI, Anthropic, Google, etc.), and configure governance rules
3. **Done** — you're taken to The Tenshu, your mission control dashboard
4. **Next time**, just click the ⚔️ **Shogun** shortcut on your Desktop

---

## 🖥️ After Installation

### Launching Shogun

Use the desktop shortcut that was created during installation:

| Platform | How to launch |
|----------|--------------|
| **Windows** | Double-click **"Shogun — The Tenshu"** on your Desktop |
| **macOS** | Double-click **Shogun.app** on your Desktop |
| **Linux** | Double-click **shogun.desktop** on your Desktop |

Shogun opens at **http://localhost:8888** in your default browser.

### 🌍 14 Supported Languages

The entire interface — menus, labels, explainers, and system messages — is fully translated. Select your language during setup or switch anytime from the Dashboard.

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

pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m shogun
```

**Endpoints:**
- **Tenshu UI**: http://localhost:8888/
- **Setup Wizard**: http://localhost:8888/setup
- **API Docs**: http://localhost:8888/docs
- **Reset Setup**: `POST /api/v1/setup/reset`

No Docker, no external services. SQLite + Qdrant embedded handles everything locally.

</details>

---

## 🏗️ What Is Shogun?

Shogun is built around a clear hierarchy of AI concepts:

| Name | What It Does |
|------|-------------|
| ⚔️ **Shogun** | Your primary AI orchestrator — the brain |
| 🥷 **Samurai** | Specialized sub-agents for specific tasks |
| 🏯 **The Tenshu** | Mission control dashboard (the UI you see) |
| 📚 **Archives** | Structured long-term memory with semantic search |
| 📜 **Kaizen** | Constitutional governance — hard rules the AI can't break |
| 🔄 **Bushido** | Self-improvement engine with scheduled health checks |
| ⚔️ **The Katana** | Model providers, tools, and intelligent routing |
| ⛩️ **The Torii** | Security gateway and permissions |
| 🥋 **The Dojo** | Skills system — powered by [OpenClaw College](https://www.openclawcollege.com) |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI, SQLAlchemy 2.0 |
| Frontend | React, TypeScript, Vite |
| Database | SQLite (default) / PostgreSQL (optional) |
| Vector Memory | Qdrant (embedded) |
| Validation | Pydantic v2 |
| Scheduling | APScheduler |

---

## License

Proprietary — [AlphaHorizon AI](https://github.com/AlphaHorizon-AI)
