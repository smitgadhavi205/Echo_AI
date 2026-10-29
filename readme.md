# 🎙️ Echo AI
### The Ultimate Cross-Platform Personal Voice AI Assistant

A real-time voice AI that can hear, see, speak, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native bidirectional audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

**Echo AI** gives your desktop an intelligent presence — combining an expressive animated interface, multimodal computer control, and robust resilience when network conditions or model services fluctuate.

Say *"play the new Dune trailer"* and the video appears seamlessly in the HUD where the avatar was, muted until you ask for sound. A YouTube link, a local file, a direct URL, or just a description to search for: they all stream cleanly, and Echo AI informs you instantly before the stream buffers rather than remaining silent.

Under the hood, every one-shot Gemini call routes through a **measured model ladder**, dynamically prioritizing response latency and availability. When a model encounters quota limits, timeouts, or transient outages, Echo AI immediately transitions to the next available tier with intelligent cooldown tracking so your workflow is never interrupted.

Everything Echo AI ships with is purpose-built to **drive the computer** — applications, local files, browser automation, desktop window management, camera and screen vision.

It is not just an assistant — it is an autonomous extension of your digital workspace.

---

## 🚀 Capabilities

### Core Features

| Feature | Description |
|---|---|
| 🧑‍🎤 **Holographic Avatar** | An animated human head in the HUD — real facial geometry, lit and drawn in software, requiring no dedicated GPU or heavy game engines |
| 👄 **Real Lip-Sync** | ~50 mouth shapes per second derived from audio formants **and** phoneme transcriptions — real closures, spreads, and rounds |
| 🌍 **Universal Articulation** | Mouth shapes derived via Unicode reduction, providing consistent visual speech across Latin, Cyrillic, and Greek scripts |
| 🙂 **Facial Dynamics** | Brow tracking, natural saccadic eye movement, organic blinking, and head nodding synchronized with stressed syllables |
| 😐 **Face as Status** | Looks away while thinking, makes direct eye contact when listening, lowers lids during sleep, and glances toward active content |
| 🎚️ **Push-to-Talk** | Hold **Ctrl+Space** to open the microphone — closed the rest of the time. Global hook on Windows, window-scoped on macOS/Linux |
| 🔇 **Self-Echo Guard** | Eliminates audio feedback loops: Echo AI recognizes its own speech playback and drops it without muting the user |
| 🪪 **Runtime Self-Knowledge** | Operating system, installed tools, display metrics, and system limits are discovered dynamically at startup |
| 🎙️ **Wake Word** | Fully local **"Hey Echo"** detection (`openwakeword`) — stays dormant until called, auto-sleeps after idle timeout, zero audio streamed while sleeping |
| ⚡ **Instant Acknowledgment** | Generates immediate, localized conversational acknowledgments when initiating longer tasks |
| 🚀 **Low Latency Engine** | Powered by **Gemini 2.5 / 3.1 Flash Live** for ultra-fast time-to-first-word voice interaction |
| 🧩 **Self-Describing Skills** | Modular skill architecture in `actions/` — each skill exports a `TOOL` schema and handler, auto-registered on boot |
| 🧠 **Recallable Two-Tier Memory** | No arbitrary size limits — the active prompt carries recent context and a category index, while on-demand recall queries local history |
| 👁️ **Memory Management Panel** | Inspect every fact Echo AI has retained, filter by category or date, and delete items with a single click |
| ↩️ **System Undo** | Reverses recent filesystem and system setting changes (file moves, copies, renames, deletions, volume, brightness) |
| ⚠️ **Explicit Confirmation Gate** | Irreversible operations (system shutdown, reboot, network disconnect) require user confirmation in the UI |
| 🎧 **Audio Device Management** | Intelligent detection, filtering, deduplication, and testing of system microphones and output speakers |
| 🔗 **Session Continuity** | Seamless reconnection handling — connection dropouts or audio device changes preserve conversation context |
| 🧩 **Plugin Extensibility** | Drop custom single-file scripts into `plugins/` for automatic capability discovery |
| 📺 **Integrated HUD Media Player** | Direct playback of YouTube streams, web video URLs, and local files directly within the UI frame |
| 🪜 **Intelligent Model Ladder** | Tiered fallback across Gemini models with automated cooldowns for rate limits (429) and outages (503/504) |
| 🎨 **Dynamic Live Theming** | Live interface recoloring with dynamic palette generation, hue rotation, and synchronized avatar tinting |
| 〰️ **Audio Visualizer** | Smooth sinusoidal waveform reacting to live input and synthetic voice output |
| 🎙️ **Multi-Voice Selector** | Switch between native Gemini voices on the fly without restarting the application |
| ♾️ **Long-Running Sessions** | Sliding-window conversational compression for extended multi-hour sessions |
| 🖥️ **Full System Control** | Launch desktop software, adjust hardware volume/brightness, toggle system settings, and automate hotkeys |
| 👁️ **Visual Awareness** | Full screen capture and webcam inputs forwarded into the multimodal context pipeline |
| ⌨️ **Hybrid Input** | Instant switching between hands-free voice and interactive keyboard commands |
| 🌅 **Morning Briefing** | Boot-time briefing covering time, previous session context, system health, and headlines |
| 🔔 **Proactive Notifications** | Context-sensitive background check-ins tailored to user schedule and recent tasks |
| 📊 **Hardware Telemetry** | Real-time monitoring of CPU, RAM, GPU load, and thermal sensors with speech warnings |
| 🌤️ **Live Weather** | Geolocation and weather forecast integration personalized from saved preferences |
| 🔍 **Multi-Engine Search** | Integrated web research supporting news, product comparisons, technical queries, and general web browsing |
| ⏰ **System Reminders** | OS-native scheduled background notifications via Task Scheduler, Launchd, or systemd |
| 📂 **Document Processing** | Analyze, summarize, and query text, markdown, PDF, and code files |
| 🌐 **Browser Automation** | Voice-driven tab control, navigation, page reading, and interaction via Playwright |
| 📨 **Communication Tools** | Quick composition and dispatch across supported messaging platforms |
| 📱 **Remote Web Dashboard** | Secure local network control panel accessible from mobile devices via QR code |
| ⚡ **Auto-Start Integration** | Native system startup configuration for seamless launch on OS boot |
| 📋 **Smart Clipboard** | Quick actions (summarize, translate, fix, explain) on clipboard text changes |

