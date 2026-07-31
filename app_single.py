import os
import re
import subprocess
import numpy as np
import sqlite3
import streamlit as st
from PIL import Image, ImageDraw
from moviepy import (
    VideoClip, ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips, CompositeAudioClip, concatenate_audioclips
)

# --- DIRECTORIES ---
os.makedirs("uploaded_assets", exist_ok=True)
os.makedirs("audio_clips", exist_ok=True)
os.makedirs("video_output", exist_ok=True)
os.makedirs("default_assets", exist_ok=True)

# ==============================================================================
# DATABASE ENGINE
# ==============================================================================
DB_NAME = 'shorts_single.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS channels (  
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_name TEXT, niche TEXT,   
        subscribers TEXT, total_shorts INTEGER DEFAULT 0, youtube_credentials TEXT
    )''')  
    c.execute('''CREATE TABLE IF NOT EXISTS shorts (  
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER, title TEXT,  
        script TEXT, trigger TEXT, description TEXT, tags TEXT,  
        video_path TEXT, audio_path TEXT, subtitles_path TEXT, youtube_url TEXT, status TEXT DEFAULT 'idea'  
    )''')  
    conn.commit()
    conn.close()

def get_all_channels():
    conn = sqlite3.connect(DB_NAME)
    channels = conn.cursor().execute("SELECT id, channel_name, niche, subscribers, total_shorts, youtube_credentials FROM channels").fetchall()
    conn.close()
    return channels

def add_channel(name, niche, subs, credentials=""):
    conn = sqlite3.connect(DB_NAME)
    conn.cursor().execute("INSERT INTO channels (channel_name, niche, subscribers, youtube_credentials) VALUES (?, ?, ?, ?)", (name, niche, subs, credentials))
    conn.commit()
    conn.close()

def delete_channel(channel_id):
    conn = sqlite3.connect(DB_NAME)
    conn.cursor().execute("DELETE FROM channels WHERE id=?", (channel_id,))
    conn.cursor().execute("DELETE FROM shorts WHERE channel_id=?", (channel_id,))
    conn.commit()
    conn.close()

def add_short(channel_id, title, script, trigger, description, tags, status='idea'):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""INSERT INTO shorts (channel_id, title, script, trigger, description, tags, status) VALUES (?, ?, ?, ?, ?, ?, ?)""", (channel_id, title, script, trigger, description, tags, status))  
    short_id = c.lastrowid
    conn.commit()
    conn.close()
    return short_id

def get_all_shorts():
    conn = sqlite3.connect(DB_NAME)
    shorts = conn.cursor().execute("""
        SELECT s.id, s.channel_id, s.title, s.script, s.trigger, s.description, s.tags, 
               s.video_path, s.audio_path, s.subtitles_path, s.youtube_url, s.status, ch.channel_name, ch.niche 
        FROM shorts s LEFT JOIN channels ch ON s.channel_id = ch.id ORDER BY s.id DESC
    """).fetchall()
    conn.close()
    return shorts

def get_short(short_id):
    conn = sqlite3.connect(DB_NAME)
    s = conn.cursor().execute("""
        SELECT s.id, s.channel_id, s.title, s.script, s.trigger, s.description, s.tags, 
               s.video_path, s.audio_path, s.subtitles_path, s.youtube_url, s.status, ch.channel_name, ch.niche 
        FROM shorts s LEFT JOIN channels ch ON s.channel_id = ch.id WHERE s.id=?
    """, (short_id,)).fetchone()
    conn.close()
    return s

def update_short_video(short_id, video_path, audio_path, subtitles_path, status='created'):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE shorts SET video_path=?, audio_path=?, subtitles_path=?, status=? WHERE id=?", (video_path, audio_path, subtitles_path, status, short_id))
    s = c.execute("SELECT channel_id FROM shorts WHERE id=?", (short_id,)).fetchone()
    if s:
        c.execute("UPDATE channels SET total_shorts = total_shorts + 1 WHERE id=?", (s[0],))
    conn.commit()
    conn.close()

def update_short_status(short_id, status, youtube_url=None):
    conn = sqlite3.connect(DB_NAME)
    if youtube_url:
        conn.cursor().execute("UPDATE shorts SET status=?, youtube_url=? WHERE id=?", (status, youtube_url, short_id))
    else:
        conn.cursor().execute("UPDATE shorts SET status=? WHERE id=?", (status, short_id))
    conn.commit()
    conn.close()

def delete_short(short_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    s = c.execute("SELECT video_path, audio_path, subtitles_path FROM shorts WHERE id=?", (short_id,)).fetchone()
    if s:
        for fpath in s:
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except:
                    pass
    c.execute("DELETE FROM shorts WHERE id=?", (short_id,))
    conn.commit()
    conn.close()

# ==============================================================================
# PSYCHOLOGY DATA
# ==============================================================================
DEEP_PSYCHOLOGY = {  
    "Curiosity Gap": "Create an open loop in the first 2 seconds that makes the brain demand closure.",  
    "Loss Aversion": "Highlight what the viewer will lose (status, money, time, respect) if they don’t act.",  
    "Identity Signaling": "Make the viewer feel they belong to a higher-status group (smart, disciplined, successful).",  
    "Social Proof + Numbers": "Use real numbers or ‘thousands of people’ to trigger herd mentality.",  
    "Authority + Surprise": "Drop unexpected facts or expert-level insights in the first 5 seconds.",  
    "Scarcity + Urgency": "Create the feeling that this information or opportunity is disappearing.",  
    "Reciprocity Loop": "Give massive value first so the viewer feels obligated to like/comment.",  
    "FOMO (Fear of Missing Out)": "Show that others are already winning while the viewer is left behind.",  
    "Contrast Effect": "Show clear before vs after or right vs wrong in a visual way.",  
    "Emotional Story Hook": "Start with a 3-second personal micro-story that creates instant emotional connection."  
}

TRIGGER_HOOK_TEMPLATES = {
    "Curiosity Gap": [
        "What happens when you combine [Niche] with psychology? The answer will shock you.",
        "99% of people get this entirely wrong. Here is the exact truth about [Niche].",
        "I tested this secret [Niche] strategy for 7 days. Here is what nobody tells you."
    ],
    "Loss Aversion": [
        "Stop doing this in your [Niche] right now if you don't want to lose years of progress.",
        "The biggest mistake stealing your success in [Niche] every single day.",
        "If you use this common framework, you are practically throwing away your goals."
    ],
    "Identity Signaling": [
        "Only the top 1% of highly disciplined [Niche] performers actually do this one thing.",
        "How to instantly command respect and build a truly unshakeable mindset.",
        "If you want to operate at an elite level, stop acting like everybody else."
    ]
}

# ==============================================================================
# VIDEO ENGINE (CINEMATIC & KEN BURNS ANIMATION)
# ==============================================================================
def make_animated_background_clip(duration, theme="Curiosity"):
    width, height = 720, 1280
    theme_str = str(theme).lower()
    
    if "success" in theme_str or "emerald" in theme_str:
        c1, c2, orb_color = (6, 78, 59), (15, 23, 42), (16, 185, 129)
    elif "urgency" in theme_str or "crimson" in theme_str:
        c1, c2, orb_color = (127, 29, 29), (15, 23, 42), (239, 68, 68)
    elif "story" in theme_str or "blue" in theme_str:
        c1, c2, orb_color = (30, 58, 138), (15, 23, 42), (59, 130, 246)
    else:
        c1, c2, orb_color = (15, 23, 42), (88, 28, 135), (168, 85, 247)

    # Pre-generate 35 static particles to draw programmatically
    np.random.seed(42)
    particles = []
    for _ in range(35):
        particles.append({
            'x_pct': np.random.rand(),
            'y_start_pct': np.random.rand(),
            'speed': 0.04 + 0.08 * np.random.rand(),
            'size': 2 + int(4 * np.random.rand()),
            'opacity': 40 + int(120 * np.random.rand())
        })

    base_img = Image.new("RGB", (width, height))
    base_draw = ImageDraw.Draw(base_img)
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * y / height)
        g = int(c1[1] + (c2[1] - c1[1]) * y / height)
        b = int(c1[2] + (c2[2] - c1[2]) * y / height)
        base_draw.line([(0, y), (width, y)], fill=(r, g, b))

    def make_frame(t):
        img = base_img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        
        # 1. Draw subtle grid
        grid_color = (255, 255, 255, 10)
        for gx in range(1, 6):
            draw.line([(gx * 120, 0), (gx * 120, height)], fill=grid_color, width=1)
        for gy in range(1, 10):
            draw.line([(0, gy * 128), (width, gy * 128)], fill=grid_color, width=1)
            
        # 2. Draw floating stars/dust
        for p in particles:
            x = int(p['x_pct'] * width)
            y = int(((p['y_start_pct'] - p['speed'] * t) % 1.0) * height)
            rad = p['size']
            draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(orb_color[0], orb_color[1], orb_color[2], p['opacity']))
            if rad > 3:
                draw.ellipse([x - rad - 2, y - rad - 2, x + rad + 2, y + rad + 2], fill=(orb_color[0], orb_color[1], orb_color[2], int(p['opacity'] * 0.4)))
        
        # 3. Draw huge background glowing soft blobs
        cx1 = 360 + int(140 * np.sin(t * 1.1))
        cy1 = 550 + int(90 * np.cos(t * 0.8))
        rad1 = 180 + int(20 * np.sin(t * 2.0))
        draw.ellipse([cx1 - rad1, cy1 - rad1, cx1 + rad1, cy1 + rad1], fill=(orb_color[0], orb_color[1], orb_color[2], 55))
        
        cx2 = 360 + int(180 * np.cos(t * 0.9))
        cy2 = 800 + int(110 * np.sin(t * 0.6))
        rad2 = 210
        draw.ellipse([cx2 - rad2, cy2 - rad2, cx2 + rad2, cy2 + rad2], fill=(255, 255, 255, 20))

        # 4. Draw vignette
        for border in range(0, 160, 10):
            opacity = int(((border / 160) ** 2) * 150)
            draw.rectangle([border, border, width-border, height-border], outline=(0, 0, 0, opacity), width=10)

        # 5. Neon outline border
        draw.rectangle([18, 18, width-18, height-18], outline=(255, 255, 255, 35), width=2)
        
        return np.array(img)

    return VideoClip(make_frame, duration=duration)

def make_ken_burns_clip(img_path, duration):
    base_img = Image.open(img_path).convert("RGB")
    bw, bh = base_img.size
    target_w, target_h = 720, 1280
    
    def make_frame(t):
        scale = 1.0 + 0.18 * (t / duration)
        vw, vh = bw / scale, bh / scale
        left, top = (bw - vw) / 2, (bh - vh) / 2
        cropped = base_img.crop((left, top, left + vw, top + vh))
        return np.array(cropped.resize((target_w, target_h), Image.Resampling.LANCZOS))
        
    return VideoClip(make_frame, duration=duration)

def clean_script_for_speech(script_text):
    lines = script_text.split('\n')
    cleaned = [l.strip()[1:] if l.strip().startswith(('-', '•')) else l.strip() for l in lines if l.strip() and not (l.strip().startswith('[') and l.strip().endswith(']'))]
    return re.sub(r'\[.*?\]', '', " ".join(cleaned)).replace('+', 'and').replace('👇', 'below').strip()

def generate_tts_audio(text, voice_name="en-US-ChristopherNeural", output_basename="voice"):
    audio_path, vtt_path = os.path.join("audio_clips", f"{output_basename}.mp3"), os.path.join("audio_clips", f"{output_basename}.vtt")
    try:
        subprocess.run(["edge-tts", "--voice", voice_name, "--text", text, "--write-media", audio_path, "--write-subtitles", vtt_path], check=True, stdout=subprocess.PIPE)
        return audio_path, vtt_path
    except Exception:
        from gtts import gTTS
        gTTS(text=text, lang='en').save(audio_path)
        return audio_path, None

def parse_vtt(vtt_path):
    if not vtt_path or not os.path.exists(vtt_path): return []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        matches = re.findall(r'(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*\n((?:(?!\n\n).)*)', f.read(), re.DOTALL)
    
    def time_to_sec(t_str):
        parts = t_str.replace(',', '.').split(':')
        return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])

    subtitles = [{'start': time_to_sec(s), 'end': time_to_sec(e), 'text': txt.strip().replace('\n', ' ')} for s, e, txt in matches if txt.strip()]
    for i in range(len(subtitles) - 1):
        if subtitles[i]['end'] > subtitles[i+1]['start']: subtitles[i]['end'] = subtitles[i+1]['start']
    return subtitles

def make_vertical_clip(clip, target_w=720, target_h=1280):
    w, h = clip.size
    if (w / h) > (target_w / target_h): return clip.resized(height=target_h).cropped(x_center=int(clip.size[0] / 2), width=target_w)
    else: return clip.resized(width=target_w).cropped(y_center=int(clip.size[1] / 2), height=target_h)

# --- DYNAMIC WORD-BY-WORD CHOPPER ---
def split_subtitles_into_words(subtitles, words_per_clip=1):
    word_subs = []
    for sub in subtitles:
        text = sub['text'].strip()
        words = text.split()
        if not words:
            continue
        
        total_chars = sum(len(w) for w in words)
        start_time = sub['start']
        total_duration = sub['end'] - sub['start']
        
        i = 0
        while i < len(words):
            group = words[i:i+words_per_clip]
            group_text = " ".join(group)
            group_chars = sum(len(w) for w in group)
            
            if total_chars > 0:
                group_dur = (group_chars / total_chars) * total_duration
            else:
                group_dur = total_duration / (len(words) / words_per_clip)
                
            group_start = start_time
            group_end = start_time + group_dur
            
            if group_end > sub['end']:
                group_end = sub['end']
                
            if group_dur > 0.02:
                word_subs.append({
                    'start': group_start,
                    'end': group_end,
                    'text': group_text.upper() # Uppercase bold captions!
                })
            
            start_time = group_end
            i += words_per_clip
            
    return word_subs

# --- CINEMATIC VISUAL PROGRESS BAR OVERLAY ---
def make_progress_bar_clip(duration, width=720, height=1280, bar_height=10, bar_color=(255, 45, 85)):
    def make_frame(t):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        
        pct = min(t / duration, 1.0)
        progress_w = int(pct * width)
        
        if progress_w > 0:
            draw.rectangle(
                [0, height - bar_height, progress_w, height], 
                fill=(bar_color[0], bar_color[1], bar_color[2], 230)
            )
            if progress_w > 5:
                draw.rectangle(
                    [0, height - bar_height - 2, progress_w, height - bar_height], 
                    fill=(bar_color[0], bar_color[1], bar_color[2], 100)
                )
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

# --- UPGRADED CAPTIONS GENERATOR ---
def build_subtitle_clips_upgraded(subtitles, target_w=720, font_size=55, color='yellow', caption_style='standard'):
    display_subs = subtitles
    actual_font_size = font_size
    
    if caption_style == 'word_pop':
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=1)
        actual_font_size = int(font_size * 1.35)
        
    text_clips = []
    for s in display_subs:
        duration = s['end'] - s['start']
        if duration <= 0.05: continue
        
        txt_clip = TextClip(
            text=s['text'], 
            font_size=actual_font_size, 
            color=color, 
            stroke_color='black', 
            stroke_width=4, 
            method='caption', 
            size=(target_w - 80, None), 
            text_align='center'
        )
        text_clips.append(
            txt_clip.with_duration(duration)
                    .with_start(s['start'])
                    .with_position(('center', 0.55))
        )
    return text_clips

def build_subtitle_clips(subtitles, target_w=720, font_size=55, color='yellow'):
    return build_subtitle_clips_upgraded(subtitles, target_w, font_size, color, caption_style='standard')

# --- SMART BACKGROUND AUDIO MIXER ---
def load_and_mix_audio(voice_audio_path, bg_music_path=None, bg_music_volume=0.10):
    voice_audio = AudioFileClip(voice_audio_path)
    
    if not bg_music_path or not os.path.exists(bg_music_path):
        return voice_audio, voice_audio
        
    music_audio = AudioFileClip(bg_music_path)
    
    voice_audio = voice_audio.with_volume_scaled(1.0)
    music_audio = music_audio.with_volume_scaled(bg_music_volume)
    
    duration = voice_audio.duration
    if music_audio.duration < duration:
        loops_needed = int(np.ceil(duration / music_audio.duration))
        music_audio = concatenate_audioclips([music_audio] * loops_needed)
        
    music_audio = music_audio.with_duration(duration)
    final_audio = CompositeAudioClip([voice_audio, music_audio])
    return final_audio, voice_audio

# --- PIPELINE 1: INSTANT AI PRESET (ANIMATED) WITH KWARGS ---
def create_video_from_script(short_id, script_text, theme_name, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join("video_output", f"short_{short_id}.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}")
    
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", 0.10)
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume)
    duration = voice_audio.duration
    
    bg_clip = make_animated_background_clip(duration, theme=theme_name).with_audio(mixed_audio)
    bg_clip = make_vertical_clip(bg_clip)
    
    caption_style = kwargs.get("caption_style", "standard")
    text_clips = build_subtitle_clips_upgraded(parse_vtt(vtt_path), color=font_color, caption_style=caption_style)
    
    extra_clips = []
    if kwargs.get("show_progress_bar", True):
        prog_clip = make_progress_bar_clip(duration)
        extra_clips.append(prog_clip)
        
    CompositeVideoClip([bg_clip] + text_clips + extra_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    
    try:
        mixed_audio.close()
        voice_audio.close()
        bg_clip.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
    except:
        pass
        
    return output_video_path, audio_path, vtt_path

# --- PIPELINE 2: CUSTOM PHOTOS (KEN BURNS ANIMATED) ---
def create_video_from_photos(short_id, photo_paths, script_text, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join("video_output", f"short_{short_id}_photos.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_photos")
    
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", 0.10)
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume)
    duration = voice_audio.duration
    
    photo_duration = duration / len(photo_paths)
    photo_clips = [make_ken_burns_clip(p, photo_duration) for p in photo_paths]
        
    bg_clip = concatenate_videoclips(photo_clips).with_audio(mixed_audio).with_duration(duration)
    bg_clip = make_vertical_clip(bg_clip)
    
    caption_style = kwargs.get("caption_style", "standard")
    text_clips = build_subtitle_clips_upgraded(parse_vtt(vtt_path), color=font_color, caption_style=caption_style)
    
    extra_clips = []
    if kwargs.get("show_progress_bar", True):
        prog_clip = make_progress_bar_clip(duration)
        extra_clips.append(prog_clip)
        
    CompositeVideoClip([bg_clip] + text_clips + extra_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    
    try:
        mixed_audio.close()
        voice_audio.close()
        bg_clip.close()
        for pc in photo_clips: pc.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
    except:
        pass
        
    return output_video_path, audio_path, vtt_path

# --- PIPELINE 3: USER VIDEO CLIPS ---
def create_video_from_clips(short_id, clip_paths, script_text, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join("video_output", f"short_{short_id}_clips.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_clips")
    
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", 0.10)
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume)
    duration = voice_audio.duration
    
    raw_clips = [make_vertical_clip(VideoFileClip(cp)) for cp in clip_paths]
    combined_bg = concatenate_videoclips(raw_clips)
    
    if combined_bg.duration < duration:
        combined_bg = concatenate_videoclips([combined_bg] * (int(duration // combined_bg.duration) + 1))
    
    combined_bg = combined_bg.with_duration(duration).with_audio(mixed_audio)
    
    caption_style = kwargs.get("caption_style", "standard")
    text_clips = build_subtitle_clips_upgraded(parse_vtt(vtt_path), color=font_color, caption_style=caption_style)
    
    extra_clips = []
    if kwargs.get("show_progress_bar", True):
        prog_clip = make_progress_bar_clip(duration)
        extra_clips.append(prog_clip)
        
    CompositeVideoClip([combined_bg] + text_clips + extra_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    
    try:
        mixed_audio.close()
        voice_audio.close()
        combined_bg.close()
        for rc in raw_clips: rc.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
    except:
        pass
        
    return output_video_path, audio_path, vtt_path

# ==============================================================================
# YOUTUBE SEO METADATA ENGINE
# ==============================================================================
def generate_viral_seo_pack(title, spoken_script, niche, trigger):
    niche_clean = niche.replace(" ", "").replace("&", "").replace("-", "")
    trigger_clean = trigger.replace(" ", "")

    base_tags = [niche.lower(), "shorts", "viral", "psychology", trigger.lower()]
    extra_tags = ["how to", "mindset", "success tips", "life hacks", "motivation", "secret", niche_clean.lower()]
    all_tags = list(set([t.strip() for t in (base_tags + extra_tags) if t.strip()]))
    
    tags_str = ", ".join(all_tags)
    hashtags_str = f"#{niche_clean} #Shorts #ViralVideo #Psychology #{trigger_clean} #Success"
    optimized_title = f"{title[:85]} 🎯" if not title.endswith("🎯") else title[:90]

    optimized_desc = f"""{optimized_title}

{spoken_script}

Here is exactly why this psychology secret works:
When you use the [{trigger}] mechanism, you build undeniable leverage in {niche}. Stop acting like amateur performers—build an elite mindset today.

🔔 Hit Subscribe to join the top 1% dominating {niche}!

{hashtags_str}"""
    return {"title": optimized_title, "description": optimized_desc, "tags": tags_str, "hashtags": hashtags_str}

# ==============================================================================
# STREAMLIT UI
# ==============================================================================
st.set_page_config(page_title="YT Shorts Premium Studio & SEO Hub", page_icon="🔥", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 3rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #FF3B30, #F5921D, #FF2D55); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }
    .badge { padding: 0.4em 0.8em; font-size: 0.85em; font-weight: 700; color: #fff; border-radius: 0.5rem; }
    .badge-idea { background-color: #3182CE; }
    .badge-created { background-color: #38A169; }
    .badge-uploaded { background-color: #805AD5; }
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

def save_uploaded_file(uploaded_file, target_dir="uploaded_assets"):
    if not uploaded_file: return None
    file_path = os.path.join(target_dir, uploaded_file.name)
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
    return file_path

st.markdown('<div class="main-header">🔥 Ultimate Viral Video & SEO Pack Studio</div>', unsafe_allow_html=True)
st.markdown('Deep Core Psychology Hooks 🤝 24fps Cinematic Animated Video Generator & Elite Viral Copy Hub')

init_db()
all_channels = get_all_channels()
all_shorts = get_all_shorts()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📡 Active Brands", len(all_channels))
col2.metric("💡 Total Ideas Tracked", len(all_shorts))
col3.metric("🎬 Compiled HD Videos", len([s for s in all_shorts if len(s)>7 and s[7] is not None]))
col4.metric("🚀 Live Publications", len([s for s in all_shorts if len(s)>11 and s[11] == 'uploaded']))
st.divider()

page = st.sidebar.radio("🧭 Studio Navigator", ["🎯 Hub & Channels", "🧠 Psychology Lab & Script Creator", "🎬 Premium HD Video Studio", "📺 Creator Video Archive", "🚀 Viral Launch & SEO Hub"])
st.sidebar.divider()
pexels_api_key = st.sidebar.text_input("🔑 Pexels API Key", type="password", help="Enter your Pexels developer key to automatically fetch real 9:16 vertical stock b-roll videos based on your script!")

if page == "🎯 Hub & Channels":
    st.header("📡 Creator Brand Hub")
    if not all_channels:
        st.info("Click below to load our elite target brand instantly.")
        if st.button("✨ Add Premium Demo Channel (Elite Mindset Mastery)", type="primary"):
            add_channel("Elite Mindset Mastery", "Self Improvement & Dark Psychology", "24.5k"); st.rerun()

    for ch in all_channels:
        with st.container():
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"### 📺 **{ch[1]}** (`{ch[2]}`) - Subs: `{ch[3]}` | Videos Tracks: `{ch[4]}`")
            if c2.button("🗑️ Delete Brand", key=f"del_{ch[0]}"): delete_channel(ch[0]); st.rerun()
            st.divider()

    with st.form("add_ch"):
        st.subheader("➕ Add New Brand Identity")
        name = st.text_input("Brand Name")
        niche = st.text_input("Target Domain Niche")
        subs = st.text_input("Subscribers Count (Optional)")
        if st.form_submit_button("Add Brand", type="primary") and name and niche:
            add_channel(name, niche, subs); st.success("Created!"); st.rerun()

elif page == "🧠 Psychology Lab & Script Creator":
    st.header("🧠 Deep Brain Triggers & Hook Lab")
    if not all_channels: st.warning("Add a channel first.")
    else:
        c1, c2 = st.columns(2)
        ch_map = {ch[0]: ch for ch in all_channels}
        ch_id = c1.selectbox("Target Brand", list(ch_map.keys()), format_func=lambda x: f"{ch_map[x][1]} ({ch_map[x][2]})")
        niche = ch_map[ch_id][2]
        trig = c2.selectbox("Psychological Trigger Mechanism", list(DEEP_PSYCHOLOGY.keys()))
        
        st.info(f"**Brain Mechanism:** {DEEP_PSYCHOLOGY[trig]}")
        templates = TRIGGER_HOOK_TEMPLATES.get(trig, ["How to master [Niche] in 3 steps."])
        idea = st.text_area("Hook Concept", value=templates[0].replace("[Niche]", niche), height=100)
        
        if st.button("🚀 Generate High-Conversion Script Pack", type="primary"):
            st.session_state['d_script'] = f"[0-3 sec HOOK]\n{idea}\n\n[PSYCHOLOGY TRIGGER: {trig}]\n{DEEP_PSYCHOLOGY[trig]}\n\n[VALUE DELIVERY]\nStep 1: Eliminate the #1 friction point immediately.\nStep 2: Build an elite daily feedback loop.\n\n[ENGAGEMENT CTA]\nDrop a 🔥 in the comments if you are executing this today!"
            st.session_state['d_title'] = idea[:60]
            st.session_state['d_tags'] = f"{niche.lower().replace(' ','')}, shorts, viral, psychology"
            
        if 'd_script' in st.session_state:
            with st.form("save_form"):
                title = st.text_input("Video Title", value=st.session_state['d_title'])
                script = st.text_area("Production Script", value=st.session_state['d_script'], height=250)
                tags = st.text_input("Keywords", value=st.session_state['d_tags'])
                if st.form_submit_button("💾 Save Short to Premium Video Studio", type="primary"):
                    add_short(ch_id, title, script, trig, f"{title}\n\n{script}\n\n#{niche.replace(' ','')} #Shorts", tags)
                    st.success("Stored! Head to **Premium HD Video Studio** to render!")
                    del st.session_state['d_script']; st.rerun()

elif page == "🎬 Premium HD Video Studio":
    st.header("🎬 Premium HD Animated Video Studio")
    pending = [s for s in all_shorts if len(s)>7 and s[7] is None]
    if not pending: st.success("🌟 All your stored Shorts have compiled HD videos! Create a new concept in **Psychology Lab**.")
    else:
        s_id = st.selectbox("Select Pending Short to Render:", pending, format_func=lambda s: f"[{s[12]}] {s[2]} (Trigger: {s[4]})")[0]
        curr = [s for s in pending if s[0] == s_id][0]
        script = curr[3]
        
        with st.expander("👁️ View Original Script vs Spoken Lines"):
            st.code(script); st.write(f"`{clean_script_for_speech(script)}`")
            
        method = st.radio("Pipeline Method:", ["✨ Method 1: Cinematic Animated Presets (24fps moving abstract glowing orbs)", "📸 Method 2: Custom Slideshow Photos (Ken Burns smooth zoom animation)", "🎞️ Method 3: Raw Video Trimming (Auto-scales user action clips to perfect 9:16 vertical)"])
        
        st.subheader("🎨 Custom Styling Studio")
        col_c1, col_c2, col_c3 = st.columns(3)
        ai_voice = col_c1.selectbox("🔊 AI Narrator Voice", ["en-US-ChristopherNeural (Elite Deep Male)", "en-US-GuyNeural (Energetic Crisp Male)", "en-US-AriaNeural (Warm Professional Female)", "en-GB-SoniaNeural (Elegant British Female)"])
        font_color = col_c2.selectbox("🔤 Dynamic Caption Color", ["yellow", "white", "cyan", "green", "red", "magenta"])
        cap_style = col_c3.selectbox("🔤 Subtitle Style", ["🔥 Word-Pop (Hormozi style)", "Full Sentence (Standard)"])
        
        caption_style_code = "word_pop" if "Word-Pop" in cap_style else "standard"
        voice_code = ai_voice.split(" ")[0]
        
        st.markdown("**🎵 Background Audio & Overlays:**")
        col_m1, col_m2, col_m3 = st.columns(3)
        music_sel = col_m1.selectbox("🎵 Soundtrack", ["None", "Dramatic Beats (test.mp3)", "Atmospheric Ambient (backup.mp3)"])
        music_volume = col_m2.slider("🎵 Volume Scale", min_value=0.0, max_value=0.30, value=0.12, step=0.01, format="%.2f")
        show_progress_bar = col_m3.checkbox("🚨 Show Progress Bar (Glowing Crimson)", value=True)
        
        bg_music_path = None
        if "test.mp3" in music_sel:
            bg_music_path = "test.mp3"
        elif "backup.mp3" in music_sel:
            bg_music_path = "backup.mp3"
            
        st.divider()
        
        if method.startswith("✨ Method 1"):
            bg_choice = st.selectbox("Cinematic Tone Profile:", ["Curiosity Deep Navy Profile", "Success Premium Emerald Profile", "Urgency Crimson Profile", "Story Royal Blue Profile"]).split(" ")[0]
            if st.button("🚀 Render 24fps Cinematic Animated Video Now", type="primary", use_container_width=True):
                with st.spinner("Generating AI Voice, WebVTT timings, computing 24fps visual animation frames, and compiling MP4..."):
                    try:
                        v_path, a_path, vtt_path = create_video_from_script(
                            s_id, 
                            script, 
                            bg_choice, 
                            voice_code, 
                            font_color,
                            caption_style=caption_style_code,
                            bg_music_path=bg_music_path,
                            bg_music_volume=music_volume,
                            show_progress_bar=show_progress_bar,
                            pexels_api_key=pexels_api_key
                        )
                        update_short_video(s_id, v_path, a_path, vtt_path); st.success("🎉 Rendered Flawlessly!"); st.balloons(); st.video(v_path)
                    except Exception as e: st.error(f"Render Error: {e}")
                        
        elif method.startswith("📸 Method 2"):
            photos = st.file_uploader("Upload Photos", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            if photos and st.button("🚀 Render Ken Burns Slideshow Video Now", type="primary", use_container_width=True):
                with st.spinner("Saving images, generating audio, applying Ken Burns zoom, and rendering final MP4..."):
                    photo_paths = [save_uploaded_file(p) for p in photos]
                    try:
                        v_path, a_path, vtt_path = create_video_from_photos(
                            s_id, 
                            photo_paths, 
                            script, 
                            voice_code, 
                            font_color,
                            caption_style=caption_style_code,
                            bg_music_path=bg_music_path,
                            bg_music_volume=music_volume,
                            show_progress_bar=show_progress_bar
                        )
                        update_short_video(s_id, v_path, a_path, vtt_path); st.success("🎉 Ken Burns Video Rendered Flawlessly!"); st.video(v_path)
                    except Exception as e: st.error(f"Render Error: {e}")

        elif method.startswith("🎞️ Method 3"):
            clips = st.file_uploader("Upload Raw Action Clips (.mp4 / .mov)", type=["mp4", "mov"], accept_multiple_files=True)
            if clips and st.button("🚀 Render Action Video Now", type="primary", use_container_width=True):
                with st.spinner("Trimming clips, scaling to perfect vertical 1080x1920, and compiling MP4..."):
                    clip_paths = [save_uploaded_file(c) for c in clips]
                    try:
                        v_path, a_path, vtt_path = create_video_from_clips(
                            s_id, 
                            clip_paths, 
                            script, 
                            voice_code, 
                            font_color,
                            caption_style=caption_style_code,
                            bg_music_path=bg_music_path,
                            bg_music_volume=music_volume,
                            show_progress_bar=show_progress_bar
                        )
                        update_short_video(s_id, v_path, a_path, vtt_path); st.success("🎉 Action Video Rendered Flawlessly!"); st.video(v_path)
                    except Exception as e: st.error(f"Render Error: {e}")

elif page == "📺 Creator Video Archive":
    st.header("📺 Creator Video Archive")
    for s in all_shorts:
        s_id, _, title, script, trigger, _, tags, v_path, a_path, _, yt_url, status, ch_name, ch_niche = s[:14]
        with st.container():
            c1, c2 = st.columns([2, 3])
            c1.markdown(f"### 🎬 **{title}**\n**Brand:** `{ch_name}` (`{ch_niche}`) | **Trigger:** `{trigger}`\n**State:** <span class='badge badge-{status}'>{status.upper()}</span>", unsafe_allow_html=True)
            if yt_url: c1.markdown(f"🔗 **Live Link:** [{yt_url}]({yt_url})")
            with c1.expander("📝 Read Script"): st.write(script); st.code(tags)
            if c1.button("🗑️ Delete", key=f"del_{s_id}"): delete_short(s_id); st.rerun()
                
            if v_path and os.path.exists(v_path):
                c2.video(v_path)
                with open(v_path, "rb") as vf: c2.download_button("📥 Download Final MP4", vf, f"Short_{s_id}.mp4", "video/mp4", key=f"dl_v_{s_id}", use_container_width=True)
                if a_path and os.path.exists(a_path):
                    with open(a_path, "rb") as af: c2.download_button("📥 Download Voiceover MP3", af, f"Voice_{s_id}.mp3", "audio/mp3", key=f"dl_a_{s_id}", use_container_width=True)
            else: c2.warning("No video rendered yet.")
        st.divider()

elif page == "🚀 Viral Launch & SEO Hub":
    st.header("🚀 Algorithmic SEO Copy Pack Hub")
    st.write("All complex YouTube OAuth / API linking has been completely removed. Grab your Algorithmic Viral Copy Metadata Pack below and publish instantly onto your YouTube Studio, TikTok, or Instagram Reels!")
    
    ready = [s for s in all_shorts if len(s)>11 and s[11] == 'created']
    if not ready: st.info("🌟 No compiled videos ready for launch right now. Render a video first in **Premium HD Video Studio**!")
    else:
        s_id = st.selectbox("🎯 Select Compiled Video to Launch:", ready, format_func=lambda s: f"[{s[12]}] {s[2]}")[0]
        up = [s for s in ready if s[0] == s_id][0]
        u_id, _, u_title, u_script, u_trigger, _, _, u_vpath = up[:8]
        u_chniche = up[13] if len(up)>13 else "Psychology"
        
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown("### 📋 Ultimate Algorithmic SEO Pack")
            seo = generate_viral_seo_pack(u_title, clean_script_for_speech(u_script), u_chniche, u_trigger)
            st.text_input("**📌 Algorithmic Viral Title:**", value=seo["title"])
            st.text_area("**📝 YouTube Optimized Description:**", value=seo["description"], height=250)
            st.text_input("**🏷️ Premium Tag Keywords:**", value=seo["tags"])
            st.text_input("**🔗 Hashtag Cluster:**", value=seo["hashtags"])
            
            st.divider()
            with st.form("mark_live"):
                url = st.text_input("Optional: Paste published live video link (e.g. https://www.youtube.com/shorts/XYZ):")
                if st.form_submit_button("✅ Successfully Published on Socials", type="primary"):
                    update_short_status(u_id, 'uploaded', url); st.rerun()
                    
        with c2:
            st.markdown("### 🎬 Video Preview & Direct Grab")
            if u_vpath and os.path.exists(u_vpath):
                st.video(u_vpath)
                with open(u_vpath, "rb") as vf:
                    st.download_button("📥 Download HD Vertical Video (.mp4)", vf, f"{u_title.replace(' ', '_')}.mp4", "video/mp4", type="primary", use_container_width=True)
            else: st.warning("Video missing on disk.")
