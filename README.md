# 🤖 MBU Examly Browser Automation Agent

A general-purpose, self-healing browser automation agent built on top of [browser-use](https://github.com/browser-use/browser-use) and Google Gemini. The agent is specifically optimized to navigate the MBU Examly platform, answer MCQs from a curated answer bank, solve competitive coding/DSA questions using a high-fidelity coding brain, and bypass bot detection mechanisms.

---

## ✨ Key Capabilities

1. **Intelligent Navigation & Answering**: Automatically log in, navigate to the target course, locate the assessment, and complete both MCQ and coding sections.
2. **Two-Brain Architecture**:
   - **Navigation Brain**: Powered by `gemini-3.1-flash-lite` for fast, lightweight page structure analysis, clicks, and scrolling.
   - **Coding Brain**: Powered by `gemini-2.5-flash` (with thinking/reasoning enabled) to solve complex Data Structures & Algorithms (DSA) problems with optimal time/space complexity.
3. **Simulated Human Typing (Anti-Bot Evasion)**: 
   - Never uses instant text filling, value insertion, or clipboard pasting (`.fill()` or `.setValue()`).
   - Simulates realistic human typing character-by-character with a delay of 100ms and random variation (80ms to 120ms) on all text inputs, textareas, and code editors.
   - Programmatically disables Monaco editor auto-closing brackets/quotes before typing to prevent syntax corruption.
4. **Terminal-Based AI Consultant**: Replaces heavy web dashboards with a lightweight console fallback. When the agent is stuck, it prompts the console; typing `ai` automatically consults an independent Gemini API assistant via `ai_consultant.py` to get an actionable solution.
5. **Multi-Account Pipeline (`multi_run.py`)**:
   - **Account 1 (Sacrifice/Discovery)**: Solves the test from scratch and saves all Q&A to the answer bank.
   - **AI Review Phase**: Automatically fixes any wrong solutions in the bank using the upgraded coding model.
   - **Accounts 2+ (Perfect Runs)**: Replays the corrected answer bank using a zero-API Playwright script (`replay_direct.py`) for 100% accuracy and speed.

---

## 🛠️ Architecture & Core Components

```
┌───────────────────────────────────────────────────────────────┐
│                        main.py (Wizard)                       │
│  - Wizard setup & arguments                                   │
│  - Navigation Brain: gemini-3.1-flash-lite                    │
│  - Fallback/Recovery Brain: gemini-2.5-flash                 │
└────────────┬──────────────────────────┬──────────────────────┘
             │                          │
  ┌──────────▼───────────┐   ┌─────────▼──────────┐
  │  code_solver.py      │   │  ai_consultant.py  │
  │  (Coding Brain)      │   │  (Terminal Help)   │
  │  Model: gemini-2.5-  │   │  Gemini API →      │
  │  flash (with thinking)│  │  terminal response │
  └──────────┬───────────┘   └────────────────────┘
             │
  ┌──────────▼───────────┐   ┌────────────────────┐
  │  replay_direct.py    │   │  session_store.py  │
  │  (Zero-API Replay)   │   │  (Local JSON)      │
  └──────────────────────┘   └────────────────────┘
```

- **`stealth.py`**: Configures Playwright args (`AutomationControlled`, custom User-Agent, ghost cursor paths) to defeat bot-detection signatures.
- **`visual_grounding.py`**: Utilizes Gemini Vision to locate elements on screenshots and click coordinates if CSS selectors break.
- **`prompts/`**: GSD-inspired modular prompt system to prevent context rot:
  - `examly_base.py`: Concise setup instructions.
  - `examly_coding.py`: Step-by-step DSA solver workflow.
  - `examly_mcq.py`: MCQ answering strategy.
  - `examly_submit.py`: Safety submission gates.
  - `troubleshooting.py`: Modal dismissals, force-enabling buttons, and evasion.

---

## ⚙️ Setup & Installation

### Requirements
- **Python 3.13+**
- **[uv](https://github.com/astral-sh/uv)** (recommended package manager)

### 1. Clone & Sync
```bash
git clone https://github.com/sameerreddy789/Browser_Automation.git
cd Browser_Automation
uv sync
```

### 2. Configure Environment
Create a `.env` file in the root directory (see `.env.example`):
```env
# Required Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Course details
COURSE_NAME="2028_MBU_60 days Skill Development Assessment Course"

# Saved accounts for sequential runs
ACCOUNT_1_EMAIL=sacrifice_account@mbu.asia
ACCOUNT_1_PASS=password123

ACCOUNT_2_EMAIL=main_account@mbu.asia
ACCOUNT_2_PASS=password456

ACCOUNT_3_EMAIL=third_account@mbu.asia
ACCOUNT_3_PASS=password789
```

---

## 💻 Usage

### A. Run Single Account (Normal Mode)
Launch the interactive wizard to enter credentials, date, and task:
```bash
uv run python main.py
```

Or run directly with arguments:
```bash
uv run python main.py --email "user@mbu.asia" --password "pass123" --task "Take the Day 18 Assessment"
```

### B. Run Multi-Account Pipeline
Sequentially run the sacrifice account, trigger AI answer-bank fixes, and replay on the remaining accounts:
```bash
uv run python multi_run.py --day "Day 18"
```
*Use `--skip-sacrifice` if you already ran the first account and have the JSON answer bank ready.*

### C. Direct Zero-API Replay
To replay on an account without consuming any LLM API quota:
```bash
uv run python replay_direct.py --email "user@mbu.asia" --password "pass123" --day "Day 18"
```

---

## 📂 Repository Structure

```
Browser_Automation/
├── main.py                    # Core agent entry, wizard, custom actions, LLM loop
├── code_solver.py             # Competitive coding solver (gemini-2.5-flash + thinking)
├── ai_consultant.py           # Console consultation model for stuck/blocker queries
├── multi_run.py               # Orchestrator for multi-account test pipelines
├── replay_direct.py           # Standalone pure Playwright replay player (Zero-API)
├── session_store.py           # Local session backup/restore (JSON cookies)
├── stealth.py                 # Anti-bot configurations (arguments, ghost cursor)
├── visual_grounding.py        # Gemini Vision coordinates finder & descriptor
├── prompts/                   # GSD-inspired modular system prompts
│   ├── __init__.py
│   ├── examly_base.py
│   ├── examly_coding.py
│   ├── examly_mcq.py
│   ├── examly_submit.py
│   └── troubleshooting.py
├── proxy/                     # Proxy rotator pool with alive tracking
├── parsers/                   # crawlee structural text extractor
├── pyproject.toml             # Project dependencies (uv managed)
└── .gitignore                 # Excludes .env, sessions/, and local run logs
```

---

## 📄 License
[Apache 2.0](LICENSE)
