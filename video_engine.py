import os
import re
import asyncio
import threading
import subprocess
import numpy as np
import requests
import time
import random
import edge_tts
import db_manager as db_settings
from moviepy import (
    VideoClip, ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips, CompositeAudioClip, concatenate_audioclips
)
from PIL import Image, ImageDraw

# ==============================================================================
# --- PROACTIVE WINDOWS & PYTHON 3.14 COMPATIBILITY PATCHES ---
# ==============================================================================

original_poll = subprocess.Popen.poll
def safe_poll(self):
    try:
        return original_poll(self)
    except OSError as e:
        if getattr(e, 'winerror', None) == 6 or "handle is invalid" in str(e).lower():
            return 0
        raise
subprocess.Popen.poll = safe_poll

def run_async_in_thread(coro):
    result = []
    exception = []
    def worker():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(coro)
            result.append(res)
            loop.close()
        except Exception as e:
            exception.append(e)
            
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    if exception:
        raise exception[0]
    return result[0] if result else None

# ==============================================================================

AUDIO_DIR = "audio_clips"
VIDEO_DIR = "video_output"
DEFAULT_DIR = "default_assets"
B_ROLL_DIR = "b_roll_library"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(DEFAULT_DIR, exist_ok=True)
os.makedirs(B_ROLL_DIR, exist_ok=True)

# --- ADVANCED SEMANTIC CONCEPT EXPANDER (THE HUMAN EDITOR BRUTAL SECRET) ---
# Translates dry text keywords into visually stunning, cinematic b-roll search prompts
CONCEPT_EXPANSIONS = {
    "percent": "luxury penthouse view night",
    "disciplined": "workout training morning sweat",
    "minds": "brain connection cyber glow",
    "mind": "glowing human brain macro",
    "neuro": "glowing digital synapses grid",
    "focus": "macro focus eye iris",
    "boundary": "dark locked gate neon light",
    "harvard": "classic library old books bookshelf",
    "studies": "cinematic retro clock ticking",
    "show": "projector screen lens flare",
    "lock": "cyber padlock key close up",
    "screen": "code matrix lines green",
    "brain": "neon brain holographic rotation",
    "deep": "galaxy deep space cosmic nebulas",
    "friction": "running shoes asphalt fast pace",
    "immediately": "lightning storm striking clouds",
    "automate": "industrial robotic arms assembly",
    "morning": "morning sun rays through foggy forest",
    "performers": "elite executive walking slow motion",
    "waste": "hourglass sand spilling macro",
    "scrolling": "smart phone screen scrolling glow close up",
    "money": "luxury gold bars vault safe",
    "cash": "counting dollar bills hands slow motion",
    "secrets": "mysterious figure shadow smoke",
    "truth": "hundred percent 100 badge neon",
    "mistake": "crumpled paper trash basket",
    "destroying": "fire flames burning close up"
}

def expand_keyword_to_concept(word):
    word_clean = str(word).lower().strip()
    return CONCEPT_EXPANSIONS.get(word_clean, f"aesthetic {word_clean}")

# --- KEYWORD EXTRACTOR FOR AUTOMATED B-ROLL SEARCH ---
def extract_best_keywords(text, num_words=6):
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at', 'with', 'by', 'to', 'for', 'and', 'but', 
        'or', 'if', 'then', 'else', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 
        'my', 'your', 'his', 'her', 'its', 'our', 'their', 'how', 'why', 'what', 'who', 'whom', 'here', 'there', 
        'about', 'stop', 'doing', 'right', 'now', 'your', 'mine', 'all', 'any', 'get', 'gets', 'got'
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    
    result = []
    seen = set()
    for w in filtered:
        if w not in seen:
            seen.add(w)
            result.append(w)
            if len(result) >= num_words:
                break
    return result if result else ["abstract"]

