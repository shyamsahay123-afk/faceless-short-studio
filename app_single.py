import os
import re
import random
import sqlite3
import traceback
import subprocess
import numpy as np
import requests
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
os.makedirs("b_roll_library", exist_ok=True)

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

def get_setting(key, default_val):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    res = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    if res:
        return res[0]
    return default_val

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
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

def update_short_video(short_id, video_path, audio_path, subtitles_path, status='created'):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""UPDATE shorts SET video_path=?, audio_path=?, subtitles_path=?, status=? WHERE id=?""", (video_path, audio_path, subtitles_path, status, short_id))
    conn.commit()
    conn.close()

# ==============================================================================
# SCRIPT GENERATION TEMPLATES
# ==============================================================================
TRIGGER_HOOK_TEMPLATES = {
    "Curiosity Gap": [
        "What happens when you combine [X] with [Y]? The answer will shock you.",
        "99% of people get this entirely wrong. Here is the exact truth about [Topic].",
        "I tested this secret [Niche] strategy for 7 days. Here is what nobody tells you."
    ],
    "Identity Signaling": [
        "Only the top 1% of highly disciplined [Role/Niche] actually do this one thing.",
        "How to instantly command respect and build a truly unshakeable mindset.",
        "If you want to operate like an elite [Role/Goal], stop acting like everybody else."
    ],
    "Loss Aversion": [
        "Stop doing [Bad Habit/Mistake] right now if you don't want to lose all your [Money/Time/Health].",
        "The biggest mistake stealing your [Desired Outcome] every single day.",
        "If you use this common [Tool/Method], you are practically throwing away your [Goal]."
    ]
}

VALUE_DELIVERY_TEMPLATES = [
    """[VALUE DELIVERY]
Step 1: Eliminate the #1 friction point immediately.
Step 2: Install this powerful daily feedback loop.
Step 3: Execute flawlessly using the 80/20 rule.
Example: Notice how top creators never waste time on fluff.""",
    """[VALUE DELIVERY]
