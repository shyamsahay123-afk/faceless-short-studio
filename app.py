import os
import re
import random
import traceback
import xml.etree.ElementTree as ET
import requests
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

# --- Ensure Directories Exist ---
os.makedirs("uploaded_assets", exist_ok=True)

def save_uploaded_file(uploaded_file, target_dir="uploaded_assets"):
    if not uploaded_file: return None
    file_path = os.path.join(target_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

# --- LOCAL FILE API KEY AUTO-SAVER ---
def load_pexels_key():
    if os.path.exists("pexels_key.txt"):
        try:
            with open("pexels_key.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            pass
    return ""

def save_pexels_key(key):
    try:
        with open("pexels_key.txt", "w", encoding="utf-8") as f:
            f.write(str(key).strip())
    except:
        pass

# --- REAL-TIME GOOGLE & YOUTUBE SHORTS TREND BOARD CRAWLER ---
def fetch_trending_shorts_concepts():
    """
    Parses live search trends RSS from Google and automatically rewrites them
    into highly clickable, viral short-form mindset & psychology concepts.
    """
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
                t_text = item.text
                if t_text:
                    base_trends.insert(idx, f"Why high-performers study the '{t_text}' focus shift")
    except:
        pass
    return list(set(base_trends))[:5]

# --- Standalone AI Script Draft Generator ---
def auto_generate_script_local(topic, style_choice):
    if "Dramatic" in style_choice:
        hook_category = "Curiosity Gap"
        trigger_desc = "Create an open loop in the first 2 seconds that makes the brain demand closure."
    elif "Motivational" in style_choice:
        hook_category = "Identity Signaling"
        trigger_desc = "Make the viewer feel they belong to a higher-status group (smart, disciplined, successful)."
    elif "High-Alert" in style_choice:
        hook_category = "Loss Aversion"
        trigger_desc = "Highlight what the viewer will lose if they don’t act."
    else:
        hook_category = "Emotional Story Hook"
        trigger_desc = "Start with a 3-second personal micro-story that creates instant emotional connection."
        
    hooks = psych.TRIGGER_HOOK_TEMPLATES.get(hook_category, ["99% of people get this entirely wrong. Here is the exact truth about [Topic]."])
    selected_hook = random.choice(hooks)
    custom_hook = selected_hook.replace("[Topic]", topic).replace("[Niche]", topic).replace("[Role/Niche]", "performer").replace("[Role/Goal]", "leader").replace("[Bad Habit/Mistake]", "wasting focus").replace("[Money/Time/Health]", "focus")
    
    val_delivery = random.choice(psych.VALUE_DELIVERY_TEMPLATES)
    cta = random.choice(psych.ENGAGEMENT_CTA_TEMPLATES)
    
    full_script = f"""[0-3 sec HOOK]\n{custom_hook}\n\n[PSYCHOLOGY TRIGGER: {hook_category}]\n{trigger_desc}\n\n{val_delivery}\n\n[ENGAGEMENT CTA]\n{cta}"""
    title = f"{custom_hook[:45]}..." if len(custom_hook) > 45 else custom_hook
    tags = f"{topic.lower().replace(' ', '')}, shorts, viral, psychology, {hook_category.lower().replace(' ', '')}"
    
    return title, full_script, tags, hook_category

# ==============================================================================
# INITIALIZE DATABASE & LOCAL API AUTOSAVER
# ==============================================================================
db.init_db()
saved_key = load_pexels_key()
pexels_api_key = st.sidebar.text_input(
    "🔑 Pexels API Key", 
    type="password", 
    value=saved_key,
    help="Your key is saved permanently on your PC once typed!"
)
if pexels_api_key != saved_key:
    save_pexels_key(pexels_api_key)

st.sidebar.divider()
all_shorts = db.get_all_shorts()
st.sidebar.write(f"📁 Total Videos Generated: **{len(all_shorts)}**")

# ==============================================================================
# MAIN PAGE INTERFACE
# ==============================================================================
st.markdown('<div class="main-header">🎬 Faceless AI Short Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">YouTube Trends Crawler 🤝 Real-Time Interactive AI Script Editor 🤝 Hybrid Video Compiler</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# STEP 1: REAL-TIME YOUTUBE SHORTS TREND BOARD
# ------------------------------------------------------------------------------
st.subheader("📡 Step 1: Live YouTube Shorts Trend Board")
st.write("Our automated scraper crawled Google and YouTube Trends right now. Click on any viral concept below to automatically load it as your next video prompt!")

trending_concepts = fetch_trending_shorts_concepts()
for idx, trend in enumerate(trending_concepts):
    with st.container():
        st.markdown(
            f"""<div class="trend-badge">
                <span>🔥 <b>Trend #{idx+1}:</b> {trend}</span>
            </div>""", 
            unsafe_allow_html=True
        )
        if st.button("🔌 Use This Concept Prompt", key=f"trend_btn_{idx}"):
            st.session_state['topic_override'] = trend
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
        "Emotional Story (Calm ambient music, royal blue fallback)"
    ])

# Draft Script Button (Triggers the Interactive Editor Phase!)
if st.button("🤖 STEP 1: DRAFT SCRIPT & ANALYZE KEYWORDS", type="primary", use_container_width=True):
    if not topic_input or not topic_input.strip():
        st.error("⚠️ Please enter a Topic or select a trend first!")
    else:
        title, script, tags, trigger_used = auto_generate_script_local(topic_input, style_choice)
        st.session_state['active_title'] = title
        st.session_state['active_script'] = script
        st.session_state['active_tags'] = tags
        st.session_state['active_trigger'] = trigger_used
        st.success("🎉 Script Drafted successfully! Tweak and edit your spoken lines below before rendering!")

# INTERACTIVE SCRIPT EDITOR CONTAINER (Shows ONLY if script has been generated)
if 'active_script' in st.session_state:
    st.markdown("### 📝 The Interactive AI Editor")
    st.write("You can rewrite, tweak, or fully customize the generated script or stock search tags below:")
    
    edited_title = st.text_input("📌 Video Draft Title (For your database):", value=st.session_state['active_title'])
    edited_script = st.text_area("✍️ Spoken Script & Notes (AI will speak exactly what you type here!):", value=st.session_state['active_script'], height=250)
    
    # Analyze B-Roll search keywords in real-time!
    spoken_clean = video.clean_script_for_speech(edited_script)
    keywords_list = video.extract_best_keywords(spoken_clean, num_words=6)
    
    st.markdown("**🔍 Visual Stock B-Roll Search Prompts:**")
    st.write(f"The AI will search and download beautiful vertical video loops for these terms: `{', '.join(keywords_list)}`")
    
    st.session_state['active_title'] = edited_title
    st.session_state['active_script'] = edited_script

st.divider()

# ------------------------------------------------------------------------------
# STEP 3: VOCAL & STYLING SETTINGS
# ------------------------------------------------------------------------------
st.subheader("🎛️ Step 3: Vocal & Styling Settings")
col_s1, col_s2, col_s3 = st.columns(3)

ai_voice_label = col_s1.selectbox("🔊 Narrator Voice", ["Elite Deep Male", "Energetic Crisp Male", "Warm Professional Female", "Elegant British Female"])
voice_mapping = {"Elite Deep Male": "en-US-ChristopherNeural", "Energetic Crisp Male": "en-US-GuyNeural", "Warm Professional Female": "en-US-AriaNeural", "Elegant British Female": "en-GB-SoniaNeural"}
voice_code = voice_mapping[ai_voice_label]

pacing_label = col_s2.selectbox("⏱️ Video Pacing", [
    "⚡ Adrenaline ADHD (1.3s cuts)",
    "🎬 Cinematic (2.0s cuts)",
    "🌌 Mindful Slower (3.2s cuts)"
])
pacing_mapping = {
    "⚡ Adrenaline ADHD (1.3s cuts)": 1.3,
    "🎬 Cinematic (2.0s cuts)": 2.0,
    "🌌 Mindful Slower (3.2s cuts)": 3.2
}
cut_duration_val = pacing_mapping[pacing_label]

caption_theme_label = col_s3.selectbox("🔤 Caption Theme", ["🔥 Hormozi Gold style", "🌌 Cyberpunk Neon", "⚪ Minimalist White"])
caption_mapping = {
    "🔥 Hormozi Gold style": ("hormozi", "yellow"),
    "🌌 Cyberpunk Neon": ("cyberpunk", "cyan"),
    "⚪ Minimalist White": ("minimalist", "white")
}
caption_style_code, caption_color = caption_mapping[caption_theme_label]

bg_music_path = "test.mp3" if ("Dramatic" in style_choice or "Urgency" in style_choice) else "backup.mp3"
show_progress_bar = True
music_volume = 0.12

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
    if 'active_script' not in st.session_state:
        st.error("⚠️ Please click '🤖 STEP 1: DRAFT SCRIPT & ANALYZE KEYWORDS' first to review and edit your script before compiling!")
    elif not pexels_api_key or not pexels_api_key.strip():
        st.error("❌ Pexels API Key is missing! Please enter your Pexels Key in the left sidebar first to allow the AI to generate stock videos and fill gaps!")
    else:
        # Load edited variables from state
        preset_title = st.session_state['active_title']
        preset_script = st.session_state['active_script']
        preset_tags = st.session_state.get('active_tags', 'shorts, viral')
        trigger_used = st.session_state.get('active_trigger', 'Identity Signaling')
        
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
        
        progress_container = st.container(border=True)
        with progress_container:
            st.markdown("### 🤖 Live AI Production Console")
            progress_bar = st.progress(0.0)
            status_indicator = st.status("Initializing AI Compilation Engines...", expanded=True)
        
        def render_progress(pct, text):
            progress_bar.progress(pct)
            status_indicator.write(f"🔹 {text} ({int(pct*100)}%)")
            
        custom_filepaths = []
        if uploaded_files:
            custom_filepaths = [save_uploaded_file(f) for f in uploaded_files]
            
        try:
            # Call our ultimate hybrid compiler!
            v_path, a_path, vtt_path = video.create_hybrid_ai_video(
                short_id, 
                preset_script, 
                custom_filepaths, 
                voice_code, 
                caption_color,
                bg_music_path=bg_music_path,
                bg_music_volume=music_volume,
                show_progress_bar=show_progress_bar,
                pexels_api_key=pexels_api_key,
                progress_callback=render_progress,
                caption_style=caption_style_code,
                cut_duration=cut_duration_val
            )
            
            db.update_short_video(short_id, v_path, a_path, vtt_path, status='created')
            status_indicator.update(label="✅ Video Generated Successfully!", state="complete", expanded=False)
            
            st.success("🎉 Your AI video has been compiled flawlessly!"); st.balloons()
            
            # Display player nicely
            col_p1, col_p2, col_p3 = st.columns([1.2, 1.6, 1.2])
            with col_p2:
                st.video(v_path)
            
            with st.expander("📋 Click to Copy: Algorithmic SEO Copy Pack"):
                seo_data = yt.generate_viral_seo_pack(preset_title, video.clean_script_for_speech(preset_script), "Self Improvement", trigger_used)
                st.text_input("📌 Optimized Title:", value=seo_data["title"])
                st.text_area("📝 Description:", value=seo_data["description"], height=180)
                st.text_input("🏷️ Tags & Keywords:", value=seo_data["tags"])
                
        except Exception as e:
            status_indicator.update(label="❌ Render Failed!", state="error", expanded=True)
            st.error(f"⚠️ Render failure: {e}")
            with st.expander("🛠️ Debug Terminal & Crash Log Stack Trace"):
                st.code(traceback.format_exc())