# --- PEXELS DYNAMIC VIDEO DOWNLOADER (UPGRADED WITH RANDOM PICKER & UNIQUE ID CACHING) ---
def download_pexels_b_roll(query, api_key):
    clean_query = str(query).replace(" ", "+")
    
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={clean_query}&per_page=15&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            data = r.json()
            videos = data.get("videos", [])
            if videos:
                selected_v = random.choice(videos[:min(len(videos), 6)])
                video_id = selected_v.get("id")
                
                local_path = os.path.join(B_ROLL_DIR, f"{clean_query.lower()}_{video_id}_916.mp4")
                if os.path.exists(local_path):
                    return local_path
                    
                video_files = selected_v.get("video_files", [])
                target_link = None
                
                for vf in video_files:
                    if vf.get("file_type") == "video/mp4":
                        w = vf.get("width") or 0
                        h = vf.get("height") or 0
                        if w < h:
                            target_link = vf.get("link")
                            break
                            
                if not target_link and video_files:
                    target_link = video_files[0].get("link")
                    
                if target_link:
                    video_res = requests.get(target_link, timeout=40)
                    if video_res.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(video_res.content)
                        return local_path
    except Exception as e:
        print(f"Pexels search failed for '{query}': {e}")
    return None

# --- PEXELS AUTOMATED BACKUP KEYWORD DOWNLOADER (PREVENTS BLANK BACKGROUNDS) ---
def download_pexels_b_roll_with_fallback(query, api_key):
    # Proactively expand our keyword into a cinematic visual search term!
    expanded_query = expand_keyword_to_concept(query)
    
    clip = download_pexels_b_roll(expanded_query, api_key)
    if clip and os.path.exists(clip):
        return clip
        
    backups = ["moody dark", "urban night", "focused student", "ticking clock", "rain window", "cyberpunk city", "financial trade"]
    backup_query = random.choice(backups)
    print(f"Pexels primary expanded '{expanded_query}' returned no results. Auto-downloading backup: '{backup_query}'")
    return download_pexels_b_roll(backup_query, api_key)

# --- CINEMATIC ANIMATED PRESET GENERATOR WITH PARTICLES & VIGNETTE ---
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
        
        grid_color = (255, 255, 255, 10)
        for gx in range(1, 6):
            draw.line([(gx * 120, 0), (gx * 120, height)], fill=grid_color, width=1)
        for gy in range(1, 10):
            draw.line([(0, gy * 128), (width, gy * 128)], fill=grid_color, width=1)
            
        for p in particles:
            x = int(p['x_pct'] * width)
            y = int(((p['y_start_pct'] - p['speed'] * t) % 1.0) * height)
            rad = p['size']
            draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(orb_color[0], orb_color[1], orb_color[2], p['opacity']))
            if rad > 3:
                draw.ellipse([x - rad - 2, y - rad - 2, x + rad + 2, y + rad + 2], fill=(orb_color[0], orb_color[1], orb_color[2], int(p['opacity'] * 0.4)))
        
        cx1 = 360 + int(140 * np.sin(t * 1.1))
        cy1 = 550 + int(90 * np.cos(t * 0.8))
        rad1 = 180 + int(20 * np.sin(t * 2.0))
        draw.ellipse([cx1 - rad1, cy1 - rad1, cx1 + rad1, cy1 + rad1], fill=(orb_color[0], orb_color[1], orb_color[2], 55))
        
        cx2 = 360 + int(180 * np.cos(t * 0.9))
        cy2 = 800 + int(110 * np.sin(t * 0.6))
        rad2 = 210
        draw.ellipse([cx2 - rad2, cy2 - rad2, cx2 + rad2, cy2 + rad2], fill=(255, 255, 255, 20))

        for border in range(0, 160, 10):
            opacity = int(((border / 160) ** 2) * 150)
            draw.rectangle([border, border, width-border, height-border], outline=(0, 0, 0, opacity), width=10)

        draw.rectangle([18, 18, width-18, height-18], outline=(255, 255, 255, 35), width=2)
        
        return np.array(img)

    return VideoClip(make_frame, duration=duration)

# --- KEN BURNS SLIDESHOW GENERATOR WITH SMOOTH CONSTANT ZOOM ---
def make_ken_burns_clip(img_path, duration):
    base_img = Image.open(img_path).convert("RGB")
    bw, bh = base_img.size
    target_w, target_h = 720, 1280
    
    img_aspect = bw / bh
    target_aspect = target_w / target_h
    
    if img_aspect > target_aspect:
        crop_w = int(bh * target_aspect)
        left = (bw - crop_w) // 2
        base_img_cropped = base_img.crop((left, 0, left + crop_w, bh))
    else:
        crop_h = int(bw / target_aspect)
        top = (bh - crop_h) // 2
        base_img_cropped = base_img.crop((0, top, bw, top + crop_h))
        
    cw, ch = base_img_cropped.size

    def make_frame(t):
        scale = 1.0 + 0.15 * (t / duration)
        vw, vh = cw / scale, ch / scale
        left, top = (cw - vw) / 2, (ch - vh) / 2
        cropped = base_img_cropped.crop((left, top, left + vw, top + vh))
        return np.array(cropped.resize((target_w, target_h), Image.Resampling.LANCZOS))
        
    return VideoClip(make_frame, duration=duration)

