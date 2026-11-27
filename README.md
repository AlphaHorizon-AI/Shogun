# Shogun AgentFlow (Bare-Bones Edition)

A stripped-down, local-first visual AI workflow runtime containing **only** what is required to build and execute AgentFlows:

- **AgentFlow** — Visual React Flow DAG builder, scheduler, execution history, and live output viewer with 6 core node types (`Input`, `Ad-Hoc Agent`, `Logic / Decision`, `Approval Gate`, `Local Folder`, `Output`).
- **Ad-Hoc Agents in the Flow** — Inline per-node role/system prompt, task description or uploaded instruction file, expected output, routing profile override, timeouts, and retries.
- **AI Providers** — Cloud API keys (OpenAI, Anthropic, Google Gemini, OpenRouter, custom OpenAI-compatible), ChatGPT/OAuth sign-in, and local models (Ollama / LM Studio).
- **Routing Profiles** — Automatic and custom ordered model chains with fallbacks, temperature, and reasoning settings.
- **Local Folder Setup** — Configure and inspect the sandboxed local workspace directory used by `Input`, `Local Folder`, and `Output` nodes.

## Quick Start

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -e .

cd frontend
npm install
npm run build
cd ..

python -m shogun
```

Open the URL printed/launched by `python -m shogun` (default: `http://127.0.0.1:8000`).
