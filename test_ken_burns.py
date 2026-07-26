import numpy as np
from PIL import Image, ImageDraw
from moviepy import VideoClip

def test_kb():
    # 1. Create a dummy test image with patterns
    base_img = Image.new("RGB", (1080, 1920), color=(10, 50, 100))
    draw = ImageDraw.Draw(base_img)
    draw.rectangle([200, 400, 880, 1520], fill=(200, 100, 50), outline="white", width=10)
    draw.ellipse([400, 800, 680, 1080], fill="yellow")
    base_img.save("dummy_test.jpg")
    
    # 2. Ken Burns animation
    bw, bh = base_img.size
    target_w, target_h = 720, 1280
    duration = 3.0
    
    def make_frame(t):
        # Zoom from 1.0 to 1.2 over duration
        scale = 1.0 + 0.2 * (t / duration)
        vw = bw / scale
        vh = bh / scale
        
        left = (bw - vw) / 2
        top = (bh - vh) / 2
        right = left + vw
        bottom = top + vh
        
        cropped = base_img.crop((left, top, right, bottom))
        resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        return np.array(resized)
        
    vc = VideoClip(make_frame, duration=duration)
    vc.write_videofile("test_kb.mp4", fps=24, codec="libx264")

if __name__ == "__main__":
    test_kb()
    print("Ken burns compiled successfully!")
