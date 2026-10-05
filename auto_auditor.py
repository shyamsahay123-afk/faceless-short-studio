import os
import re
import subprocess
import imageio_ffmpeg
import numpy as np
from PIL import Image
from moviepy import VideoFileClip

def audit_video(mp4_path):
    if not os.path.exists(mp4_path):
        return False, "[Audit] FAIL: File does not exist.", None
        
    print(f"🔍 [QC Auditor] Inspecting {os.path.basename(mp4_path)}...")
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # 1. AUDIO CHECK (Mathematical dB Analysis)
    cmd = [ffmpeg_exe, "-y", "-i", mp4_path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    passed_audio = True
    audio_log = "Audio: PASS"
    
    max_vol_match = re.search(r'max_volume:\s*([-.\d]+)\s*dB', res.stderr)
    mean_vol_match = re.search(r'mean_volume:\s*([-.\d]+)\s*dB', res.stderr)
    
    if not max_vol_match or not mean_vol_match:
        passed_audio = False
        audio_log = "Audio: FAIL (No audio track detected in MP4)"
    else:
        max_vol = float(max_vol_match.group(1))
        if max_vol < -35.0:
            passed_audio = False
            audio_log = f"Audio: FAIL (Muted or Too quiet. Max Vol: {max_vol}dB)"
        else:
            audio_log = f"Audio: PASS (Max Vol: {max_vol}dB)"
            
    # 2. VISUAL CHECK & STORYBOARD
    passed_visual = True
    visual_log = "Visual: PASS"
    storyboard_path = mp4_path.replace(".mp4", "_storyboard.jpg")
    
    try:
        clip = VideoFileClip(mp4_path)
        duration = clip.duration
        if duration < 3.0:
            passed_visual = False
            visual_log = f"Visual: FAIL (Video extremely short: {duration}s)"
        else:
            # Extract 6 frames evenly spaced
            times = np.linspace(0.5, duration - 0.5, 6)
            frames = [clip.get_frame(t) for t in times]
            clip.close()
            
            # Stitch into 2x3 grid
            h, w, _ = frames[0].shape
            grid_w = w * 3
            grid_h = h * 2
            grid_img = Image.new('RGB', (grid_w, grid_h))
            
            for i, frame in enumerate(frames):
                img = Image.fromarray(frame)
                row = i // 3
                col = i % 3
                grid_img.paste(img, (col * w, row * h))
                
            # Resize to manageable size (1080 width)
            scale = 1080 / grid_w
            grid_img = grid_img.resize((1080, int(grid_h * scale)), Image.LANCZOS)
            grid_img.save(storyboard_path, quality=80)
            visual_log = f"Visual: PASS (Duration: {duration:.1f}s, Res: {w}x{h})"
            
    except Exception as e:
        passed_visual = False
        visual_log = f"Visual: FAIL (Render Error: {e})"
        
    final_pass = passed_audio and passed_visual
    report = f"{audio_log} | {visual_log}"
    
    return final_pass, report, storyboard_path
