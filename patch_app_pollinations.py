import sys

with open('/home/user/faceless-short-studio/app.py', 'r') as f:
    content = f.read()

# Remove the "watermarked" text from Pollinations description
content = content.replace(
    'st.text_input("Pollinations Key (optional — no watermark)", type="password", value=saved_poll)',
    'st.text_input("Pollinations Key", type="password", value=saved_poll)'
)

content = content.replace(
    'st.caption("⚪ Keyless works, but is rate-limited (~1 image/15s) and watermarked")',
    'st.caption("⚪ Optional: Add key to remove rate limits")'
)

# And remove the watermark comment
content = content.replace(
    '# Pollinations Key (B3 — OPTIONAL): sk_/pk_ key = no rate limit, no watermark',
    '# Pollinations Key (B3 — OPTIONAL): sk_/pk_ key = no rate limit'
)

with open('/home/user/faceless-short-studio/app.py', 'w') as f:
    f.write(content)

print("Pollinations UI text Patched")
