# HALO

Local voice AI copilot for your desktop. Offline-first. Privacy-respecting. Modular skills.
Community (Non-Commercial) Edition.

![status](https://img.shields.io/badge/status-MVP-green) ![python](https://img.shields.io/badge/Python-3.10%2B-blue) ![platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux-lightgrey) ![license](https://img.shields.io/badge/License-Non--Commercial-important)

## Overview

**Halo** is a local, hotword-activated desktop assistant designed for **hands-free control**, **quick automation**, and **privacy by default**. It runs speech-to-text and text-to-speech locally, routes intents to a modular **skills** framework, and cleanly separates third-party components so you can swap vendors or models without touching core logic.

> Community Edition ships under a **Personal Non-Commercial EULA** and includes **Porcupine** (wake word) for strictly non-commercial use. See licensing details below.

## Highlights (for reviewers)

* **Local-first voice pipeline**: Porcupine (wake word) → Whisper.cpp (STT) → skills → Piper/Edge TTS (voice out).
* **Modular skills**: drop-in Python modules with declarative metadata and typed handlers.
* **Clean architecture**: command router, intent parser, side-effect boundaries, and swappable providers (wakeword/STT/TTS/LLM).
* **Zero cloud required**: runs offline; optional online integrations are opt-in.
* **Legal hygiene**: Non-commercial EULA + Third-Party Notices, explicit Porcupine terms compliance.
* **Product thinking**: dual-track design for a future **Commercial Edition** that removes or replaces non-commercial dependencies.

## Core Features

* **Hotword activation** (“Halo”) with low latency and minimal CPU use.
* **Local speech-to-text** via Whisper.cpp (configurable models).
* **Local TTS** via Piper, or Edge TTS as a fallback.
* **Skill system**: system controls (sleep/shutdown/mute/VPN), app launchers, file ops, and room for your own skills.
* **Configurable**: hotkeys, model paths, wake words, and device routing via a single config.
* **Privacy**: no telemetry; no background network calls unless you enable integrations.

## Architecture

```
halo/
├── halo_core/
│   ├── main.py               # Entry point: event loop + orchestrator
│   ├── config.py             # Centralized config loader (env/yaml)
│   ├── voice/
│   │   ├── wakeword.py       # Porcupine adapter (swappable)
│   │   ├── recognizer.py     # Whisper.cpp wrapper
│   │   └── tts.py            # Piper / Edge TTS
│   ├── llm/
│   │   ├── local_llm.py      # Optional local LLM interface (gguf/ollama)
│   │   └── intent_parser.py  # Rules / simple classifier
│   └── skills/
│       ├── __init__.py
│       ├── system_control.py # Sleep, shutdown, volume, etc.
│       ├── apps.py           # Open/close apps and files
│       └── ...               # Add your own skills here
├── requirements.txt
├── .env.example
├── EULA.md                   # Non-Commercial EULA (Porcupine compliant)
├── THIRD_PARTY_LICENSES.txt  # Porcupine + other notices
└── README.md
```

### Data Flow

Hotword → audio capture → STT → intent parse → skill dispatch → TTS response
All components are swappable behind thin adapters.

## Getting Started

### Prerequisites

* **Python 3.10+**
* **FFmpeg** (recommended for audio I/O and TTS)
* **Models & vendor SDKs**:

  * **Whisper.cpp**: download a `.bin` model (e.g., `ggml-base.en.bin`) and place under `models/whisper/`.
  * **Piper**: download a voice model and place under `models/piper/`.
  * **Porcupine (Picovoice)**: install and configure per vendor documentation. If required, set access keys/keyword files as environment variables (see below).

> Note: This repository’s Community Edition is **non-commercial** due to Porcupine’s free-tier license. Do not monetize or deploy in business settings.

### Installation

```bash
git clone https://github.com/yourname/halo.git
cd halo
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and edit values:

```ini
# Wake word / Porcupine
PORCUPINE_ACCESS_KEY=your_key_if_required
PORCUPINE_KEYWORD_PATH=./models/porcupine/halo.ppn

# Whisper.cpp
WHISPER_MODEL_PATH=./models/whisper/ggml-base.en.bin
WHISPER_DEVICE=cpu

# TTS
TTS_ENGINE=piper         # or edge
PIPER_VOICE_PATH=./models/piper/en_US-amy-medium.onnx
AUDIO_OUTPUT_DEVICE=default

# General
WAKEWORD="halo"
LOG_LEVEL=INFO
```

You can also centralize settings in `config.py` to read from `.env` and/or `configs/halo.yaml`.

### Run

```bash
python -m halo_core.main
# or
python halo_core/main.py
```

Say “Halo” and issue a command like “open Notepad”, “mute volume”, or “shut down in five minutes”.

## Creating a Skill

Create a file under `halo/halo_core/skills/`:

```python
# halo_core/skills/example.py
from typing import Optional

NAME = "example"
INTENTS = ["say hello", "hello halo"]

def can_handle(text: str) -> bool:
    text = (text or "").lower()
    return any(k in text for k in INTENTS)

def handle(text: str) -> str:
    return "Hello from the Example skill."
```

Register it by importing in `halo_core/skills/__init__.py` or via an auto-discovery routine. The router calls `can_handle()` then `handle()` and sends the response to TTS.

## Roadmap

* **Packaging**: Windows installer, Linux AppImage, background service/tray.
* **Pluggable wakeword**: replace or remove Porcupine for a Commercial Edition.
* **UI overlay**: minimal command palette and mic HUD.
* **Skill SDK**: decorators, schema, structured responses, unit tests.
* **Provider matrix**: more STT/TTS/LLM adapters and configuration presets.

## Design Decisions

* **Local-first** to guarantee privacy and low latency.
* **Thin adapters** around vendors so replacement does not ripple across the codebase.
* **Simple intent parser first**, then optional ML classifier when data justifies it.
* **Legal separation**: third-party licenses are explicit, and Commercial Edition will remove/replace non-commercial dependencies.

## Licensing

* **Community Edition EULA**: Personal **Non-Commercial** only. See `EULA.md`.
* **Third-Party Components**: Governed by their own licenses. See `THIRD_PARTY_LICENSES.txt`.

  * Includes **Porcupine by Picovoice** under a **free non-commercial** license.
    Commercial use of Porcupine requires a **paid plan from Picovoice**.
* **No sublicensing of Porcupine** is provided. If you need commercial use, remove/replace Porcupine or obtain appropriate licenses.

**Commercial inquiries**: [jai.ver.2607@gmail.com](mailto:jai.ver.2607@gmail.com)

## Privacy

* No telemetry.
* No outbound network calls unless you explicitly enable an integration.
* Audio processing is local by default.

## Contributing

Issues and PRs are welcome for the Community Edition provided contributions respect the **Non-Commercial** licensing and include updates to `THIRD_PARTY_LICENSES.txt` when adding dependencies.

## Security

If you discover a security issue, please email **[jai.ver.2607@gmail.com](mailto:jai.ver.2607@gmail.com)** with details. Do not open public issues for sensitive vulnerabilities.

## Legal Notes

* Using Porcupine under the free plan is **non-commercial only**. Reverse engineering Porcupine, using it to build competing services, or public benchmarking without replication details may violate Picovoice terms. See `THIRD_PARTY_LICENSES.txt`.
* “Windows”, “Linux”, and other marks are property of their respective owners.