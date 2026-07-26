from PIL import Image, ImageDraw, ImageFont
import math

def create_gradient_bg(filename, color1, color2, text_overlay=""):
    width = 720
    height = 1280
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        # Linear gradient
        r = int(color1[0] + (color2[0] - color1[0]) * y / height)
        g = int(color1[1] + (color2[1] - color1[1]) * y / height)
        b = int(color1[2] + (color2[2] - color1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    if text_overlay:
        # Draw some cool subtle background visual or watermark
        try:
            # Try to load a generic font or default
            font = ImageFont.load_default()
        except:
            font = None
        # Draw abstract circles
        draw.ellipse([100, 200, 600, 700], outline=(255, 255, 255, 40), width=5)
        draw.ellipse([160, 260, 540, 640], outline=(255, 255, 255, 30), width=3)
    
    img.save(filename)

if __name__ == "__main__":
    create_gradient_bg("default_assets/bg_curiosity.jpg", (15, 23, 42), (88, 28, 135), "Curiosity")
    create_gradient_bg("default_assets/bg_success.jpg", (6, 78, 59), (15, 23, 42), "Success")
    create_gradient_bg("default_assets/bg_urgency.jpg", (127, 29, 29), (15, 23, 42), "Urgency")
    create_gradient_bg("default_assets/bg_story.jpg", (30, 58, 138), (15, 23, 42), "Story")
    print("Default assets created successfully!")
