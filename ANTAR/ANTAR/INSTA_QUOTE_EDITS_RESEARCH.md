# INSTA QUOTE EDITS RESEARCH - Pro Human Edits

## Your exact words analyzed:
- "look like pro human edits" = not AI-looking, clean, precise timing, intentional
- "rectangular shaped and placed video in middle we can use it same but now with clean edges" = 1080x1920 canvas, inner video 900x1350 centered, rounded corners 24-32px, stroke + shadow, not jagged
- "same premium clips" = keep vault, no low-quality Pexels random
- "texts when we have to share things or talking to viewers" = 2 text modes: talking captions vs quote cards
- "if we just add related quotes with clips then we use different fonts" = quote mode = different font family

## Search Results - Quote Edits Used in 2024-2025:

### 1. Luxury Quote (Most Viral for Hindi/English)
- **Canvas:** 1080x1920, pure black #000000 or #0B0B0F
- **Font:** Didot, Playfair Display, Cormorant Garamond, Abril Fatface (serif, high contrast)
- **Layout:** Centered, 60% width, white text #FFFFFF with thin tracking
- **Animation:** Slow fade in 0.3s, hold 2s, fade out 0.3s. No bounce.
- **Example:** White Modern Motivational Quote Reel - Canva template
- **Why works:** Feels premium, like magazine

### 2. Rectangular Middle Video (Your Previous Style - Upgraded)
- **Canvas:** 1080x1920
- **Inner Video:** 1000x1400 centered (leaves 40px side padding, 260px top/bottom for UI safe)
- **Clean Edges:** 
  - Rounded corners 28px radius
  - 2px white stroke at 20% opacity
  - Drop shadow: offset 0,8 blur 24 black 40%
  - Anti-aliased (Pillow LANCZOS)
- **Background:** Blurred version of same clip + dark overlay 60%, or house colour #0B0B0F
- **Why works:** Pro human editors do this in CapCut/Alight Motion - video not full bleed, looks like intentional framing

### 3. Quote + Clip Combo (Related Quotes with Clips)
- **Style:** Clip plays full or rectangular, quote text overlays in middle
- **Fonts by Mood:**
  - Luxury/Sad: Didot / Abril Fatface (serif)
  - Bold Motivation: Bebas Neue, Oswald, Montserrat Bold (sans bold)
  - Soft/Emotional: Playlist Script, Allura (handwritten)
  - Hindi: Khand Bold (your locked) + Noto Devanagari fallback
- **Text Animation:**
  - Typewriter: character by character
  - Word pop: 1-2 words at a time (your current but needs pill + stroke)
  - Fly in from bottom with easeOutCubic
- **Background for text:** Dark pill 60% black rounded 24px behind text for contrast (like MrBeast captions)

### 4. Text-Only Viral (CapCut Template)
- **No footage:** Just animated text on gradient/black
- **Effects:** Stylish text effect templates - sleek animations
- **Fonts:** Bebas Neue, Squada One, League Spartan
- **Use case:** When you have no premium clip that matches quote

### 5. Trending Instagram Edits 2025-2026 (From Search)
- **Safe Zone:** Keep text in middle 1080x1420 (center 80%) to avoid Like/Comment/Share UI
- **Every 3 seconds:** Change something - zoom, text, B-roll (attention rule)
- **Captions:** Large, easy to read, near eye level, max 2 lines
- **Export:** 1080x1920 H.264, 30fps, healthy bitrate (CRF 18) - holds quality after Instagram recompresses
- **Audio:** 85% watch without sound, so text must convey message alone

## Pro Human Edit Checklist (What Makes It Look Human Not AI):
1. Clean edges - no jagged crop, rounded + anti-aliased
2. Consistent pill background for captions (same radius, same opacity)
3. No pure white #FFFFFF on black at night - use #F5F5F0 or #E9E9EF
4. Shadow + stroke on text - black stroke 8px + blur shadow
5. Different fonts for different moods - not one font for everything
6. Micro zooms: 1.0 -> 1.05 over 3 sec (Ken Burns) - subtle, human
7. Safe zones respected: 220px top, 420px bottom
8. Background blur duplicate when using rectangular middle - not flat color

## Fonts We Have Now (Working):
- Khand-Bold.ttf (351K) - Hindi talking captions, your locked identity
- BebasNeue-Regular.ttf (60K) - Bold English quotes, luxury street
- Didot-Placeholder.ttf = Abril Fatface (66K) - Luxury serif, Didot alternative for quotes

Need to add: Montserrat, Playfair (failed download due to GitHub block - can add later via fonts.google.com manual upload)

## Implementation Plan for ANTAR INSTA Track:
- New module: antar/render/insta.py
- Function: render_rectangular_middle(clip_path, output_path, config) -> 1080x1920 canvas, inner video 1000x1400 rounded + shadow
- Function: render_quote_card(text, font_choice, output_path) -> different fonts by mood
- Config: config/insta.json with rect dimensions, radius, stroke, shadow
- Keep vault premium clips, no random Pexels
