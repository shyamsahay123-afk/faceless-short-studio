import os
import re
import subprocess
import numpy as np
from moviepy import (
    VideoClip, ImageClip, VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips
)
from PIL import Image, ImageDraw

AUDIO_DIR = "audio_clips"
VIDEO_DIR = "video_output"
DEFAULT_DIR = "default_assets"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(DEFAULT_DIR, exist_ok=True)

# --- CINEMATIC ANIMATED PRESET GENERATOR ---
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
        
        cx1 = 360 + int(180 * np.sin(t * 1.3))
        cy1 = 550 + int(120 * np.cos(t * 0.9))
        rad1 = 180 + int(30 * np.sin(t * 2.5))
        draw.ellipse([cx1 - rad1, cy1 - rad1, cx1 + rad1, cy1 + rad1], fill=(orb_color[0], orb_color[1], orb_color[2], 70))
        
        cx2 = 360 + int(220 * np.cos(t * 1.1))
        cy2 = 850 + int(160 * np.sin(t * 0.7))
        rad2 = 200
        draw.ellipse([cx2 - rad2, cy2 - rad2, cx2 + rad2, cy2 + rad2], fill=(255, 255, 255, 25))

        draw.rectangle([18, 18, width-18, height-18], outline=(255, 255, 255, 50), width=2)
        return np.array(img)

    return VideoClip(make_frame, duration=duration)

# --- KEN BURNS SLIDESHOW GENERATOR ---
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

# --- TTS GENERATOR ---
def generate_tts_audio(text, voice_name="en-US-ChristopherNeural", output_basename="voice"):
    audio_path = os.path.join(AUDIO_DIR, f"{output_basename}.mp3")
    vtt_path = os.path.join(AUDIO_DIR, f"{output_basename}.vtt")
    cmd = ["edge-tts", "--voice", voice_name, "--text", text, "--write-media", audio_path, "--write-subtitles", vtt_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return audio_path, vtt_path
    except Exception as e:
        print(f"edge-tts failed: {e}. Falling back to gTTS.")
        from gtts import gTTS
        gTTS(text=text, lang='en').save(audio_path)
        return audio_path, None

# --- WEB VTT PARSER ---
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

def build_subtitle_clips(subtitles, target_w=720, font_size=55, color='yellow'):
    text_clips = []
    for s in subtitles:
        duration = s['end'] - s['start']
        if duration <= 0.05: continue
        txt_clip = TextClip(text=s['text'], font_size=font_size, color=color, stroke_color='black', stroke_width=3, method='caption', size=(target_w - 60, None), text_align='center')
        text_clips.append(txt_clip.with_duration(duration).with_start(s['start']).with_position(('center', 'center')))
    return text_clips

# --- PIPELINE 1: INSTANT AI PRESET (ANIMATED) WITH KWARGS ---
def create_video_from_script(short_id, script_text, bg_asset_or_theme, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join(VIDEO_DIR, f"short_{short_id}.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}")
    audio = AudioFileClip(audio_path)
    
    # Determine if it's a theme name or video/image path
    theme_keywords = ['curiosity', 'success', 'urgency', 'story', 'theme', 'profile']
    is_theme = isinstance(bg_asset_or_theme, str) and (any(k in bg_asset_or_theme.lower() for k in theme_keywords) or not os.path.exists(bg_asset_or_theme))

    if is_theme:
        bg_clip = make_animated_background_clip(audio.duration, theme=str(bg_asset_or_theme)).with_audio(audio)
    elif isinstance(bg_asset_or_theme, str) and bg_asset_or_theme.lower().endswith(('.mp4', '.mov')):
        bg_clip = VideoFileClip(bg_asset_or_theme)
        if bg_clip.duration < audio.duration:
            bg_clip = concatenate_videoclips([bg_clip] * (int(audio.duration // bg_clip.duration) + 1))
        bg_clip = bg_clip.with_duration(audio.duration).with_audio(audio)
    elif isinstance(bg_asset_or_theme, str):
        bg_clip = ImageClip(bg_asset_or_theme).with_duration(audio.duration).with_audio(audio)
    else:
        bg_clip = ImageClip(np.array(bg_asset_or_theme)).with_duration(audio.duration).with_audio(audio)
        
    bg_clip = make_vertical_clip(bg_clip)
    text_clips = build_subtitle_clips(parse_vtt(vtt_path), color=font_color)
    
    CompositeVideoClip([bg_clip] + text_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    try: audio.close(); bg_clip.close()
    except: pass
    return output_video_path, audio_path, vtt_path

# --- PIPELINE 2: CUSTOM PHOTOS (KEN BURNS ANIMATED) ---
def create_video_from_photos(short_id, photo_paths, script_text, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join(VIDEO_DIR, f"short_{short_id}_photos.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_photos")
    audio = AudioFileClip(audio_path)
    
    photo_duration = audio.duration / len(photo_paths)
    photo_clips = [make_ken_burns_clip(p, photo_duration) for p in photo_paths]
        
    bg_clip = concatenate_videoclips(photo_clips).with_audio(audio).with_duration(audio.duration)
    text_clips = build_subtitle_clips(parse_vtt(vtt_path), color=font_color)
    
    CompositeVideoClip([bg_clip] + text_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    return output_video_path, audio_path, vtt_path

# --- PIPELINE 3: USER VIDEO CLIPS ---
def create_video_from_clips(short_id, clip_paths, script_text, voice_name="en-US-ChristopherNeural", font_color='yellow', **kwargs):
    output_video_path = os.path.join(VIDEO_DIR, f"short_{short_id}_clips.mp4")
    spoken_text = clean_script_for_speech(script_text)
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_clips")
    audio = AudioFileClip(audio_path)
    
    raw_clips = [make_vertical_clip(VideoFileClip(cp)) for cp in clip_paths]
    combined_bg = concatenate_videoclips(raw_clips)
    
    if combined_bg.duration < audio.duration:
        combined_bg = concatenate_videoclips([combined_bg] * (int(audio.duration // combined_bg.duration) + 1))
    
    combined_bg = combined_bg.with_duration(audio.duration).with_audio(audio)
    text_clips = build_subtitle_clips(parse_vtt(vtt_path), color=font_color)
    
    CompositeVideoClip([combined_bg] + text_clips).write_videofile(output_video_path, fps=24, codec="libx264", audio_codec="aac", preset="fast")
    return output_video_path, audio_path, vtt_path
