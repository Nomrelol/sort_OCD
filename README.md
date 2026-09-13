# ⚡ sort_OCD

> **AI-Powered File Organizer CLI** — Clean your folders in seconds with local or cloud AI.

![Version](https://img.shields.io/badge/version-2.0.0-brightcyan)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

sort_OCD organizes messy folders intelligently. It supports **8 sorting modes**, **3 AI backends**, a **background watcher daemon**, **duplicate detection**, and full **session-based undo** — all from one clean command.

---

## Features

| Feature | Details |
|---|---|
| **8 Sort Modes** | By type, date, size, alphabet, AI custom rule, AI auto-pilot |
| **20+ File Categories** | Images, Videos, Audio, Code, Design, 3D Models, eBooks, Fonts, and more |
| **Multi-Backend AI** | Ollama (local/free), OpenAI, Anthropic, or any custom endpoint |
| **Duplicate Detection** | SHA-256 hashing — finds exact duplicates, lets you pick what to keep |
| **Folder Watcher** | Background daemon auto-sorts your Downloads as files arrive |
| **Session Undo** | Every move logged to SQLite — reliably reversible at any time |
| **Stats Dashboard** | See all-time stats, recent sessions, most-used modes |
| **Saved Profiles** | Save your "Downloads workflow" and run it with one command |
| **Zero Setup** | Works out-of-the-box. AI is optional and auto-detected |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/sort-ocd/sort_ocd.git
cd sort_OCD

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3a. Install (base — no AI)
pip install -e .

# 3b. Install with local AI (Ollama)
pip install -e ".[ai-local]"

# 3c. Install with cloud AI (OpenAI + Anthropic)
pip install -e ".[ai-cloud]"

# 3d. Install everything
pip install -e ".[all]"
```

> **Note:** Always activate the venv first (`source venv/bin/activate`) before using `sort-ocd`.

---

## Quick Start

```bash
# Interactive mode — guided, no flags needed
sort-ocd

# Sort a folder by file type (instant, no AI)
sort-ocd sort ~/Downloads --by ext

# Sort by date (year/month/day)
sort-ocd sort ~/Downloads --by month

# Sort by file size
sort-ocd sort ~/Downloads --by size

# Alphabetical sort
sort-ocd sort ~/Downloads --by alpha
```

---

## AI Modes

```bash
# AI Auto-Pilot: AI scans files and suggests 3 structures, you pick one
sort-ocd sort ~/Downloads --by ai_auto

# AI Custom Rule: describe what you want in plain English
sort-ocd sort ~/Downloads --by ai --ai-rule "Put receipts in Finance, photos in Memories"
```

**AI Backend Setup** (one-time, optional):
```bash
sort-ocd config
```
This opens an interactive wizard where you choose Ollama, OpenAI, Anthropic, or a custom endpoint. Settings are saved to `~/.sort_ocd_config.json`.

---

## Folder Watcher

```bash
# Start watching ~/Downloads and auto-sort new files
sort-ocd watch ~/Downloads

# Watch with a specific mode
sort-ocd watch ~/Downloads --mode ext

# Stop the watcher
sort-ocd watch --stop
```

---

## Duplicate Finder

```bash
sort-ocd dupes ~/Downloads
```

Scans all files by SHA-256 hash, shows duplicate groups, and lets you interactively pick which copy to keep. Duplicates are moved to a `_DUPLICATES/` subfolder — **never deleted**.

---

## Undo

```bash
# Undo the last operation
sort-ocd undo

# Undo a specific session by ID
sort-ocd undo --session 3
```

---

## Stats Dashboard

```bash
sort-ocd stats
```

Shows total files organized, sessions history, and most-used modes.

---

## Saved Profiles

```bash
# Save your current setup as a profile
sort-ocd profile save my-downloads --mode ext

# List all profiles
sort-ocd profile list

# Run a profile on a folder
sort-ocd profile run my-downloads ~/Downloads

# Delete a profile
sort-ocd profile delete my-downloads
```

---

## All Commands

```
sort-ocd                              Interactive mode (default)
sort-ocd sort <path> [--by mode]      Sort files directly
sort-ocd watch <path>                 Start folder watcher daemon
sort-ocd watch --stop                 Stop running watcher
sort-ocd dupes <path>                 Find and handle duplicates
sort-ocd stats                        History and stats dashboard
sort-ocd config                       Configure AI backend
sort-ocd undo [--session N]           Undo last (or session N)
sort-ocd profile list                 List saved profiles
sort-ocd profile save <name>          Save a profile
sort-ocd profile run <name> <path>    Run a saved profile
sort-ocd profile delete <name>        Delete a profile
sort-ocd --version                    Show version
sort-ocd --help                       Show help
```

---

## Sorting Modes

| Mode | Flag | Description |
|---|---|---|
| File Type | `--by ext` | 20+ categories: Images, Videos, Code, Design, etc. |
| Year | `--by year` | Folders like `2024`, `2025` |
| Month | `--by month` | Folders like `2025-09 September` |
| Day | `--by day` | Folders like `2025-09-13 Saturday` |
| AI Auto | `--by ai_auto` | AI proposes 3 strategies, you pick |
| AI Custom | `--by ai` | Describe your rule in plain English |
| Size | `--by size` | Tiny / Small / Medium / Large / Huge |
| Alphabetical | `--by alpha` | A-Z folders by filename first letter |

---

## AI Backends

| Backend | Privacy | Cost | Setup |
|---|---|---|---|
| **Ollama** (default) | 🔒 100% local | Free | Install [Ollama](https://ollama.ai), pull a model |
| **OpenAI** | ☁️ Cloud | ~$0.001/file | `OPENAI_API_KEY` |
| **Anthropic** | ☁️ Cloud | ~$0.001/file | `ANTHROPIC_API_KEY` |
| **Custom endpoint** | Varies | Varies | Any OpenAI-compatible URL |

Run `sort-ocd config` to switch backends at any time.

---

## License

MIT © sort_OCD
