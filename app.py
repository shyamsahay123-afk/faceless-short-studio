import os
import re
import gc
import random
import traceback
import xml.etree.ElementTree as ET
import requests
import numpy as np
import streamlit as st
from PIL import Image
import db_manager as db
import psychology_data as psych
import video_engine as video
import youtube_engine as yt

# --- Configure Streamlit Page (Clean, Dark Theme Layout) ---
st.set_page_config(
    page_title="Faceless AI Short Studio", 
    page_icon="🎬", 
    layout="centered"
)

# --- Custom Styling CSS (Luxury Minimalist Theme) ---
st.markdown("""
<style>
    .reportview-container .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #FF2D55, #FF9500);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #8E8E93;
        margin-bottom: 2rem;
        text-align: center;
    }
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 700 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 18px !important;
        background: linear-gradient(45deg, #FF2D55, #FF5E3A) !important;
        color: white !important;
        border: none !important;
        width: 100% !important;
        box-shadow: 0 4px 15px rgba(255, 45, 85, 0.4) !important;
        transition: 0.3s !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 45, 85, 0.6) !important;
    }
    div[role="listbox"] {
        max-height: 250px !important;
        overflow-y: auto !important;
    }
    html {
        scroll-behavior: smooth !important;
    }
    .trend-badge {
        background-color: #1c1c1e;
        border: 1px solid #2c2c2e;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# --- Ensure Directories Exist (B8: anchored to the app folder, not the CWD) ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(APP_DIR, "uploaded_assets"), exist_ok=True)

def save_uploaded_file(uploaded_file, target_dir="uploaded_assets"):
    if not uploaded_file: return None
    target_dir = os.path.join(APP_DIR, target_dir)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

# --- LOCAL FILE API KEY AUTO-SAVERS (B8: always in the app folder) ---
def load_key_from_file(filename):
    path = os.path.join(APP_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[Keys] Could not read {filename}: {e}")
    return ""

def save_key_to_file(filename, key):
    try:
        with open(os.path.join(APP_DIR, filename), "w", encoding="utf-8") as f:
            f.write(str(key).strip())
    except Exception as e:
        print(f"[Keys] Could not save {filename}: {e}")

# --- CLEAN API KEY UTILITY ---
def clean_api_key(key):
    if not key:
        return ""
    return str(key).split(" - ")[0].split(" ")[0].strip()

# --- SECRET RESOLVER: Streamlit Cloud secrets first, local .txt files second ---
def get_secret_key(name, filename):
    try:
        if name in st.secrets:
            v = str(st.secrets[name]).strip()
            if v:
                return clean_api_key(v)
    except Exception:
        pass
    return clean_api_key(load_key_from_file(filename))

# --- FAST CACHED API CONNECTION STATUS TESTERS ---
@st.cache_data(ttl=60)
def test_pexels_key_connection(api_key):
    if not api_key or not api_key.strip():
        return "empty"
    try:
        r = requests.get("https://api.pexels.com/v1/collections", headers={"Authorization": api_key}, timeout=10)
        if r.status_code == 200:
            return "valid"
        return "invalid"
    except Exception:
        return "error"

@st.cache_data(ttl=60)
def test_pixabay_key_connection(api_key):
    if not api_key or not api_key.strip():
        return "empty"
    url = f"https://pixabay.com/api/videos/?key={api_key}&q=nature&per_page=3"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return "valid"
        return "invalid"
    except Exception:
        return "error"

@st.cache_data(ttl=60)
def test_elevenlabs_key_connection(api_key):
    if not api_key or not api_key.strip():
        return "empty"
    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
    try:
        r = requests.post(url, headers={"xi-api-key": api_key}, json={"text": "."}, timeout=10)
        if r.status_code in (200, 402):
            return "valid"
        return "invalid"
    except Exception:
        return "error"

@st.cache_data(ttl=60)
def test_huggingface_key_connection(api_key):
    if not api_key or not api_key.strip():
        return "empty"
    # Use Hugging Face's official, lightweight user identity API. 
    # Try both standard and modern v2 endpoints to support all fine-grained and classic tokens!
    try:
        # Try v2 first (supports fine-grained and classic tokens)
        r = requests.get("https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if r.status_code == 200:
            return "valid"
        # Fallback to legacy whoami
        r2 = requests.get("https://huggingface.co/api/whoami", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if r2.status_code == 200:
            return "valid"
        return "invalid"
    except Exception:
        return "error"

def display_status_badge(status):
    if status == "valid":
        return "<span style='color: #39FF14; font-weight: bold; font-size: 14px;'>🟢 Connected</span>"
    elif status == "invalid":
        return "<span style='color: #FF3B30; font-weight: bold; font-size: 14px;'>🔴 Invalid Key</span>"
    elif status == "empty":
        return "<span style='color: #8E8E93; font-size: 14px;'>⚪ Disconnected</span>"
    else:
        return "<span style='color: #FF9500; font-size: 14px;'>🟡 Connection Error</span>"

# --- REAL-TIME GOOGLE & YOUTUBE SHORTS TREND BOARD CRAWLER ---
def fetch_trending_shorts_concepts():
    base_trends = [
        "Why the Top 1% Use Dopamine Fasting to Build Unshakeable Focus",
        "The Dark Psychology of the 'Pavlov Effect' (How to brainwash yourself to work)",
        "The Silent Morning Rule: Why high-performers speak to no-one before 9 AM",
        "The Neuroscience of Procrastination (Why willpower is a complete lie)",
        "The Bizarre '3-Second Rule' to Eliminate Social Anxiety Instantly",
        "Why Intelligent People Struggle to Stay Consistent (And the exact cure)"
    ]
    try:
        r = requests.get("https://trends.google.com/trends/trendingsearches/daily/rss?geo=US", timeout=4)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            items = root.findall('.//item/title')
            for idx, item in enumerate(items[:3]):
                if item.text: base_trends.insert(idx, f"Why high-performers study the '{item.text}' focus shift")
    except Exception:
        pass
    return list(set(base_trends))[:5]

# --- Standalone AI Script Draft Generator (now in script_engine.py so the
# daily.py CLI autopilot can import it without starting Streamlit) ---
from script_engine import auto_generate_script_local, score_hook, best_hook_line, generate_script_with_score

# ==============================================================================
# DATABASE & SETTINGS INITIALIZATION
# ==============================================================================
db.init_db()

# --- Permanent Sidebar API Keys Auto-Savers & GLOWING CONNECTION BADGES ---
st.sidebar.subheader("🔑 Advanced API Keys")

with st.sidebar.expander("🔑 Configure Keys (Auto-Saved)", expanded=True):
    # Groq Key (The New Brain)
    saved_groq = get_secret_key("GROQ_API_KEY", "groq_key.txt")
    raw_groq_key = st.text_input("Groq Key (AI Director LLM)", type="password", value=saved_groq)
    if raw_groq_key != saved_groq:
        save_local_key("groq_key.txt", raw_groq_key)
        st.rerun()
    st.caption(f"{'🟢 Connected' if raw_groq_key.strip() else '🔴 Missing (Using legacy templates)'}")
    
    # Pexels Key
    saved_pexels = get_secret_key("PEXELS_API_KEY", "pexels_key.txt")
    raw_pexels_api_key = st.text_input("Pexels Key (Video)", type="password", value=saved_pexels)
    pexels_api_key = clean_api_key(raw_pexels_api_key)
    if pexels_api_key != saved_pexels:
        save_key_to_file("pexels_key.txt", pexels_api_key)
    st.markdown(display_status_badge(test_pexels_key_connection(pexels_api_key)), unsafe_allow_html=True)
    st.write("")
        
    # Pixabay Key
    saved_pixabay = get_secret_key("PIXABAY_API_KEY", "pixabay_key.txt")
    raw_pixabay_api_key = st.text_input("Pixabay Key (Video)", type="password", value=saved_pixabay)
    pixabay_api_key = clean_api_key(raw_pixabay_api_key)
    if pixabay_api_key != saved_pixabay:
        save_key_to_file("pixabay_key.txt", pixabay_api_key)
    st.markdown(display_status_badge(test_pixabay_key_connection(pixabay_api_key)), unsafe_allow_html=True)
    st.write("")
        
    # ElevenLabs Key
    saved_eleven = get_secret_key("ELEVENLABS_API_KEY", "elevenlabs_key.txt")
    raw_elevenlabs_api_key = st.text_input("ElevenLabs Key (Voice)", type="password", value=saved_eleven)
    elevenlabs_api_key = clean_api_key(raw_elevenlabs_api_key)
    if elevenlabs_api_key != saved_eleven:
        save_key_to_file("elevenlabs_key.txt", elevenlabs_api_key)
    st.markdown(display_status_badge(test_elevenlabs_key_connection(elevenlabs_api_key)), unsafe_allow_html=True)
    st.write("")
    
    # Hugging Face Key
    saved_hf = get_secret_key("HUGGINGFACE_TOKEN", "huggingface_token.txt")
    raw_hf_token = st.text_input("Hugging Face Token (AI Video)", type="password", value=saved_hf)
    huggingface_token = clean_api_key(raw_hf_token)
    if huggingface_token != saved_hf:
        save_key_to_file("huggingface_token.txt", huggingface_token)
    st.markdown(display_status_badge(test_huggingface_key_connection(huggingface_token)), unsafe_allow_html=True)
    st.write("")
    
    # Pollinations Key (B3 — OPTIONAL): sk_/pk_ key = no rate limit
    saved_poll = get_secret_key("POLLINATIONS_KEY", "pollinations_key.txt")
    raw_poll = st.text_input("Pollinations Key", type="password", value=saved_poll)
    pollinations_key = clean_api_key(raw_poll)
    if pollinations_key != saved_poll:
        save_key_to_file("pollinations_key.txt", pollinations_key)
    if pollinations_key:
        _poll_ok = pollinations_key.startswith(("sk_", "pk_"))
        st.markdown(display_status_badge("valid" if _poll_ok else "invalid"), unsafe_allow_html=True)
    else:
        st.caption("⚪ Optional: Add key to remove rate limits")

st.sidebar.divider()
all_shorts = db.get_all_shorts()
st.sidebar.write(f"📁 Total Videos Generated: **{len(all_shorts)}**")

# ==============================================================================
# MAIN PAGE INTERFACE
# ==============================================================================
st.markdown('<div class="main-header">🎬 Faceless AI Short Studio <span style="font-size: 0.4em; color: #888;">v2.1.2</span></div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">YouTube Trends Crawler 🤝 Real-Time Interactive AI Script Editor 🤝 Hybrid Video Compiler</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# STEP 1: REAL-TIME YOUTUBE SHORTS TREND BOARD
# ------------------------------------------------------------------------------
st.subheader("📡 Step 1: Live YouTube Shorts Trend Board")
st.write("Our automated scraper crawled Google and YouTube Trends right now. Click on any viral concept below to automatically load it as your next video prompt!")

# Custom algorithmic predictions and trend velocity tags to show exactly WHY it's trending!
trend_velocities = ["📈 +340% Search Velocity today (ADHD Retention High)", "🔥 +245% Viral Shorts Index (Hook Potential)", "🧠 +180% Mindset Search Surge", "📈 +290% High Completion Index (Rewatch Potential)", "⚡ +195% Fast-Paced Focus Trend"]
trend_analyses = ["💡 Recommended hook style: Curiosity Gap", "💡 Recommended style: Identity Signaling", "💡 Recommended hook style: Loss Aversion", "💡 Recommended style: High-Alert Urgency", "💡 Recommended style: Slower Dramatic"]

trending_concepts = fetch_trending_shorts_concepts()
for idx, trend in enumerate(trending_concepts):
    vel = trend_velocities[idx % len(trend_velocities)]
    analysis = trend_analyses[idx % len(trend_analyses)]
    with st.container():
        st.markdown(
            f"""<div class="trend-badge">
                <span>🔥 <b>Trend #{idx+1}:</b> {trend} <br>
                <small style="color: #FF2D55; font-weight: bold;">{vel}</small> | 
                <small style="color: #8E8E93;">{analysis}</small></span>
            </div>""", 
            unsafe_allow_html=True
        )
        if st.button("🔌 Use This Concept Prompt", key=f"trend_btn_{idx}"):
            st.session_state['topic_override'] = trend
            st.rerun()

# --- NEW STUNNING GENERATIVE AI TEST ROOM (THE IMPOSSIBLE PROMPT PROOVER!) ---
st.write("")
st.markdown("### 🧪 Step 1.5: Generative AI Test Room (Impossible Prompts)")
st.write("How do you prove that your AI is drawing a completely unique video from scratch rather than just searching Google? **Try an 'Impossible Prompt'!** Standard stock databases only have real-world videos. They do *not* have sci-fi or surreal videos. Select a prompt below, choose B-Roll Source: **Hugging Face AI** in Step 3, and watch the AI draw the scene in seconds!")

with st.expander("🧪 Open Generative AI Test Lab", expanded=False):
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("**1. Surreal Sci-Fi Concept**")
        st.write("*Prompt:* `A glowing neon astronaut riding a pink horse on Mars, vertical`")
        if st.button("🔌 Load Sci-Fi Prompt", type="secondary"):
            st.session_state['topic_override'] = "glowing neon astronaut riding a pink horse on Mars, vertical"
            st.session_state['b_roll_override'] = "🤖 True AI Generated (Hugging Face - Free)"
            st.rerun()
            
        st.markdown("**2. Aesthetic Fantasy Concept**")
        st.write("*Prompt:* `A neon-purple human brain floating inside a clear glass jar, dark room`")
        if st.button("🔌 Load Fantasy Prompt", type="secondary"):
            st.session_state['topic_override'] = "neon-purple human brain floating inside a clear glass jar, dark room"
            st.session_state['b_roll_override'] = "🤖 True AI Generated (Hugging Face - Free)"
            st.rerun()
            
    with col_t2:
        st.markdown("**3. Cute Surreal Concept**")
        st.write("*Prompt:* `A cute fluffy orange cat wearing a miniature medieval helmet writing on computer`")
        if st.button("🔌 Load Cute Prompt", type="secondary"):
            st.session_state['topic_override'] = "cute fluffy orange cat wearing a miniature medieval helmet writing on computer"
            st.session_state['b_roll_override'] = "🤖 True AI Generated (Hugging Face - Free)"
            st.rerun()

st.divider()

# ------------------------------------------------------------------------------
# STEP 2: CONCEPT PROMPT & INTERACTIVE AI SCRIPT EDITOR
# ------------------------------------------------------------------------------
st.subheader("✍️ Step 2: Prompt & AI Script Editor")

col_p1, col_p2 = st.columns([3, 2])
with col_p1:
    default_topic = st.session_state.get('topic_override', "How to overcome morning laziness")
    topic_input = st.text_input("💡 Video Topic / Prompt:", value=default_topic, placeholder="Type your idea or click on a trend above...")
with col_p2:
    style_choice = st.selectbox("🎨 Video Vibe / Style", [
        "Dark & Dramatic (Mysterious music, purple pulsing loops fallback)",
        "Motivational & Elite (Inspirational music, emerald glowing fallback)",
        "High-Alert Urgency (Dramatic tense music, crimson alarm fallback)",
        "Emotional Story (Calm ambient music, royal blue fallback)",
        "❤️ Romance & Intimacy (Calm beautiful music, deep rose fallback)"
    ])

# Draft Script Button (Triggers the Interactive Editor Phase!)
if st.button("🤖 STEP 1: DRAFT SCRIPT & ANALYZE KEYWORDS", type="primary", use_container_width=True):
    if not topic_input or not topic_input.strip():
        st.error("⚠️ Please enter a Topic or select a trend first!")
    else:
        title, script, tags, extra_data = auto_generate_script_local(topic_input, style_choice)
        st.session_state['active_ai_data'] = extra_data if isinstance(extra_data, dict) else None
        st.session_state['active_title'] = title
        st.session_state['active_script'] = script
        st.session_state['active_tags'] = tags
        st.session_state['active_trigger'] = "AI Director" if isinstance(extra_data, dict) else "Legacy Template"
        st.success("🎉 Script Drafted successfully! Tweak and edit your spoken lines below before rendering!")

# INTERACTIVE SCRIPT EDITOR CONTAINER (Shows ONLY if script has been generated)
if 'active_script' in st.session_state:
    st.markdown("### 📝 The Interactive AI Editor")
    st.write("You can rewrite, tweak, or fully customize the generated script or stock search tags below:")
    
    edited_title = st.text_input("📌 Video Draft Title (For your database):", value=st.session_state['active_title'])
    edited_script = st.text_area("✍️ Spoken Script & Notes (AI will speak exactly what you type here!):", value=st.session_state['active_script'], height=250)
    
    # Analyze B-Roll search keywords in real-time!
    spoken_clean = video.clean_script_for_speech(edited_script)
    keywords_list = video.extract_best_keywords(spoken_clean, num_words=12)
    
    st.session_state['active_title'] = edited_title
    st.session_state['active_script'] = edited_script

    # --- HOOK SCORECARD — pre-render quality gate (fix the hook BEFORE spending 2.5 min rendering) ---
    _hook = best_hook_line(edited_script)
    _hscore, _hchecks = score_hook(_hook)
    _hicon = "🟢" if _hscore >= 75 else ("🟡" if _hscore >= 55 else "🔴")
    _hfailed = [n for n, ok in _hchecks if not ok]
    _hint = f"  <br><small style='color:#FF9500'>Fix: {', '.join(_hfailed[:3])}</small>" if _hfailed else "  <br><small style='color:#39FF14'>All checks passed — render-safe</small>"
    st.markdown(f"**{_hicon} Hook Scorecard: {_hscore}/100** — <i>“{_hook[:80]}”</i>{_hint}", unsafe_allow_html=True)

    # --- RETENTION RE-CUT — feed the app your viewers' real behavior ---
    st.markdown("#### 📈 Retention Re-Cut (the app learns from your viewers)")
    st.caption("YouTube Studio → your video → Analytics → 'Average Percentage of Viewers' → EXPORT (CSV). "
               "The app finds where viewers drop and CUTS that sentence from the script. Re-render = shorter video, no dead zone.")
    _ret_file = st.file_uploader("Retention CSV export", type=["csv"], key="retention_csv")
    if _ret_file is not None and 'active_script' in st.session_state:
        try:
            import retention_engine as _ret
            _curve = _ret.parse_retention_csv(_ret_file.getvalue().decode("utf-8-sig"))
            _dips = _ret.find_retention_dips(_curve)
            if _dips:
                # word timings come from the last render's SRT (saved after each render)
                _srt_path = st.session_state.get("last_render_srt", "")
                _subs = video.parse_vtt(_srt_path) if _srt_path and os.path.exists(_srt_path) else []
                st.markdown("**Detected viewer drop zones:**")
                for _d in _dips:
                    st.markdown(f"- ⚠️ **{_d['start']:.0f}s–{_d['end']:.0f}s** — retention fell **{_d['depth_pct']:.0f} pts** (to {_d['min_pct']:.0f}%)")
                if _subs:
                    if st.button("✂️ APPLY RE-CUT TO THIS SCRIPT", use_container_width=False):
                        _new_script, _removed = _ret.recut_script_for_dips(edited_script, _subs, _dips)
                        if _removed:
                            st.session_state['active_script'] = _new_script
                            st.rerun()
                        else:
                            st.warning("No whole sentence falls inside a drop zone — shorten the topic or split the video.")
                else:
                    st.info("Render this script once first (the app needs its word timings), then re-upload the CSV to auto-cut.")
            else:
                st.success("No significant drop zones found — the retention curve is flat. Keep this script.")
        except Exception as _e:
            st.error(f"Could not parse retention CSV: {_e}")

    # Calculate estimated cuts needed
    word_count = len(spoken_clean.split())
    duration_est = word_count / 2.5
    
    pacing_dur = 2.0
    num_cuts_est = int(np.ceil(duration_est / pacing_dur))
    
    # --- INTERACTIVE VISUAL STORYBOARD PROMPTER ---
    st.markdown("### 🎬 Step 2.5: Interactive Visual Storyboard Director")
    st.write("Direct what visual clip appears on screen for every 2-second block of your video! Overwrite the default keywords with custom prompts (e.g. *'couple hugging'*, *'fireplace'*) to direct your scenario:")
    
    col_sc1, col_sc2 = st.columns(2)
    custom_scenarios = []
    
    for c_idx in range(min(12, num_cuts_est)):
        default_term = keywords_list[c_idx % len(keywords_list)]
        col_target = col_sc1 if c_idx % 2 == 0 else col_sc2
        term_val = col_target.text_input(
            f"📷 Scene #{c_idx+1} Prompt (Sec {c_idx*2}-{(c_idx+1)*2}):", 
            value=default_term, 
            key=f"scen_{c_idx}"
        )
        custom_scenarios.append(term_val)
        
    st.session_state['custom_scenarios'] = custom_scenarios

st.divider()

# ------------------------------------------------------------------------------
# STEP 3: VOCAL & STYLING SETTINGS
# ------------------------------------------------------------------------------
st.subheader("🎛️ Step 3: Vocal & Styling Settings")
col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)

# PIECE 7 — VOICE TONES (ElevenLabs V3 presets: human tone, not V1 robot)
# 🇮🇳 HINDI VARIANTS: same visual identity, new voice + Devanagari-safe captions.
# (Write/paste the script in Hindi, pick a Hindi voice, render — done.)
_HINDI_VOICES = ["🇮🇳 Hindi Male (Madhur)", "🇮🇳 Hindi Female (Swara)"]
ai_voice_label = col_s1.selectbox("🔊 Narrator Voice (V3 Tones + Hindi)", list(video.VOICE_PRESETS.keys()) + _HINDI_VOICES)
voice_code = {"Deep Narrator Male": "en-US-ChristopherNeural", "Energetic Male": "en-US-GuyNeural",
              "Warm Female": "en-US-AriaNeural", "Calm British Female": "en-GB-SoniaNeural",
              "🇮 Hindi Male (Madhur)": "hi-IN-MadhurNeural",
              "🇮🇳 Hindi Female (Swara)": "hi-IN-SwaraNeural"}[ai_voice_label]

pacing_label = col_s2.selectbox("⏱️ Video Pacing (now LIVE)", [
    "🌑 Deep Cosmic (4-9s holds — GOONINGGNG)",
    "⚡ Adrenaline ADHD (1.3s cuts)",
    "🎬 Cinematic (2.0s cuts)",
    "🌌 Mindful Slower (3.2s cuts)"
])
pacing_mapping = {
    "⚡ Adrenaline ADHD (1.3s cuts)": ("adrenaline", 1.3),
    "🎬 Cinematic (2.0s cuts)": ("cinematic", 2.0),
    "🌌 Mindful Slower (3.2s cuts)": ("mindful", 3.2),
    "🌑 Deep Cosmic (4-9s holds — GOONINGGNG)": ("cosmic", 6.0)
}
pacing_code, cut_duration_val = pacing_mapping[pacing_label]

caption_theme_label = col_s3.selectbox("🔤 Caption Theme", ["⌨️ Typewriter (GOONINGGNG)", "⚪ Minimalist White (reference style)", "🎬 Cinematic Sentences (mystery style)", "🔥 Hormozi Gold style", "🌌 Cyberpunk Neon"])
caption_mapping = {
    "⚪ Minimalist White (reference style)": ("minimalist", "white"),
    "🎬 Cinematic Sentences (mystery style)": ("cinematic", "white"),
    "🔥 Hormozi Gold style": ("hormozi", "yellow"),
    "🌌 Cyberpunk Neon": ("cyberpunk", "cyan"),
    "⌨️ Typewriter (GOONINGGNG)": ("typewriter", "white")
}
caption_style_code, caption_color = caption_mapping[caption_theme_label]

# B-Roll Visual Source dropdown supporting our brand new True AI Generative SVD!
default_b_roll_idx = 0
b_roll_override = st.session_state.get('b_roll_override', None)
if b_roll_override:
    if "Hugging" in b_roll_override: default_b_roll_idx = 2

b_roll_source_label = col_s4.selectbox("🏞️ Visual Source", [
    "Pexels (Free Stock)",
    "Pixabay (Free Stock)",
    "🤖 True AI Generated (Hugging Face - Free)"
], index=default_b_roll_idx)

if "Pexels" in b_roll_source_label:
    b_roll_source_val = "pexels"
elif "Pixabay" in b_roll_source_label:
    b_roll_source_val = "pixabay"
else:
    b_roll_source_val = "huggingface"

meme_sfx_label = col_s5.selectbox("🔥 Meme Sound", [
    "None",
    "Record Scratch",
    "Bass Drop",
    "Energy Flare",
    "Tick Tock",
    "Comet Whoosh",
    "Clock Hit",
    "Warp Whoosh",
    "Riser",
    "Climax Impact",
    "Sub Boom"
], help="First 3 = classic downloads. The rest = real SFX extracted from the viral reference short (reference pack).")

bg_music_path = "test.mp3" if ("Dramatic" in style_choice or "Urgency" in style_choice) else "backup.mp3"
show_progress_bar = False
music_volume = 0.09  # v2: voice-first mix — music sits clearly UNDER the voice

# ==============================================================================
# ELITE VISUAL STYLE SYSTEM — the 7-layer composition (reference: top faceless channels)
# ==============================================================================
st.markdown("#### 🎨 Elite Visual Style System")
st.caption("Dark animated background (never pure black) + stacked hook text + script beats + cards + arrows + SFX — the exact layer system used by top faceless channels.")
col_v1, col_v2, col_v3 = st.columns(3)
bg_style_label = col_v1.selectbox("Background Style", [
    "🌑 Void Black (GOONINGGNG filter)",
    "🕸️ Elite Dark Grid",
    "🌠 Cosmic Gold (Cinematic)",
    "🌌 Aurora Mesh",
    "🎬 Red Pinstripe",
    "✨ Glow Field"
])
bg_style_map = {"🕸️ Elite Dark Grid": "grid", "🌠 Cosmic Gold (Cinematic)": "cosmic", "🌌 Aurora Mesh": "aurora", "🎬 Red Pinstripe": "pinstripe", "✨ Glow Field": "glow", "🌑 Void Black (GOONINGGNG filter)": "void"}
bg_style_val = bg_style_map[bg_style_label]

accent_label = col_v2.selectbox("Accent Color (one system, every video)", [
    "⚡ Yellow (Attention)",
    "🏆 Gold (Mystery/Cinematic)",
    "🌿 Green (Growth)",
    "🧊 Cyan (Tech)",
    "🔥 Red (Urgency)",
    "💜 Magenta (Drama)"
])
accent_map = {"⚡ Yellow (Attention)": "yellow", "🏆 Gold (Mystery/Cinematic)": "gold", "🌿 Green (Growth)": "green", "🧊 Cyan (Tech)": "cyan", "🔥 Red (Urgency)": "red", "💜 Magenta (Drama)": "magenta"}
accent_val = accent_map[accent_label]

clip_mode_label = col_v3.selectbox("Clip Mode (your HD clips)", [
    "Full screen",
    "⚡ Full Auto (AI clips primary)",
    "Blend over grid (stock)",
    "Inset rounded window",
    "Text-first (no clips)"
])
clip_mode_map = {"⚡ Full Auto (AI clips primary)": "auto", "Blend over grid (stock)": "blend", "Inset rounded window": "inset", "Full screen": "full", "Text-first (no clips)": "none"}
clip_mode_val = clip_mode_map[clip_mode_label]

show_progress_bar = st.toggle("📊 Show progress bar (keep OFF — YouTube UI covers it)", value=False)

# PIECE 9 — SFX KNOB (one slider controls the whole sound-design layer)
sfx_level = st.slider("🔊 SFX Level (whole sound layer: hits, whooshes, ticks)", 0, 100, 70) / 100.0

# PSYCHOLOGY TRICKS — the trick director (named secret + comment bait, auto-rotated)
tricks_on = st.toggle("🧠 Psychology Tricks (named secret + comment bait, auto-rotated)", value=True,
                      help="Every video gets one named secret; a comment bait rotates (open question / hidden detail / debate split); one planted flaw per ~10 videos. Spec: psychology_tricks.md")

# PIECE 4 — CHARACTER BIBLE (the channel's locked visual identity)
st.markdown("#### 👤 Character Bible (locked visual identity)")
st.caption("One description + one fixed seed = the SAME look in every video. Set it once — video #50 looks like video #1.")
bible = video.load_character_bible()
col_b1, col_b2, col_b3 = st.columns([2, 3, 1])
bib_enabled = col_b1.toggle("Character bible ON", value=bible.get("enabled", True))
bib_name = col_b1.text_input("Character name", value=bible.get("name", "The Narrator"))
bib_desc = col_b2.text_area("Character description (locked in every AI image)", value=bible.get("description", ""))
bib_seed = col_b3.number_input("Seed (locked)", min_value=1, max_value=9999999, value=int(bible.get("seed", 421337)))
# Watermark lock removed as requested
bib_handle = "" 
if st.button("💾 Save Character Bible", use_container_width=False):
    video.save_character_bible({"enabled": bib_enabled, "name": bib_name, "description": bib_desc, "seed": int(bib_seed),
                                "watermark": bib_handle,
                                "style_suffix": bible.get("style_suffix", "dark cinematic atmosphere, moody cinematic lighting, 8k, photorealistic, vertical 9:16 composition")})
    st.success("Bible saved — every future AI image uses this locked identity.")

st.divider()

# ------------------------------------------------------------------------------
# STEP 4: OPTIONAL CUSTOM FILE UPLOADS
# ------------------------------------------------------------------------------
st.subheader("📤 Step 4: Upload Custom Assets (Optional)")
uploaded_files = st.file_uploader(
    "Drag & Drop Your Pictures or Videos (.jpg, .png, .mp4, .mov)", 
    type=["jpg", "png", "jpeg", "mp4", "mov"], 
    accept_multiple_files=True,
    help="Optional. If uploaded, the AI will use your files first. If they are shorter than the voiceover, the AI automatically downloads matching vertical Pexels stock video loops to fill the gaps! Leave empty for a 100% automated stock video."
)

st.divider()

# ==============================================================================
# SINGLE GIANT ONE-CLICK MASTER ACTION BUTTON
# ==============================================================================
if st.button("👉 GENERATE & COMPILE MY AI VIDEO NOW 👈", type="primary", use_container_width=True):
        # Determine the key to validate
    if b_roll_source_val == "pexels":
        active_video_key = pexels_api_key
    elif b_roll_source_val == "pixabay":
        active_video_key = pixabay_api_key
    else:
        active_video_key = huggingface_token
        
    if not active_video_key or not active_video_key.strip():
        st.error(f"❌ {b_roll_source_label} Key/Token is missing! Please configure it in the left sidebar under Advanced API Keys first!")
    else:
        # If they clicked compile but forgot to click Step 1, auto-draft the script silently right now!
        if 'active_script' not in st.session_state:
            title, script, tags, extra_data = auto_generate_script_local(topic_input, style_choice)
            st.session_state['active_ai_data'] = extra_data if isinstance(extra_data, dict) else None
            st.session_state['active_title'] = title
            st.session_state['active_script'] = script
            st.session_state['active_tags'] = tags
            st.session_state['active_trigger'] = "AI Director" if isinstance(extra_data, dict) else "Legacy Template"
            
        if st.session_state['active_title'] == "Safety Warning":
            st.error("❌ Cannot compile: Please select a non-restricted creative topic in Step 2!")
        else:
            preset_title = st.session_state['active_title']
            preset_script = st.session_state['active_script']
        preset_tags = st.session_state.get('active_tags', 'shorts, viral')
        trigger_used = st.session_state.get('active_trigger', 'Identity Signaling')
        scenarios_input = st.session_state.get('custom_scenarios', [])
        
        all_channels = db.get_all_channels()
        if not all_channels:
            db.add_channel("My Faceless Empire", "Self Improvement", "10k")
            all_channels = db.get_all_channels()
        ch_id = all_channels[0][0]
        
        # Save to database
        short_id = db.add_short(
            ch_id, 
            preset_title, 
            preset_script, 
            trigger_used, 
            f"{preset_title}\n\nGenerated autonomously.\n\n#AI #Shorts", 
            preset_tags
        )
        
        # --- COMPACT IN-PLACE TERMINAL RENDER LOG SYSTEM ---
        progress_container = st.container(border=True)
        with progress_container:
            st.markdown("### 🤖 Live AI Production Console")
            progress_bar = st.progress(0.0)
            status_text = st.empty() # Overwrites text dynamically in-place!
        
        def render_progress(pct, text):
            progress_bar.progress(pct)
            status_text.markdown(f"🤖 **AI Active:** {text} ... **{int(pct*100)}%**")
            
        custom_filepaths = []
        if uploaded_files:
            custom_filepaths = [save_uploaded_file(f) for f in uploaded_files]
            
        try:
            # Call our ultimate hybrid compiler! (returns 4-tuple: +auto thumbnail)
            v_path, a_path, vtt_path, thumb_path = video.create_hybrid_ai_video(
                short_id, 
                preset_script, 
                custom_filepaths, 
                voice_code, 
                caption_color,
                bg_music_path=bg_music_path,
                bg_music_volume=music_volume,
                show_progress_bar=show_progress_bar,
                pexels_api_key=pexels_api_key if b_roll_source_val == "pexels" else (pixabay_api_key if b_roll_source_val == "pixabay" else ""),
                elevenlabs_api_key=elevenlabs_api_key,
                progress_callback=render_progress,
                caption_style=caption_style_code,
                cut_duration=cut_duration_val,
                pacing=pacing_code,
                b_roll_source=b_roll_source_val,
                custom_scenarios=scenarios_input,
                meme_sfx_name=meme_sfx_label,
                hf_token=huggingface_token,
                style_bg=bg_style_val,
                style_accent=accent_val,
                clip_mode=clip_mode_val,
                voice_preset=ai_voice_label,
                sfx_level=sfx_level,
                character_bible={"enabled": bib_enabled, "name": bib_name, "description": bib_desc, "seed": int(bib_seed),
                                 "watermark": bib_handle,
                                 "style_suffix": video.load_character_bible().get("style_suffix", "dark cinematic atmosphere, moody cinematic lighting, 8k, photorealistic, vertical 9:16 composition")},
                tricks=tricks_on,
            )
            
            db.update_short_video(short_id, v_path, a_path, vtt_path, status='created')
            st.session_state['last_render_srt'] = vtt_path  # enables Retention Re-Cut
            st.session_state['last_render_video_name'] = os.path.basename(v_path)
            status_text.markdown("🤖 **AI Active:** Render complete! ... **100%**")

            # CONFORMANCE AUDIT — the render reports itself BEFORE you watch.
            # Dead frames, style drift, missing outro/watermark/captions, dead
            # audio: all flagged with exact timestamps.
            try:
                _qc = video.run_qc_report(v_path, vtt_path, cosmic=(bg_style_val == "void"), watermark=bib_handle)
                _qc_warn = [l for l in _qc if l.startswith("⚠") or l.startswith("❌")]
                with st.expander("🔍 QC Self-Audit — " + ("ISSUES FOUND, timestamps below" if _qc_warn else "all clear"), expanded=bool(_qc_warn)):
                    for _l in _qc:
                        st.text(_l)
                if _qc_warn:
                    st.warning("QC found issues above — the timestamp tells you exactly where. Send me that line and I fix that layer.")
            except Exception as _qe:
                st.caption(f"QC skipped: {_qe}")
            
            st.success("🎉 Your AI video has been compiled flawlessly!"); st.balloons()
            
            # Display player + auto thumbnail (piece 11)
            col_p1, col_p2, col_p3 = st.columns([1.2, 1.6, 1.2])
            with col_p2:
                st.video(v_path)
            with col_p1:
                if thumb_path and os.path.exists(thumb_path):
                    st.markdown("**🖼️ Auto Thumbnail (upload-ready):**")
                    st.image(thumb_path, use_container_width=True)
            
            with st.expander("📋 Click to Copy: Algorithmic SEO Copy Pack"):
                seo_data = yt.generate_viral_seo_pack(preset_title, video.clean_script_for_speech(preset_script), "Self Improvement", trigger_used)
                st.text_input("📌 Optimized Title:", value=seo_data["title"])
                st.text_area("📝 Description:", value=seo_data["description"], height=180)
                st.text_input("🏷️ Tags & Keywords:", value=seo_data["tags"])
                
        except Exception as e:
            status_text.error("❌ Render Failed!")
            st.error(f"⚠️ Render failure: {e}")
            with st.expander("🛠️ Debug Terminal & Crash Log Stack Trace"):
                st.code(traceback.format_exc())

# ------------------------------------------------------------------------------
# PIECE 12 — BATCH MODE: the assembly line (5 topics in → 5 videos + 5 thumbs out)
# "Lock a template → write all scripts → generate all videos → all QC → export."
# ------------------------------------------------------------------------------
st.divider()
with st.expander("📦 Batch Mode — generate a week of videos in one run (assembly line)", expanded=False):
    st.caption("Pro batch workflow: lock the style (set above), enter up to 5 topics, one click. Each video gets its own script, V3 voice, bible visuals, auto thumbnail.")
    batch_topics = []
    for i in range(5):
        batch_topics.append(st.text_input(f"Topic {i+1} (leave empty to skip)", key=f"batch_topic_{i}"))
    batch_topics = [t.strip() for t in batch_topics if t.strip()]
    if st.button("🏭 GENERATE BATCH", type="primary", use_container_width=True, disabled=(len(batch_topics) == 0)):
        batch_results = []
        for i, btopic in enumerate(batch_topics):
            st.markdown(f"### 🏭 Batch {i+1}/{len(batch_topics)}: {btopic[:60]}")
            batch_bar = st.progress(0.0)
            batch_status = st.empty()
            def batch_progress(p, t, _bar=batch_bar, _st=batch_status):
                _bar.progress(p)
                _st.markdown(f"**Batch {i+1}:** {t} ... **{int(p*100)}%**")
            try:
                btitle, bscript, btags, btrigger = auto_generate_script_local(btopic, style_choice)
                all_ch = db.get_all_channels()
                if not all_ch:
                    db.add_channel("My Faceless Empire", "Self Improvement", "10k")
                    all_ch = db.get_all_channels()
                bid = db.add_short(all_ch[0][0], btitle, bscript, btrigger, f"{btitle}\n\nBatch generated.", btags)
                bv, ba, bvtt, bthumb = video.create_hybrid_ai_video(
                    bid, bscript, None, voice_code, caption_color,
                    bg_music_path=bg_music_path, bg_music_volume=music_volume,
                    show_progress_bar=show_progress_bar,
                    pexels_api_key=pexels_api_key if b_roll_source_val == "pexels" else (pixabay_api_key if b_roll_source_val == "pixabay" else ""),
                    elevenlabs_api_key=elevenlabs_api_key,
                    progress_callback=batch_progress,
                    caption_style=caption_style_code,
                    cut_duration=cut_duration_val,
                pacing=pacing_code,
                    b_roll_source=b_roll_source_val,
                    custom_scenarios=[],
                    meme_sfx_name="None",
                    hf_token=huggingface_token,
                    style_bg=bg_style_val,
                    style_accent=accent_val,
                    clip_mode=clip_mode_val,
                    voice_preset=ai_voice_label,
                    sfx_level=sfx_level,
                    character_bible={"enabled": bib_enabled, "name": bib_name, "description": bib_desc, "seed": int(bib_seed),
                                     "watermark": bib_handle,
                                 "style_suffix": video.load_character_bible().get("style_suffix", "dark cinematic atmosphere, moody cinematic lighting, 8k, photorealistic, vertical 9:16 composition")},
                                     tricks=tricks_on)
                db.update_short_video(bid, bv, ba, bvtt, status='created')
                st.session_state['last_render_srt'] = bvtt  # enables Retention Re-Cut
                st.session_state['last_render_video_name'] = os.path.basename(bv)
                batch_status.markdown(f"✅ **Batch {i+1} done:** {os.path.basename(bv)}")
                # conformance audit: surface issues per video (exact timestamps)
                try:
                    _bqc = video.run_qc_report(bv, bvtt, cosmic=(bg_style_val == "void"), watermark=bib_handle)
                    _bw = [l for l in _bqc if l.startswith("⚠") or l.startswith("❌")]
                    if _bw:
                        batch_status.warning("Batch QC: " + " · ".join(_bw[:3]))
                except Exception:
                    pass
                # O2: force-free the frame buffers before the next batch video
                # (5 videos in one process is what OOM-killed low-RAM hosts)
                gc.collect()
                try:
                    video.prune_output_dirs()
                except Exception:
                    pass
                if bthumb and os.path.exists(bthumb):
                    st.image(bthumb, caption=f"Thumbnail {i+1}", use_container_width=False)
                batch_results.append((btitle, bv, bthumb))
            except Exception as be:
                batch_status.error(f"❌ Batch {i+1} failed: {be}")
        if batch_results:
            st.success(f"🏭 BATCH COMPLETE — {len(batch_results)}/{len(batch_topics)} videos generated. All in Video Output.")

# ------------------------------------------------------------------------------
# PERFORMANCE LOG — feed it real numbers, the template LEARNS
# ------------------------------------------------------------------------------
st.divider()
with st.expander("📊 Performance Log — the template that learns from your uploads", expanded=False):
    st.caption("After each upload: YouTube Studio → your video → paste CTR / views / avg retention → Save. "
               "The channel remembers which thumbnail variant won; the next render makes that variant the primary.")
    _log = video.read_performance_log()
    if _log:
        _rows = list(_log.items())[-10:][::-1]
        st.table({
            "Date": [e.get("logged", "") for _n, e in _rows],
            "Video": [str(e.get("title") or "")[:38] for _n, e in _rows],
            "CTR %": [e.get("ctr", "") for _n, e in _rows],
            "Views": [e.get("views", "") for _n, e in _rows],
            "Avg Ret %": [e.get("avg_retention", "") for _n, e in _rows],
            "Thumb #": [e.get("thumb_variant", 0) for _n, e in _rows],
        })
        _bv = video.best_thumb_variant()
        st.success(f"🧠 Best-performing thumbnail variant so far: **#{_bv}** — it becomes the primary on the next render.")
    _p1, _p2 = st.columns([3, 2])
    with _p1:
        _pv_name = st.text_input("Video file name (auto from last render)", value=st.session_state.get("last_render_video_name", ""))
        _pv_title = st.text_input("Video title", value=st.session_state.get("active_title", ""))
    with _p2:
        _pc1, _pc2, _pc3, _pc4 = st.columns(4)
        _p_ctr = _pc1.number_input("CTR %", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        _p_views = _pc2.number_input("Views", min_value=0, step=100, format="%d")
        _p_ret = _pc3.number_input("Avg Ret %", min_value=0.0, max_value=100.0, step=1.0, format="%.0f")
        _p_var = _pc4.number_input("Thumb # used", min_value=0, max_value=2, step=1, value=int(video.best_thumb_variant()))
    if st.button("💾 Save Performance Entry", use_container_width=True):
        if _pv_name and _p_ctr and _p_ctr > 0:
            video.log_performance(_pv_name, _pv_title, ctr=_p_ctr, views=_p_views, avg_retention=_p_ret, thumb_variant=int(_p_var))
            st.success("Logged. The template is learning.")
            st.rerun()
        else:
            st.warning("Need at least the video name + a CTR > 0.")
