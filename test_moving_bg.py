import numpy as np
from PIL import Image, ImageDraw
from moviepy import VideoClip

def create_moving_bg(duration=3, theme="curiosity", filename="test_out.mp4"):
    width, height = 720, 1280
    
    if "success" in theme.lower():
        c1, c2 = (6, 78, 59), (15, 23, 42)
        orb_color = (16, 185, 129)
    elif "urgency" in theme.lower():
        c1, c2 = (127, 29, 29), (15, 23, 42)
        orb_color = (239, 68, 68)
    elif "story" in theme.lower():
        c1, c2 = (30, 58, 138), (15, 23, 42)
        orb_color = (59, 130, 246)
    else:
        c1, c2 = (15, 23, 42), (88, 28, 135)
        orb_color = (168, 85, 247)

    # Pre-render a base background gradient image to make `make_frame` incredibly fast!
    base_img = Image.new("RGB", (width, height))
    base_draw = ImageDraw.Draw(base_img)
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * y / height)
        g = int(c1[1] + (c2[1] - c1[1]) * y / height)
        b = int(c1[2] + (c2[2] - c1[2]) * y / height)
        base_draw.line([(0, y), (width, y)], fill=(r, g, b))

    def make_frame(t):
        # Start with a fresh copy of the base gradient
        img = base_img.copy()
        draw = ImageDraw.Draw(img, "RGBA")
        
        # Draw moving glowing abstract orbs
        # Orb 1: sweeping horizontally & pulsing
        cx1 = 360 + int(200 * np.sin(t * 1.5))
        cy1 = 500 + int(100 * np.cos(t * 1.0))
        rad1 = 200 + int(40 * np.sin(t * 3))
        draw.ellipse(
            [cx1 - rad1, cy1 - rad1, cx1 + rad1, cy1 + rad1],
            fill=(orb_color[0], orb_color[1], orb_color[2], 80)
        )
        
        # Orb 2: sweeping opposite direction
        cx2 = 360 + int(250 * np.cos(t * 1.2))
        cy2 = 800 + int(150 * np.sin(t * 0.8))
        rad2 = 220
        draw.ellipse(
            [cx2 - rad2, cy2 - rad2, cx2 + rad2, cy2 + rad2],
            fill=(255, 255, 255, 30)
        )

        # Cinematic border
        draw.rectangle([20, 20, width-20, height-20], outline=(255, 255, 255, 60), width=3)
        return np.array(img)

    vc = VideoClip(make_frame, duration=duration)
    vc.write_videofile(filename, fps=24, codec="libx264")

if __name__ == "__main__":
    create_moving_bg()
    print("Moving bg compiled successfully!")
