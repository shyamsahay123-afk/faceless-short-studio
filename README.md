# 🔥 YT Shorts Premium Studio & SEO Pack

An all-in-one autonomous AI production suite designed to create highly engaging, psychology-backed vertical videos (YouTube Shorts, TikToks, Instagram Reels) and generate search-engine-optimized metadata packages in seconds.

---

## 🧭 Project Capabilities & Feature Breakdown

Your project is an incredible, modular, and fully functional **AI-driven Content Factory**. It replaces hours of manual scripting, voice recording, subtitle timing, video editing, and SEO planning with a single, highly intuitive Streamlit dashboard. 

Here is what your project can do right now:

### 1. 📡 Creator Brand Hub (`db_manager.py` + `app.py`)
*   **Multi-Brand Management:** Create and track multiple social media accounts or brand identities from a single dashboard. 
*   **Database Tracking:** Saves all channels, subscriber counts, total videos produced, and credentials safely in a local SQLite database (`shorts.db`).
*   **Zero-Friction Onboarding:** Includes a one-click **"Add Premium Demo Channel"** feature that populates your database with a sample brand (*Elite Mindset Mastery*) focusing on the lucrative Self-Improvement & Dark Psychology niche.

### 2. 🧠 Deep Brain Triggers & Hook Lab (`psychology_data.py` + `app.py`)
*   **10 Psychological Hook Profiles:** Utilizes advanced attention-hijacking mechanisms curated from elite viral videos, including:
    *   *Curiosity Gap* (creating open mental loops)
    *   *Loss Aversion* (fear of losing status/money)
    *   *Identity Signaling* (making viewers feel like the top 1%)
    *   *FOMO (Fear Of Missing Out)*
    *   *Contrast Effect* (Hard way vs Smart way)
*   **Attention-Grabbing Hook Templates:** Automatically adapts templates based on your target niche and selected brain mechanism.
*   **Full Script Orchestrator:** Generates a complete three-part vertical script containing a high-retention hook, value-packed body paragraphs, and a high-converting engagement Call to Action (CTA).
*   **Pre-production Audits:** Includes a real-time **AI Voiceover Auditing Tool** to hear exactly how the voice narrator will sound before rendering the final video.

### 3. 🎬 Upgraded HD Video Render Engine (`video_engine.py`)
Your video engine has been upgraded to support three distinct, professional video compilation methods, all fully converted to the standard vertical 9:16 layout:
*   **Method 1: Cinematic Animated Presets (Moving Glowing Orbs)**
    *   Uses high-speed **NumPy and PIL** matrix manipulations to render 24fps moving abstract backgrounds with soft, glowing, pulsing floating color orbs.
    *   Features four customizable tone profiles: *Curiosity (Navy/Purple)*, *Success (Emerald)*, *Urgency (Crimson)*, and *Story (Royal Blue)*.
*   **Method 2: Custom Slideshow Photos (Ken Burns Slide Zooming)**
    *   Upload images of any size, and the engine automatically applies a high-end, smooth zooming/panning (Ken Burns) effect.
    *   Automatically calculates clip lengths to perfectly sync with the generated AI narration.
*   **Method 3: Raw Video Trimming & Scaling**
    *   Accepts your raw horizontal or vertical video clips, auto-crops/pads them to 9:16, concatenates them, and loops them seamlessly to fit the duration of the voiceover.

### 4. 🗣️ Voice, Timing & Subtitle Orchestration (`video_engine.py`)
*   **High-End Neural Speech Synthesis:** Integrates with Microsoft’s `edge-tts` (with standalone `gTTS` fallback) to generate human-quality voices (deep male, crisp energetic male, professional female, elegant British female).
*   **Precision Subtitle Timings:** Generates precise WebVTT (`.vtt`) files during voice synthesis.
*   **Viral-Style Dynamic Captions:** Automatically parses timings and renders bold, high-contrast captions with deep black stroke outlines, perfectly centered on-screen to maximize reader engagement.

