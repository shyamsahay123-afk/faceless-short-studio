with open('style_engine.py', 'r') as f:
    content = f.read()
content = content.replace(
    'handle_txt = str(handle or "").strip() or "@yourchannel"',
    'handle_txt = str(handle or "").strip()'
)
with open('style_engine.py', 'w') as f:
    f.write(content)

with open('video_engine.py', 'r') as f:
    content = f.read()

content = content.replace(
    'if watermark and str(watermark).strip() not in ("", "@yourchannel"):',
    'if watermark and str(watermark).strip() != "":'
)
content = content.replace(
    'if not _wm_g or _wm_g == "@yourchannel":',
    'if False: # Removed watermark warning'
)
content = content.replace(
    'print("[GATE] ⚠ no watermark handle set — the outro will show \'@yourchannel\' and NO frame watermark. Set it in the Character Bible (or daily_settings.json).")',
    'pass'
)
with open('video_engine.py', 'w') as f:
    f.write(content)

print("Watermark patched")
