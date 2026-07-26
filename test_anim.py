import numpy as np
from PIL import Image, ImageDraw
from moviepy import VideoClip

def test_anim():
    width, height = 720, 1280
    def make_frame(t):
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        # draw a moving circle
        cx = 360 + int(100 * np.sin(t))
        cy = 640 + int(100 * np.cos(t))
        draw.ellipse([cx-50, cy-50, cx+50, cy+50], fill=(255, 0, 0))
        return np.array(img)
        
    vc = VideoClip(make_frame, duration=2)
    vc.write_videofile("test_anim.mp4", fps=24, codec="libx264")

if __name__ == "__main__":
    test_anim()
    print("Animation test success!")