Here is the exact breakdown:
1. The Core Shift: Shift from passive consumption to relentless execution.
2. The Leverage Framework: Use automated systems to do 90% of the heavy lifting.
3. The Execution Sprint: Lock in for 90 minutes deep work every morning."""
]

ENGAGEMENT_CTA_TEMPLATES = [
    "Drop a 🔥 in the comments if you are executing this today!",
    "Save this video so you don't lose it + Follow for daily elite frameworks 📈",
    "Hit Subscribe to join the top 1% building unstoppable futures 👇"
]

def auto_generate_script_local(topic, style_choice):
    if "Dramatic" in style_choice:
        hook_category = "Curiosity Gap"
        trigger_desc = "Create an open loop in the first 2 seconds that makes the brain demand closure."
    elif "Motivational" in style_choice:
        hook_category = "Identity Signaling"
        trigger_desc = "Make the viewer feel they belong to a higher-status group (smart, disciplined, successful)."
    else:
        hook_category = "Loss Aversion"
        trigger_desc = "Highlight what the viewer will lose if they don’t act."
        
    hooks = TRIGGER_HOOK_TEMPLATES.get(hook_category, ["99% of people get this entirely wrong. Here is the exact truth about [Topic]."])
    selected_hook = random.choice(hooks)
    custom_hook = selected_hook.replace("[Topic]", topic).replace("[Niche]", topic).replace("[Role/Niche]", "performer").replace("[Role/Goal]", "leader").replace("[Bad Habit/Mistake]", "wasting focus").replace("[Money/Time/Health]", "focus")
    
    val_delivery = random.choice(VALUE_DELIVERY_TEMPLATES)
    cta = random.choice(ENGAGEMENT_CTA_TEMPLATES)
    
    full_script = f"""[0-3 sec HOOK]\n{custom_hook}\n\n[PSYCHOLOGY TRIGGER: {hook_category}]\n{trigger_desc}\n\n{val_delivery}\n\n[ENGAGEMENT CTA]\n{cta}"""
    title = f"{custom_hook[:45]}..." if len(custom_hook) > 45 else custom_hook
    tags = f"{topic.lower().replace(' ', '')}, shorts, viral, psychology, {hook_category.lower().replace(' ', '')}"
    return title, full_script, tags, hook_category

# ==============================================================================
# VIDEO ENGINE FUNCTIONS
# ==============================================================================
def extract_best_keywords(text, num_words=2):
    stop_words = {'the','a','an','is','are','was','were','of','in','on','at','with','by','to','for','and','but','or','if','then','else','this','that','these','those','i','you','he','she','it','we','they'}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    result = []
    seen = set()
    for w in filtered:
        if w not in seen:
            seen.add(w)
            result.append(w)
            if len(result) >= num_words: break
    return result if result else ["abstract"]

def download_pexels_b_roll(query, api_key):
    clean_query = str(query).replace(" ", "+")
    local_path = os.path.join("b_roll_library", f"{clean_query.lower()}_916.mp4")
    if os.path.exists(local_path): return local_path
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={clean_query}&per_page=12&orientation=portrait"
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            videos = r.json().get("videos", [])
            if videos:
                video_files = videos[0].get("video_files", [])
                target_link = None
                for vf in video_files:
                    if vf.get("file_type") == "video/mp4":
                        w, h = vf.get("width") or 0, vf.get("height") or 0
                        if w < h:
                            target_link = vf.get("link")
                            break
                if not target_link and video_files: target_link = video_files[0].get("link")
                if target_link:
                    video_res = requests.get(target_link, timeout=40)
                    if video_res.status_code == 200:
                        with open(local_path, "wb") as f: f.write(video_res.content)
                        return local_path
    except Exception: pass
    return None

def make_animated_background_clip(duration, theme="Curiosity"):
    width, height = 720, 1280
    if "success" in theme.lower(): c1, c2, orb_color = (6, 78, 59), (15, 23, 42), (16, 185, 129)
    elif "urgency" in theme.lower(): c1, c2, orb_color = (127, 29, 29), (15, 23, 42), (239, 68, 68)
    else: c1, c2, orb_color = (15, 23, 42), (88, 28, 135), (168, 85, 247)
    np.random.seed(42)
    particles = [{'x_pct': np.random.rand(), 'y_start_pct': np.random.rand(), 'speed': 0.04 + 0.08 * np.random.rand(), 'size': 2 + int(4*np.random.rand()), 'opacity': 40 + int(120*np.random.rand())} for _ in range(35)]
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
        for p in particles:
            x, y = int(p['x_pct'] * width), int(((p['y_start_pct'] - p['speed'] * t) % 1.0) * height)
            draw.ellipse([x - p['size'], y - p['size'], x + p['size'], y + p['size']], fill=(orb_color[0], orb_color[1], orb_color[2], p['opacity']))
        cx1, cy1, rad1 = 360 + int(140*np.sin(t*1.1)), 550 + int(90*np.cos(t*0.8)), 180 + int(20*np.sin(t*2.0))
        draw.ellipse([cx1 - rad1, cy1 - rad1, cx1 + rad1, cy1 + rad1], fill=(orb_color[0], orb_color[1], orb_color[2], 55))
        for border in range(0, 160, 10):
            draw.rectangle([border, border, width-border, height-border], outline=(0, 0, 0, int(((border/160)**2)*150)), width=10)
        draw.rectangle([18, 18, width-18, height-18], outline=(255, 255, 255, 35), width=2)
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

def make_ken_burns_clip(img_path, duration):
    base_img = Image.open(img_path).convert("RGB")
    bw, bh = base_img.size
    target_w, target_h = 720, 1280
    img_aspect = bw / bh
    target_aspect = target_w / target_h
    if img_aspect > target_aspect:
        crop_w = int(bh * target_aspect)
        base_img_cropped = base_img.crop(((bw - crop_w) // 2, 0, (bw - crop_w) // 2 + crop_w, bh))
    else:
        crop_h = int(bw / target_aspect)
        base_img_cropped = base_img.crop((0, (bh - crop_h) // 2, bw, (bh - crop_h) // 2 + crop_h))
    cw, ch = base_img_cropped.size
    def make_frame(t):
        scale = 1.0 + 0.15 * (t / duration)
        vw, vh = cw / scale, ch / scale
        left, top = (cw - vw) / 2, (ch - vh) / 2
        cropped = base_img_cropped.crop((left, top, left + vw, top + vh))
        return np.array(cropped.resize((target_w, target_h), Image.Resampling.LANCZOS))
    return VideoClip(make_frame, duration=duration)

def clean_script_for_speech(script_text):
    lines = str(script_text).split('\n')
    cleaned = [l.strip()[1:] if l.strip().startswith(('-', '•')) else l.strip() for l in lines if l.strip() and not (l.strip().startswith('[') and l.strip().endswith(']'))]
    return re.sub(r'\[.*?\]', '', " ".join(cleaned)).replace('+', 'and').replace('👇', 'below').replace('🔥', 'fire').replace('🧠', 'psychology').strip()

def generate_tts_audio(text, voice_name="en-US-ChristopherNeural", output_basename="voice"):
    audio_path, vtt_path = os.path.join("audio_clips", f"{output_basename}.mp3"), os.path.join("audio_clips", f"{output_basename}.vtt")
    try:
        subprocess.run(["edge-tts", "--voice", voice_name, "--text", text, "--write-media", audio_path, "--write-subtitles", vtt_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

def split_subtitles_into_words(subtitles, words_per_clip=1):
    word_subs = []
    for sub in subtitles:
        words = sub['text'].strip().split()
        if not words: continue
        total_chars = sum(len(w) for w in words)
        start_time, total_duration = sub['start'], sub['end'] - sub['start']
        i = 0
        while i < len(words):
            group = words[i:i+words_per_clip]
            group_text = " ".join(group)
            group_chars = sum(len(w) for w in group)
            group_dur = (group_chars / total_chars) * total_duration if total_chars > 0 else total_duration / (len(words) / words_per_clip)
            group_end = start_time + group_dur
            if group_end > sub['end']: group_end = sub['end']
            if group_dur > 0.02:
                word_subs.append({'start': group_start, 'end': group_end, 'text': group_text.upper()})
            start_time = group_end
            i += words_per_clip
    return word_subs

def generate_synthetic_pop_sound(duration=0.08, frequency=650):
    sfx_path = os.path.join("audio_clips", "pop_sfx.wav")
    if os.path.exists(sfx_path): return sfx_path
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(2 * np.pi * (frequency * np.exp(-12 * t)) * t) * np.exp(-32 * t)
    audio_data = (wave * 32767).astype(np.int16)
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate); wf.writeframes(audio_data.tobytes())
    return sfx_path

def generate_synthetic_whoosh_sound(duration=0.45, start_freq=150, end_freq=1100):
    sfx_path = os.path.join("audio_clips", "whoosh_sfx.wav")
    if os.path.exists(sfx_path): return sfx_path
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = (np.sin(2 * np.pi * (start_freq + (end_freq - start_freq) * (t / duration) ** 1.5) * t) * 0.70 + np.random.uniform(-0.15, 0.15, len(t)) * 0.30) * (np.sin(np.pi * (t / duration)) ** 2)
    audio_data = (wave * 32767).astype(np.int16)
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate); wf.writeframes(audio_data.tobytes())
    return sfx_path

def make_progress_bar_clip(duration, width=720, height=1280, bar_height=10, bar_color=(255, 45, 85)):
    def make_frame(t):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        progress_w = int(min(t / duration, 1.0) * width)
        if progress_w > 0:
            draw.rectangle([0, height - bar_height, progress_w, height], fill=(bar_color[0], bar_color[1], bar_color[2], 235))
            if progress_w > 5: draw.rectangle([0, height - bar_height - 2, progress_w, height - bar_height], fill=(bar_color[0], bar_color[1], bar_color[2], 120))
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

def build_subtitle_and_sfx_clips(subtitles, target_w=720, font_size=55, color='yellow', caption_style='standard'):
    display_subs = subtitles
    actual_font_size = font_size
    if caption_style == 'word_pop':
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=1)
        actual_font_size = int(font_size * 1.35)
    text_clips, sfx_clips = [], []
    pop_sfx_path = generate_synthetic_pop_sound()
    POWER_WORDS = {"money": "💰", "cash": "💵", "wealth": "💸", "rich": "💰", "billionaire": "👑", "fail": "❌", "mistake": "❌", "wrong": "🚫", "secret": "🤫", "truth": "💯", "top": "🥇", "success": "📈", "brain": "🧠", "psychology": "🧠", "focus": "🎯", "shock": "😱", "stop": "🛑", "willpower": "💪", "discipline": "🛡️", "unstoppable": "⚡", "fire": "🔥"}
    tick_vol = float(get_setting("tick_volume", 0.18))
    for s in display_subs:
        duration = s['end'] - s['start']
        if duration <= 0.05: continue
        txt = s['text']
        clean_w = re.sub(r'[^\w]', '', txt.lower())
        word_color, word_size, is_power = color, actual_font_size, False
        if caption_style == 'word_pop' and clean_w in POWER_WORDS:
            txt, word_color, word_size, is_power = f"{POWER_WORDS[clean_w]} {txt}", "#39FF14", int(actual_font_size * 1.25), True
        txt_clip = TextClip(text=txt, font_size=word_size, color=word_color, stroke_color='black', stroke_width=4, method='caption', size=(target_w - 80, None), text_align='center')
        text_clips.append(txt_clip.with_duration(duration).with_start(s['start']).with_position(('center', 0.55)))
        if is_power:
            try: sfx_clips.append(AudioFileClip(pop_sfx_path).with_start(s['start']).with_volume_scaled(tick_vol))
            except: pass
    return text_clips, sfx_clips

def load_and_mix_audio(voice_audio_path, bg_music_path=None, bg_music_volume=0.10):
    voice_audio = AudioFileClip(voice_audio_path)
    if not bg_music_path or not os.path.exists(bg_music_path): return voice_audio, voice_audio
    music_audio = AudioFileClip(bg_music_path).with_volume_scaled(bg_music_volume)
    if music_audio.duration < voice_audio.duration:
        music_audio = concatenate_audioclips([music_audio] * int(np.ceil(voice_audio.duration / music_audio.duration)))
    music_audio = music_audio.with_duration(voice_audio.duration)
    return CompositeAudioClip([voice_audio.with_volume_scaled(1.0), music_audio]), voice_audio

def create_hybrid_ai_video(short_id, script_text, uploaded_file_paths=None, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join("video_output", f"short_{short_id}_compiled.mp4")
    progress_cb = kwargs.get("progress_callback", None)
    if progress_cb: progress_cb(0.05, "Cleaning script...")
    spoken_text = clean_script_for_speech(script_text)
    if progress_cb: progress_cb(0.15, "Generating speech...")
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_hybrid")
    db_caption_style = get_setting("caption_style", "word_pop")
    db_music_volume = float(get_setting("bg_music_volume", 0.12))
    db_font_size = int(get_setting("font_size", 55))
    db_whoosh_volume = float(get_setting("whoosh_volume", 0.12))
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", db_music_volume)
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume)
    duration = voice_audio.duration
    cut_duration = 2.0
    num_cuts = int(np.ceil(duration / cut_duration))
    progress_cb_step_weight = 0.40 / num_cuts
    visual_clips, transition_audio_clips = [], []
    whoosh_path = generate_synthetic_whoosh_sound()
    pexels_key = kwargs.get("pexels_api_key", None)
    custom_files = uploaded_file_paths if uploaded_file_paths else []
    for idx in range(num_cuts):
        start_t = idx * cut_duration
        end_t = min(start_t + cut_duration, duration)
        clip_dur = end_t - start_t
        if clip_dur <= 0.05: continue
        clip_added = False
        if idx < len(custom_files):
            file_path = custom_files[idx]
            if os.path.exists(file_path):
                if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Slicing uploaded file {idx+1}...")
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    visual_clips.append(make_ken_burns_clip(file_path, clip_dur).with_start(start_t))
                    clip_added = True
                elif file_path.lower().endswith(('.mp4', '.mov')):
                    try:
                        raw_v = VideoFileClip(file_path)
                        sub_start = np.random.uniform(0.0, raw_v.duration - clip_dur) if raw_v.duration > clip_dur + 1.0 else 0.0
                        visual_clips.append(make_vertical_clip(raw_v.subclipped(sub_start, sub_start + clip_dur).with_start(start_t)))
                        clip_added = True
                    except Exception: pass
        if not clip_added and pexels_key and pexels_key.strip():
            sentence_words = extract_best_keywords(spoken_text, num_words=1)
            search_word = sentence_words[idx % len(sentence_words)] if sentence_words else "abstract"
            if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Downloading stock from Pexels for '{search_word.upper()}'...")
            downloaded_file = download_pexels_b_roll(search_word, pexels_key)
            if downloaded_file and os.path.exists(downloaded_file):
                try:
                    raw_v = VideoFileClip(downloaded_file)
                    sub_start = np.random.uniform(0.0, raw_v.duration - clip_dur) if raw_v.duration > clip_dur + 1.0 else 0.0
                    visual_clips.append(make_vertical_clip(raw_v.subclipped(sub_start, sub_start + clip_dur).with_start(start_t)))
                    clip_added = True
                except Exception: pass
        if not clip_added:
            if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, "Generating fallback abstract loop...")
            visual_clips.append(make_vertical_clip(make_animated_background_clip(clip_dur, theme="Curiosity").with_start(start_t)))
        if idx > 0:
            try: transition_audio_clips.append(AudioFileClip(whoosh_path).with_start(start_t).with_volume_scaled(db_whoosh_volume))
            except: pass
    bg_clip = CompositeVideoClip(visual_clips, size=(720, 1280)).with_duration(duration)
    if progress_cb: progress_cb(0.80, "Emojifying captions...")
    caption_style = kwargs.get("caption_style", db_caption_style)
    text_clips, sfx_clips = build_subtitle_and_sfx_clips(parse_vtt(vtt_path), color=font_color, caption_style=caption_style, font_size=db_font_size)
    bg_clip = bg_clip.with_audio(CompositeAudioClip([mixed_audio] + sfx_clips + transition_audio_clips))
    extra_clips = [make_progress_bar_clip(duration)] if kwargs.get("show_progress_bar", True) else []
    if progress_cb: progress_cb(0.88, "Encoding vertical video...")
    CompositeVideoClip([bg_clip] + text_clips + extra_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast", logger=None)
    if progress_cb: progress_cb(0.98, "Cleaning file locks...")
    try:
        mixed_audio.close(); voice_audio.close(); bg_clip.close()
        for vc in visual_clips: vc.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
        for sc in sfx_clips: sc.close()
        for wc in transition_audio_clips: wc.close()
    except: pass
    if progress_cb: progress_cb(1.00, "Render Complete!")
    return output_video_path, audio_path, vtt_path

# ==============================================================================
# STREAMLIT UI (SINGLE-PAGE SLEEK FACELLESS AI SHORT STUDIO)
# ==============================================================================
st.set_page_config(page_title="Faceless AI Short Studio", page_icon="🎬", layout="centered")

st.markdown("""
<style>
    .reportview-container .main .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .main-header { font-size: 2.8rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #FF2D55, #FF9500); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.1rem; text-align: center; }
    .sub-header { font-size: 1.1rem; color: #8E8E93; margin-bottom: 2rem; text-align: center; }
    .stButton>button {
        border-radius: 10px !important; font-weight: 700 !important; padding: 0.75rem 1.5rem !important; font-size: 18px !important;
        background: linear-gradient(45deg, #FF2D55, #FF5E3A) !important; color: white !important; border: none !important;
        width: 100% !important; box-shadow: 0 4px 15px rgba(255, 45, 85, 0.4) !important; transition: 0.3s !important;
    }
    .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 20px rgba(255, 45, 85, 0.6) !important; }
    div[role="listbox"] { max-height: 250px !important; overflow-y: auto !important; }
    html { scroll-behavior: smooth !important; }
</style>
""", unsafe_allow_html=True)

init_db()

# Permanently auto-save and auto-fill Pexels API Key
saved_key = get_setting("pexels_api_key", "")
pexels_api_key = st.sidebar.text_input(
    "🔑 Pexels API Key", 
    type="password", 
    value=saved_key,
    help="Your key is saved permanently in your local database settings once typed!"
)
if pexels_api_key != saved_key:
    set_setting("pexels_api_key", pexels_api_key)

st.sidebar.divider()
all_shorts = get_all_shorts()
st.sidebar.write(f"📁 Total Videos Generated: **{len(all_shorts)}**")

st.markdown('<div class="main-header">🎬 Faceless AI Short Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">One-Click Fully Automated AI Stock Videos 🤝 Upload Custom Assets & Edit with Prompts</div>', unsafe_allow_html=True)

st.subheader("✍️ Step 1: Video Concept & Prompt")
topic_input = st.text_input("💡 What is your video about? (Topic/Idea)", placeholder="e.g. How to overcome morning laziness, The rules of dark psychology...")

style_choice = st.selectbox("🎨 Video Vibe / Style", [
    "Dark & Dramatic (Mysterious music, purple pulsing loops fallback)",
    "Motivational & Elite (Inspirational music, emerald glowing fallback)",
    "High-Alert Urgency (Dramatic tense music, crimson alarm fallback)",
    "Emotional Story (Calm ambient music, royal blue fallback)"
])

st.divider()

st.subheader("📤 Step 2: Upload Custom Assets (Optional)")
uploaded_files = st.file_uploader(
    "Upload Your Pictures or Videos (.jpg, .png, .mp4, .mov)", 
    type=["jpg", "png", "jpeg", "mp4", "mov"], 
    accept_multiple_files=True,
    help="Optional. If uploaded, the AI will use your files first. If they are shorter than the voiceover, the AI automatically downloads matching vertical Pexels stock video loops to fill the gaps! Leave empty for a 100% automated stock video."
)

st.divider()

st.subheader("🎛️ Step 3: Vocal & Styling Settings")
col_s1, col_s2, col_s3 = st.columns(3)

ai_voice_label = col_s1.selectbox("🔊 Narrator Voice", ["Elite Deep Male", "Energetic Crisp Male", "Warm Professional Female", "Elegant British Female"])
voice_mapping = {"Elite Deep Male": "en-US-ChristopherNeural", "Energetic Crisp Male": "en-US-GuyNeural", "Warm Professional Female": "en-US-AriaNeural", "Elegant British Female": "en-GB-SoniaNeural"}
voice_code = voice_mapping[ai_voice_label]

music_label = col_s2.selectbox("🎵 Background Music", ["Dramatic Beats", "Atmospheric Ambient", "None"])
music_mapping = {"Dramatic Beats": "test.mp3", "Atmospheric Ambient": "backup.mp3", "None": None}
bg_music_path = music_mapping[music_label]

caption_color = col_s3.selectbox("🔤 Caption Color", ["yellow", "white", "cyan", "green", "magenta"])

st.divider()

if st.button("👉 GENERATE & COMPILE MY AI VIDEO NOW 👈", type="primary", use_container_width=True):
    if not topic_input or not topic_input.strip():
        st.error("⚠️ Please enter a Video Topic or Prompt in Step 1 first!")
    elif not pexels_api_key or not pexels_api_key.strip():
        st.error("❌ Pexels API Key is missing! Please enter your Pexels Key in the left sidebar first to allow the AI to generate stock videos and fill gaps!")
    else:
        preset_title, preset_script, preset_tags, trigger_used = auto_generate_script_local(topic_input, style_choice)
        
        all_channels = get_all_channels()
        if not all_channels:
            add_channel("My Faceless Empire", "Self Improvement", "10k")
            all_channels = get_all_channels()
        ch_id = all_channels[0][0]
        
        short_id = add_short(ch_id, preset_title, preset_script, trigger_used, f"{preset_title}\n\nGenerated autonomously.\n\n#AI #Shorts", preset_tags)
        
        progress_container = st.container(border=True)
        with progress_container:
            st.markdown("### 🤖 Live AI Production Console")
            progress_bar = st.progress(0.0)
            status_indicator = st.status("Initializing AI Compilation Engines...", expanded=True)
        
        def render_progress(pct, text):
            progress_bar.progress(pct)
            status_indicator.write(f"🔹 {text} ({int(pct*100)}%)")
            
        custom_filepaths = [save_uploaded_file(f) for f in uploaded_files] if uploaded_files else []
            
        try:
            v_path, a_path, vtt_path = create_hybrid_ai_video(
                short_id, preset_script, custom_filepaths, voice_code, caption_color,
                bg_music_path=bg_music_path, bg_music_volume=0.12, show_progress_bar=True,
                pexels_api_key=pexels_api_key, progress_callback=render_progress, caption_style="word_pop"
            )
            update_short_video(short_id, v_path, a_path, vtt_path)
            status_indicator.update(label="✅ Video Generated Successfully!", state="complete", expanded=False)
            st.success("🎉 Your AI video has been compiled flawlessly!"); st.balloons()
            col_p1, col_p2, col_p3 = st.columns([1.2, 1.6, 1.2])
            with col_p2:
                st.video(v_path)
            
            with st.expander("📋 Click to Copy: Algorithmic SEO Copy Pack"):
                niche_clean = "SelfImprovement"
                trigger_clean = trigger_used.replace(" ", "")
                tags_str = preset_tags
                hashtags_str = f"#{niche_clean} #Shorts #ViralVideo #Psychology #{trigger_clean} #Success"
                optimized_title = f"{preset_title[:85]} 🎯" if not preset_title.endswith("🎯") else preset_title[:90]
                optimized_desc = f"""{optimized_title}\n\n{clean_script_for_speech(preset_script)}\n\nHere is exactly why this psychology secret works:\nWhen you use the [{trigger_used}] mechanism, you build undeniable leverage. Stop acting like amateur performers—build an elite mindset today.\n\n🔔 Hit Subscribe to join the top 1%!\n\n{hashtags_str}"""
                
                st.text_input("📌 Optimized Title:", value=optimized_title)
                st.text_area("📝 Description:", value=optimized_desc, height=180)
                st.text_input("🏷️ Tags & Keywords:", value=tags_str)
                
        except Exception as e:
            status_indicator.update(label="❌ Render Failed!", state="error", expanded=True)
            st.error(f"⚠️ Render failure: {e}")
            with st.expander("🛠️ Debug Terminal & Crash Log Stack Trace"):
                st.code(traceback.format_exc())