---

## 🏛️ Architecture Highlights

### 📺 HUD Video Playback
The user interface central display alternates between the holographic avatar, live camera feeds, and video playback:
- **Zero overlapping windows**: Embedded rendering via `QGraphicsVideoItem` maintains overlay HUD elements and notifications on top.
- **Dual stream synchronization**: Automatically extracts and syncs separate video and high-fidelity audio streams for YouTube links.
- **Language-first track selection**: Detects original source language tracks to avoid unwanted dub tracks.
- **Intelligent mic muting**: Automatically suspends microphone listening during active video playback with sound to prevent self-triggering.

### 🪜 Dynamic Model Ladder
Every non-streaming Gemini call passes through `core/gemini.py`, utilizing a resilient priority ladder:
1. `gemini-2.5-flash` / `gemini-3.1-flash-lite`
2. `gemini-2.5-flash-lite`
3. Secondary fallback tiers with automatic health checks

**Cooldown Matrix:**
- **HTTP 429 (Rate Limit / Quota)**: Cooled for 5 minutes.
- **HTTP 503 / 504 / Deadline Exceeded**: Cooled for 30 minutes to bypass transient outages.
- **HTTP 404 / Auth Failure**: Cooled for 6 hours.

### 🧠 Two-Tier Memory System
1. **Prompt Memory Core**: Maintains user identity, essential preferences, and a compressed key index of secondary knowledge within strict token limits.
2. **On-Demand Local Recall**: The `recall_memory` action conducts instant local lookups across `memory/long_term.json` when specific background facts are needed.