# --- SPEECH CLEANER ---
def clean_script_for_speech(script_text):
    if not script_text: return ""
    lines = str(script_text).split('\n')
    cleaned = []
    for line in lines:
        l = line.strip()
        if not l or (l.startswith('[') and l.endswith(']')): continue
        if l.startswith(('-', '•')): l = l[1:].strip()
        l = l.replace('+', 'and').replace('👇', 'below').replace('🔥', 'fire').replace('📈', 'to grow').replace('🧠', 'psychology').replace('🎯', 'target')
        cleaned.append(l)
    return re.sub(r'\[.*?\]', '', " ".join(cleaned)).strip()

# --- NATIVE PYTHON TTS GENERATOR (100% ROBUST, NO PATH ISSUES, NO SUBPROCESS, THREAD-SAFE EVENT LOOP) ---
def generate_tts_audio(text, voice_name="en-US-ChristopherNeural", output_basename="voice"):
    audio_path = os.path.join(AUDIO_DIR, f"{output_basename}.mp3")
    srt_path = os.path.join(AUDIO_DIR, f"{output_basename}.srt")
    
    async def amain():
        communicate = edge_tts.Communicate(text, voice_name)
        submaker = edge_tts.SubMaker()
        with open(audio_path, "wb") as f_aud:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f_aud.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
                    
        with open(srt_path, "w", encoding="utf-8") as f_sub:
            f_sub.write(submaker.get_srt())
            
    try:
        run_async_in_thread(amain())
        return audio_path, srt_path
    except Exception as e:
        print(f"Native edge-tts failed: {e}. Falling back to gTTS.")
        from gtts import gTTS
        try:
            gTTS(text=text, lang='en').save(audio_path)
            return audio_path, None
        except Exception as ge:
            print(f"gTTS fallback failed: {ge}")
            return None, None

# --- WEB VTT / SRT PARSER (FULLY HYBRID) ---
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

# --- MATHEMATICALLY PERFECT VERTICAL SCALER & CROPPER (NO EMPTY BLACK SPACES, 100% ROBUST) ---
def make_vertical_clip(clip, target_w=720, target_h=1280):
    w, h = clip.size
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        new_w = int(h * target_aspect)
        left = (w - new_w) // 2
        cropped_clip = clip.cropped(x1=left, y1=0, width=new_w, height=h)
    else:
        new_h = int(w / target_aspect)
        top = (h - new_h) // 2
        cropped_clip = clip.cropped(x1=0, y1=top, width=w, height=new_h)
        
    return cropped_clip.resized(width=target_w, height=target_h)

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
                    'text': group_text.upper()
                })
            
            start_time = group_end
            i += words_per_clip
            
    return word_subs

# --- PROCEDURAL HIGH-QUALITY CLICK/POP SOUND GENERATOR ---
def generate_synthetic_pop_sound(duration=0.08, frequency=650):
    sfx_path = os.path.join(AUDIO_DIR, "pop_sfx.wav")
    if os.path.exists(sfx_path):
        return sfx_path
        
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    decay = np.exp(-32 * t)
    freq_sweep = frequency * np.exp(-12 * t)
    wave = np.sin(2 * np.pi * freq_sweep * t) * decay
    
    audio_data = (wave * 32767).astype(np.int16)
    
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
        
    return sfx_path

