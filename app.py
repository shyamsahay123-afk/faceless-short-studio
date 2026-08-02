import os
import re
import random
import traceback
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
    div[data-baseweb="select"] {
        border-radius: 8px !important;
    }
    /* Prevent selectbox dropdown navigation from scrolling the main page */
    div[role="listbox"] {
        max-height: 250px !important;
        overflow-y: auto !important;
    }
    html {
        scroll-behavior: smooth !important;
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

# --- LOCAL FILE API KEY AUTO-SAVER (100% RELIABLE ON RESTART) ---
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

# --- Local Standalone AI Script Draft Generator ---
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
    
    # Customise template words neatly
    custom_hook = selected_hook.replace("[Topic]", topic).replace("[Niche]", topic).replace("[Role/Niche]", "performer").replace("[Role/Goal]", "leader").replace("[Bad Habit/Mistake]", "wasting focus").replace("[Money/Time/Health]", "focus")
    
    val_delivery = random.choice(psych.VALUE_DELIVERY_TEMPLATES)
    cta = random.choice(psych.ENGAGEMENT_CTA_TEMPLATES)
    
    full_script = f"""[0-3 sec HOOK]\n{custom_hook}\n\n[PSYCHOLOGY TRIGGER: {hook_category}]\n{trigger_desc}\n\n{val_delivery}\n\n[ENGAGEMENT CTA]\n{cta}"""
    title = f"{custom_hook[:45]}..." if len(custom_hook) > 45 else custom_hook
    tags = f"{topic.lower().replace(' ', '')}, shorts, viral, psychology, {hook_category.lower().replace(' ', '')}"
    
    return title, full_script, tags, hook_category

# ==============================================================================
# DATABASE & SETTINGS INITIALIZATION
# ==============================================================================
db.init_db()

# Permanently auto-save and auto-fill Pexels API Key using plain-text file
saved_key = load_pexels_key()
pexels_api_key = st.sidebar.text_input(
    "🔑 Pexels API Key", 
    type="password", 
    value=saved_key,
    help="Your key is saved permanently on your PC so you never have to type it again!"
)
if pexels_api_key != saved_key:
    save_pexels_key(pexels_api_key)

st.sidebar.divider()
st.sidebar.markdown("**🎬 Workspace Stats:**")
all_shorts = db.get_all_shorts()
st.sidebar.write(f"📁 Total Videos Generated: **{len(all_shorts)}**")

# ==============================================================================
# MAIN PAGE INTERFACE
# ==============================================================================
st.markdown('<div class="main-header">🎬 Faceless AI Short Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">One-Click Fully Automated AI Stock Videos 🤝 Upload Custom Assets & Edit with Prompts</div>', unsafe_allow_html=True)

# 1. Concept & Topic Inputs
st.subheader("✍️ Step 1: Video Concept & Prompt")
topic_input = st.text_input("💡 What is your video about? (Topic/Idea)", placeholder="e.g. How to overcome morning laziness, The rules of dark psychology...")

style_choice = st.selectbox("🎨 Video Vibe / Style", [
    "Dark & Dramatic (Mysterious music, purple pulsing loops fallback)",
    "Motivational & Elite (Inspirational music, emerald glowing fallback)",
    "High-Alert Urgency (Dramatic tense music, crimson alarm fallback)",
    "Emotional Story (Calm ambient music, royal blue fallback)"
])

st.divider()

# 2. Hybrid File Uploads (Optional)
st.subheader("📤 Step 2: Upload Custom Assets (Optional)")
uploaded_files = st.file_uploader(
    "Upload Your Pictures or Videos (.jpg, .png, .mp4, .mov)", 
    type=["jpg", "png", "jpeg", "mp4", "mov"], 
    accept_multiple_files=True,
    help="Optional. If uploaded, the AI will use your files first. If they are shorter than the voiceover, the AI automatically downloads matching vertical Pexels stock video loops to fill the gaps! Leave empty for a 100% automated stock video."
)

st.divider()

# 3. Simple Styling Options (Dropdowns with easy words!)
st.subheader("🎛️ Step 3: Vocal & Styling Settings")
col_s1, col_s2, col_s3 = st.columns(3)

ai_voice_label = col_s1.selectbox("🔊 Narrator Voice", [
    "Elite Deep Male", 
    "Energetic Crisp Male", 
    "Warm Professional Female", 
    "Elegant British Female"
])

voice_mapping = {
    "Elite Deep Male": "en-US-ChristopherNeural",
    "Energetic Crisp Male": "en-US-GuyNeural",
    "Warm Professional Female": "en-US-AriaNeural",
    "Elegant British Female": "en-GB-SoniaNeural"
}
voice_code = voice_mapping[ai_voice_label]

music_label = col_s2.selectbox("🎵 Background Music", [
    "Dramatic Beats", 
    "Atmospheric Ambient", 
    "None"
])

music_mapping = {
    "Dramatic Beats": "test.mp3",
    "Atmospheric Ambient": "backup.mp3",
    "None": None
}
bg_music_path = music_mapping[music_label]

caption_color = col_s3.selectbox("🔤 Caption Color", [
    "yellow", 
    "white", 
    "cyan", 
    "green", 
    "magenta"
])

# Under-the-hood settings (saved in background)
show_progress_bar = True
music_volume = 0.12

st.divider()

# ==============================================================================
# SINGLE GIANT ONE-CLICK MASTER ACTION BUTTON
# ==============================================================================
if st.button("👉 GENERATE & COMPILE MY AI VIDEO NOW 👈", type="primary", use_container_width=True):
    if not topic_input or not topic_input.strip():
        st.error("⚠️ Please enter a Video Topic or Prompt in Step 1 first!")
    elif not pexels_api_key or not pexels_api_key.strip():
        st.error("❌ Pexels API Key is missing! Please enter your Pexels Key in the left sidebar first to allow the AI to generate stock videos and fill gaps!")
    else:
        # 1. Silently write the psychology script in the background
        preset_title, preset_script, preset_tags, trigger_used = auto_generate_script_local(topic_input, style_choice)
        
        # Add to channels database if not exists
        all_channels = db.get_all_channels()
        if not all_channels:
            db.add_channel("My Faceless Empire", "Self Improvement", "10k")
            all_channels = db.get_all_channels()
        ch_id = all_channels[0][0]
        
        # Save short concept
        short_id = db.add_short(
            ch_id, 
            preset_title, 
            preset_script, 
            trigger_used, 
            f"{preset_title}\n\nGenerated autonomously.\n\n#AI #Shorts", 
            preset_tags
        )
        
        # 2. Setup progress monitoring console
        progress_container = st.container(border=True)
        with progress_container:
            st.markdown("### 🤖 Live AI Production Console")
            progress_bar = st.progress(0.0)
            status_indicator = st.status("Initializing AI Compilation Engines...", expanded=True)
        
        def render_progress(pct, text):
            progress_bar.progress(pct)
            status_indicator.write(f"🔹 {text} ({int(pct*100)}%)")
            
        # Process custom uploaded files
        custom_filepaths = []
        if uploaded_files:
            custom_filepaths = [save_uploaded_file(f) for f in uploaded_files]
            
        # Run render!
        try:
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
                caption_style="word_pop"
            )
            
            # Save success state
            db.update_short_video(short_id, v_path, a_path, vtt_path, status='created')
            status_indicator.update(label="✅ Video Generated Successfully!", state="complete", expanded=False)
            
            st.success("🎉 Your AI video has been compiled flawlessly!"); st.balloons()
            
            # Display final video player
            st.video(v_path)
            
            # Simple metadata pack dropdown
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