### ↩️ Reversible Actions & Safety Gate
- **Safe Undo Stack**: Actions modifying the disk or settings register precise inversion handlers (file restoration, directory pruning, brightness reset).
- **Hardware & Power Confirmation**: Potentially disruptive actions (`shutdown`, `restart`, `toggle_wifi`) trigger an explicit interactive confirmation banner on the HUD before executing.

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/smitgadhavi205/Echo_AI.git
cd Echo_AI
```

### 2. Run Setup
```bash
python setup.py
```
> `setup.py` detects your operating system, validates Python (3.11 – 3.13), installs matching requirements, and downloads Playwright browser binaries.

### 3. Launch Echo AI
```bash
python main.py
```
> On initial launch, Echo AI prompts for your Gemini API key (stored locally in `config/api_keys.json`).

---

## 📋 System Requirements

| Requirement | Details |
|---|---|
| **Operating System** | Windows 10/11, macOS (12+), or Linux (Ubuntu 22.04+, Fedora, Arch) |
| **Python** | Python 3.11, 3.12, or 3.13 |
| **Microphone & Audio** | Functional microphone and speakers/headphones |
| **API Key** | Free or paid Google Gemini API key from [Google AI Studio](https://aistudio.google.com/) |
| **Hardware / GPU** | **No dedicated GPU required**. Interface, 3D face mesh, and video rendering run fully in optimized software mode |
| **Wake Word (Optional)** | One-click download from **⚙ → WAKE WORD** in the UI (`openwakeword`, lightweight local engine) |

---

## 🗂️ Project Structure

```
Echo_AI/
├── main.py                   # Central application loop: Gemini Live stream, audio pipeline, tool routing
├── ui.py                     # PyQt6 HUD interface: avatar renderer, waveforms, system drawers, video player
├── setup.py                  # Cross-platform dependency & browser automation setup script
├── requirements.txt          # Python dependency specifications with OS markers
├── .gitignore                # Protects credentials, local certificates, and personal memories
│
├── actions/                  # Modular system tools (auto-discovered on startup)
│   ├── browser_control.py    # Web browser navigation and interaction
│   ├── computer_control.py   # Keyboard shortcuts, mouse input, window management
│   ├── computer_settings.py  # OS volume, brightness, power, and connectivity
│   ├── desktop.py            # Desktop items and taskbar operations
│   ├── dev_agent.py          # Code execution and developer agent tools
│   ├── file_controller.py    # File system management (create, move, delete, organize)
│   ├── file_processor.py     # Document reading and summarization
│   ├── open_app.py           # Cross-platform application launcher
│   ├── proactive.py          # Proactive background check-ins and contextual triggers
│   ├── reminder.py           # OS-native task scheduler notifications
│   ├── screen_processor.py   # Screen capture and webcam vision pipeline
│   ├── send_message.py       # Messaging platform bridges
│   ├── system_monitor.py     # Hardware telemetry (CPU, GPU, RAM, temps)
│   ├── video_player.py       # HUD media playback controller
│   ├── weather_report.py     # Real-time weather reporting
│   └── web_search.py         # Gemini Grounded + DuckDuckGo search integration
│
├── core/                     # Internal engine infrastructure
│   ├── action_loader.py      # Dynamic tool registration and validation
│   ├── audio_devices.py      # Audio endpoint discovery, benchmarking, and selection
│   ├── avatar.py             # 3D software avatar rendering engine
│   ├── avatar_mesh.py        # Facial landmark definitions and vertex deformations
│   ├── confirm.py            # UI confirmation gate for critical operations
│   ├── echo.py               # Self-echo suppression and acoustic guard
│   ├── face_model.obj        # 3D canonical face geometry
│   ├── gemini.py             # Model ladder, quota manager, and fallback dispatcher
│   ├── hotkey.py             # Global and windowed Push-to-Talk hooks
│   ├── installer.py          # Dynamic package installer for optional add-ons
│   ├── prompt.txt            # Base system persona and runtime instructions
│   ├── undo.py               # Action inversion and undo stack manager
│   ├── viseme.py             # Phoneme-to-viseme mapping for facial lip-sync
│   └── wake_word.py          # Offline wake word listener ("Hey Echo")
│
├── memory/                   # State and configuration persistence
│   ├── config_manager.py     # Handles api_keys.json, user preferences, and theme state
│   ├── memory_manager.py     # Persistent memory storage (long_term.json)
│   └── long_term.json        # Saved user context and learned facts (local only)
│
├── dashboard/                # Mobile companion interface
│   ├── server.py             # Local HTTPS dashboard server
│   └── static/               # Web client assets for mobile browser control
│
├── plugins/                  # User plugins directory
│   └── _template.py          # Template for authoring custom skills
│
└── config/                   # Configuration artifacts
    ├── echo.ico              # Application branding icon
    ├── api_keys.json         # Local API credentials (git-ignored)
    └── certs/                # Local self-signed TLS certificates (git-ignored)
```

---

## 🔒 Privacy & Local Sovereignty

- **100% Local Storage**: Your configurations (`config/api_keys.json`), encryption keys (`config/certs/`), and memory history (`memory/long_term.json`) reside strictly on your local machine.
- **Zero Third-Party Telemetry**: Echo AI has no central telemetry server, analytics tracking, or proprietary account requirements.
- **Scoped Network Traffic**: The only external connections made are direct calls to the Google Gemini API for conversational inference, DuckDuckGo for search queries when requested, and direct video streaming upon user instruction.
- **Git Shield**: `.gitignore` is pre-configured to strictly prevent inadvertent commits of keys, tokens, sessions, or personal databases.

---

## 📄 License

This project is licensed for personal and non-commercial use under the **[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/)** license.