# --- PROCEDURAL CINEMATIC WHOOSH SOUND GENERATOR (TRANSITIONS) ---
def generate_synthetic_whoosh_sound(duration=0.45, start_freq=150, end_freq=1100):
    sfx_path = os.path.join(AUDIO_DIR, "whoosh_sfx.wav")
    if os.path.exists(sfx_path):
        return sfx_path
        
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    freq = start_freq + (end_freq - start_freq) * (t / duration) ** 1.5
    sine_wave = np.sin(2 * np.pi * freq * t)
    
    envelope = np.sin(np.pi * (t / duration)) ** 2
    np.random.seed(123)
    noise = np.random.uniform(-0.15, 0.15, len(t))
    
    wave = (sine_wave * 0.70 + noise * 0.30) * envelope
    audio_data = (wave * 32767).astype(np.int16)
    
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
        
    return sfx_path

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
                fill=(bar_color[0], bar_color[1], bar_color[2], 235)
            )
            if progress_w > 5:
                draw.rectangle(
                    [0, height - bar_height - 2, progress_w, height - bar_height], 
                    fill=(bar_color[0], bar_color[1], bar_color[2], 120)
                )
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

# --- UPGRADED CAPTIONS GENERATOR (WITH AD-HD POWER WORDS + SFX TRIGGERS + DYNAMIC PRESETS) ---
def build_subtitle_and_sfx_clips(subtitles, target_w=720, font_size=55, color='yellow', caption_style='standard'):
    display_subs = subtitles
    actual_font_size = font_size
    
    # Check if a custom style theme is selected under caption_style
    # Themes: Hormozi, Cyberpunk, Minimalist
    caption_theme = str(caption_style).lower()
    
    is_word_pop = "hormozi" in caption_theme or "cyberpunk" in caption_theme or "word_pop" in caption_theme
    
    if is_word_pop:
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=1)
        actual_font_size = int(font_size * 0.95)
        
    text_clips = []
    sfx_clips = []
    pop_sfx_path = generate_synthetic_pop_sound()
    
    POWER_WORDS = {
        "money": "💰", "cash": "💵", "wealth": "💸", "rich": "💰", "billionaire": "👑", "billionaires": "👑",
        "fail": "❌", "mistake": "❌", "mistakes": "❌", "wrong": "🚫", "destroy": "💥", "destroying": "💥",
        "secret": "🤫", "secrets": "🤫", "hidden": "🔍", "truth": "💯", "bizarre": "👽",
        "top": "🥇", "elite": "👑", "success": "📈", "grow": "📈", "growth": "📈",
        "brain": "🧠", "neuroscientist": "🔬", "psychology": "🧠", "mind": "🧠",
        "focus": "🎯", "goal": "🎯", "goals": "🎯",
        "shock": "😱", "shocked": "😱", "shocking": "😱",
        "stop": "🛑", "danger": "⚠️", "warn": "⚠️", "warning": "⚠️",
        "willpower": "💪", "discipline": "🛡️", "unstoppable": "⚡", "relentless": "⚡",
        "fire": "🔥", "hot": "🔥", "burn": "🔥"
    }
    
    tick_vol = float(db_settings.get_setting("tick_volume", 0.18))
    
    for s in display_subs:
        duration = s['end'] - s['start']
        if duration <= 0.05: continue
        
        txt = s['text']
        clean_w = re.sub(r'[^\w]', '', txt.lower())
        
        # Default Theme: Hormozi Gold style (Yellow / Green bold)
        word_color = "#FFD700" if color == "yellow" else color
        word_size = actual_font_size
        stroke_color = "black"
        stroke_width = 4
        is_power = False
        
        # Apply Preset Themes
        if "cyberpunk" in caption_theme:
            word_color = "#00FFFF" # Tense Cyan
            if clean_w in POWER_WORDS:
                txt = f"⚡ {txt}"
                word_color = "#FF00FF" # Neon Pink on power words!
                word_size = int(actual_font_size * 1.15)
                is_power = True
        elif "minimalist" in caption_theme:
            word_color = "#FFFFFF" # Clean Minimal White
            stroke_color = "black"
            stroke_width = 2
            if clean_w in POWER_WORDS:
                word_color = "#F5921D" # Soft Orange accent
                word_size = int(actual_font_size * 1.10)
                is_power = True
        else:
            # Hormozi style (Default)
            if clean_w in POWER_WORDS:
                txt = f"{POWER_WORDS[clean_w]} {txt}"
                word_color = "#39FF14" # Neon Green
                word_size = int(actual_font_size * 1.18)
                is_power = True
            
        txt_clip = TextClip(
            text=txt, 
            font="Arial", # Windows Standard Font, 100% clean and compact
            font_size=word_size, 
            color=word_color, 
            stroke_color=stroke_color, 
            stroke_width=stroke_width, 
            method='caption', 
            size=(target_w - 120, None), 
            text_align='center'
        )
        
        # --- PREMIUM DYNAMIC WORD BOUNCE ZOOM ANIMATION ---
        try:
            if "minimalist" not in caption_theme: # bounce only for active styles!
                bouncy_txt_clip = txt_clip.resized(lambda t: min(1.0, 0.85 + (0.15 / 0.07) * t) if t < 0.07 else 1.0)
            else:
                bouncy_txt_clip = txt_clip
        except:
            bouncy_txt_clip = txt_clip
            
        text_clips.append(
            bouncy_txt_clip.with_duration(duration)
                           .with_start(s['start'])
                           .with_position(('center', 0.55))
        )
        
        if is_power:
            try:
                sfx_audio = AudioFileClip(pop_sfx_path).with_start(s['start']).with_volume_scaled(tick_vol)
                sfx_clips.append(sfx_audio)
            except:
                pass
                
    return text_clips, sfx_clips

