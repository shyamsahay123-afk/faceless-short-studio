import sys

with open('/home/user/faceless-short-studio/app.py', 'r') as f:
    content = f.read()

# Update title with version
content = content.replace(
    '<div class="main-header">🎬 Faceless AI Short Studio</div>',
    '<div class="main-header">🎬 Faceless AI Short Studio <span style="font-size: 0.4em; color: #888;">v1.1.0</span></div>'
)

# Remove watermark handle input
old_watermark = """# Watermark lock (GOONINGGNG runs its IG handle on every frame) — used by the
# Void Black mode's outro card + top-right watermark
bib_handle = st.text_input("Watermark handle (top-right, every frame — e.g. @yourchannel)", value=bible.get("watermark", ""))"""

new_watermark = """# Watermark lock removed as requested
bib_handle = "" """

content = content.replace(old_watermark, new_watermark)

with open('/home/user/faceless-short-studio/app.py', 'w') as f:
    f.write(content)

print("App UI Patched")