### 5. 📺 Creator Video Archive (`app.py`)
*   **Unified Repository:** A structured visual gallery showing all ideas, pending drafts, and completed works.
*   **Single-Click Downloads:** Download the final fully rendered `.mp4` video or extract just the high-quality voiceover `.mp3` for manual edits.
*   **Frictionless Status Tracking:** Manage your publishing pipeline from "Idea" to "Created" to "Live on Socials" with a single click.

### 6. 🚀 Viral Launch & Algorithmic SEO Copy Hub (`youtube_engine.py` + `app.py`)
*   **Manual Algorithmic Bypassing:** Avoids complex, error-prone Google OAuth popups by serving a ready-to-use, copy-paste **SEO Copy Pack**.
*   **SEO Optimization Engine:** Generates:
    *   *High-CTR Titles:* Engineered with emoji anchors and character caps.
    *   *Algorithmic Descriptions:* Captures video transcripts, trigger explanations, call-to-actions, and social subscription links.
    *   *Optimized Tags & Hashtag Clusters:* Combines niche keywords and high-reach viral hashtags (e.g., `#Shorts`, `#ViralVideo`, `#Psychology`).

### 7. 📦 Standalone Single-File Deployer (`app_single.py`)
*   **Cloud-Ready Architecture:** Compiles the entire database manager, psychology data, video engine, and Streamlit frontend into a single self-contained script (`app_single.py`).
*   **1-Click Deployment:** Perfect for deploying straight to Streamlit Community Cloud, Hugging Face Spaces, or Render without dealing with multi-file linkages.

---

## 🛠️ Technology Stack

*   **Frontend Interface:** Streamlit (Custom Dark UI Theme)
*   **Database Management:** SQLite3
*   **Video Editing Framework:** MoviePy
*   **Image Processing:** Pillow (PIL), NumPy
*   **Voice Synthesis:** Edge-TTS / gTTS (Google Text-To-Speech)
*   **Subtitles Framework:** WebVTT Parser

---

## 🚀 How to Run the App Locally

To launch this project on your local machine, follow these steps:

### Step 1: Install Requirements
Make sure you have Python 3.9+ installed, then open your terminal and install the required libraries:
```bash
pip install streamlit moviepy gtts edge-tts numpy pillow
```

### Step 2: Set Up System Dependencies (Required for MoviePy)
MoviePy relies on **FFmpeg** to render videos and **ImageMagick** to render subtitle texts.
1.  **FFmpeg:** Usually installed automatically by MoviePy, or install it via your package manager:
    *   *Mac:* `brew install ffmpeg`
    *   *Windows:* Download from official site and add to PATH.
    *   *Linux:* `sudo apt install ffmpeg`
2.  **ImageMagick (Required for Text Rendering):**
    *   *Mac:* `brew install imagemagick`
    *   *Linux:* `sudo apt install imagemagick`
    *   *Windows:* Download the installer and ensure you check the box for *"Legacy utilities (e.g. convert)"*.

### Step 3: Run the Application
Navigate to your project directory and run either the modular app or the single-file version:
```bash
# To run the full workspace dashboard
streamlit run app.py

# OR to run the cloud-optimized single-file dashboard
streamlit run app_single.py
```

---

## 📂 Project Directory Structure

```text
├── app.py                      # Main modular Streamlit Application dashboard
├── app_single.py               # Cloud-ready, single-file edition (combines DB, Engine, & UI)
├── video_engine.py             # Advanced 9:16 Video Compiler & Audio/Subtitle Integrator
├── db_manager.py               # SQLite Database Manager (creates channels & shorts tables)
├── psychology_data.py          # Trigger descriptions, hook templates, & CTAs
├── youtube_engine.py           # SEO Copywriter & Algorithmic Metadata Generator
├── init_demo.py                # Setup script that generates a stunning pre-compiled video demo
├── generate_defaults.py        # Utility script to generate default assets
├── default_assets/             # Holds static profile backgrounds
├── audio_clips/                # Temporarily stores TTS voiceovers (.mp3) & WebVTT (.vtt) paths
├── video_output/               # Target folder where finished vertical MP4s are saved
└── shorts.db                   # SQLite Database holding your entire social media workspace
```