def build_subtitle_clips(subtitles, target_w=720, font_size=55, color='yellow'):
    tc, _ = build_subtitle_and_sfx_clips(subtitles, target_w, font_size, color, caption_style='standard')
    return tc

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


# ==============================================================================
# 🧬 THE MASTER HYBRID VIDEO GENERATION PIPELINE 🧬
# ==============================================================================
def create_hybrid_ai_video(short_id, script_text, uploaded_file_paths=None, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    # --- PROACTIVE WINDOWS FILE LOCK AVOIDANCE (WinError 32): USE TIMESTAMPED FILENAMES ---
    timestamp = int(time.time())
    output_video_path = os.path.join(VIDEO_DIR, f"short_{short_id}_{timestamp}.mp4")
    
    progress_cb = kwargs.get("progress_callback", None)
    
    if progress_cb: progress_cb(0.05, "Cleaning script...")
    spoken_text = clean_script_for_speech(script_text)
    
    if progress_cb: progress_cb(0.15, "Generating high-fidelity neural speech voiceover...")
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_hybrid")
    
    # Read custom layout/pacing parameters
    db_caption_style = db_settings.get_setting("caption_style", "word_pop")
    db_music_volume = float(db_settings.get_setting("bg_music_volume", 0.12))
    db_font_size = int(db_settings.get_setting("font_size", 55))
    db_whoosh_volume = float(db_settings.get_setting("whoosh_volume", 0.12))
    
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", db_music_volume)
    
    if progress_cb: progress_cb(0.30, "Combining vocal tracks, ducking volume, and mixing soundtracks...")
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume)
    duration = voice_audio.duration
    
    # --- PROACTIVE UPGRADE: FLEXIBLE CUT PACING (ADHD vs Standard vs Mindful) ---
    cut_duration = float(kwargs.get("cut_duration", 2.0))
    num_cuts = int(np.ceil(duration / cut_duration))
    
    progress_cb_step_weight = 0.40 / num_cuts
    visual_clips = []
    transition_audio_clips = []
    whoosh_path = generate_synthetic_whoosh_sound()
    
    # Check both parameters and the local pexels_key.txt file to be 100% robust
    pexels_key = kwargs.get("pexels_api_key", None)
    if not pexels_key or not pexels_key.strip():
        if os.path.exists("pexels_key.txt"):
            try:
                with open("pexels_key.txt", "r", encoding="utf-8") as f:
                    pexels_key = f.read().strip()
            except:
                pass
                
    custom_files = uploaded_file_paths if uploaded_file_paths else []
    
    for idx in range(num_cuts):
        start_t = idx * cut_duration
        end_t = min(start_t + cut_duration, duration)
        clip_dur = end_t - start_t
        if clip_dur <= 0.05:
            continue
            
        clip_added = False
        
        # Scenario A: Use uploaded file first!
        if idx < len(custom_files):
            file_path = custom_files[idx]
            if os.path.exists(file_path):
                if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Slicing and zoom-formatting your uploaded asset {idx+1}...")
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    v_clip = make_ken_burns_clip(file_path, clip_dur).with_start(start_t)
                    visual_clips.append(v_clip)
                    clip_added = True
                elif file_path.lower().endswith(('.mp4', '.mov')):
                    try:
                        raw_v = VideoFileClip(file_path)
                        sub_start = 0.0
                        if raw_v.duration > clip_dur + 1.0:
                            np.random.seed(idx)
                            sub_start = np.random.uniform(0.0, raw_v.duration - clip_dur)
                        sub_v = raw_v.subclipped(sub_start, sub_start + clip_dur).with_start(start_t)
                        scaled_sub = make_vertical_clip(sub_v)
                        visual_clips.append(scaled_sub)
                        clip_added = True
                    except Exception as e:
                        print(f"Failed loading uploaded clip: {e}")
                        
        # Scenario B: Fetch stock video from Pexels!
        if not clip_added and pexels_key and pexels_key.strip():
            sentence_words = extract_best_keywords(spoken_text, num_words=1)
            search_word = "abstract"
            if len(sentence_words) > 0:
                search_word = sentence_words[idx % len(sentence_words)]
                
            if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"AI Downloading vertical HD stock clip from Pexels for '{search_word.upper()}'...")
            downloaded_file = download_pexels_b_roll_with_fallback(search_word, pexels_key)
            if downloaded_file and os.path.exists(downloaded_file):
                try:
                    raw_v = VideoFileClip(downloaded_file)
                    sub_start = 0.0
                    if raw_v.duration > clip_dur + 1.0:
                        np.random.seed(idx)
                        sub_start = np.random.uniform(0.0, raw_v.duration - clip_dur)
                    sub_v = raw_v.subclipped(sub_start, sub_start + clip_dur).with_start(start_t)
                    scaled_sub = make_vertical_clip(sub_v)
                    visual_clips.append(scaled_sub)
                    clip_added = True
                except Exception as e:
                    print(f"Failed loading downloaded stock: {e}")
                    
        # Scenario C: Fallback to animated particles!
        if not clip_added:
            if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, "Generating procedural 24fps glowing background loop...")
            theme_choice = "Curiosity"
            if "success" in spoken_text.lower(): theme_choice = "Success"
            elif "warning" in spoken_text.lower() or "mistake" in spoken_text.lower(): theme_choice = "Urgency"
            
            p_clip = make_animated_background_clip(clip_dur, theme=theme_choice).with_start(start_t)
            p_clip = make_vertical_clip(p_clip)
            visual_clips.append(p_clip)
            
        if idx > 0:
            try:
                whoosh_clip = AudioFileClip(whoosh_path).with_start(start_t).with_volume_scaled(db_whoosh_volume)
                transition_audio_clips.append(whoosh_clip)
            except:
                pass
                
    bg_clip = CompositeVideoClip(visual_clips, size=(720, 1280)).with_duration(duration)
    
    if progress_cb: progress_cb(0.80, "Slicing subtitle timings, emojifying captions, and mapping Neon highlights...")
    caption_style = kwargs.get("caption_style", db_caption_style)
    text_clips, sfx_clips = build_subtitle_and_sfx_clips(parse_vtt(vtt_path), color=font_color, caption_style=caption_style, font_size=db_font_size)
    
    if sfx_clips:
        mixed_audio = CompositeAudioClip([mixed_audio] + sfx_clips)
        
    bg_clip = bg_clip.with_audio(mixed_audio)
    
    extra_clips = []
    if kwargs.get("show_progress_bar", True):
        prog_clip = make_progress_bar_clip(duration)
        extra_clips.append(prog_clip)
        
    if progress_cb: progress_cb(0.88, "Compiling multi-track layers & starting FFmpeg rendering encoder...")
    # --- COMBINED ROBUST WINDOWS COLORSPACE & CODEC FIXED FORMAT ---
    CompositeVideoClip([bg_clip] + text_clips + extra_clips).write_videofile(
        output_video_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac", 
        preset="fast", 
        logger=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"] # Bypasses signature errors, works universally!
    )
    
    if progress_cb: progress_cb(0.98, "Releasing local system file locks and saving database state...")
    try: 
        mixed_audio.close()
        voice_audio.close() 
        bg_clip.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
        for sc in sfx_clips: sc.close()
        for wc in transition_audio_clips: wc.close()
    except: 
        pass
        
    if progress_cb: progress_cb(1.00, "Render complete!")
    return output_video_path, audio_path, vtt_path
