import sys

with open('/home/user/faceless-short-studio/app.py', 'r') as f:
    content = f.read()

content = content.replace(
    '<div class="main-header">🎬 Faceless AI Short Studio <span style="font-size: 0.4em; color: #888;">v1.1.0</span></div>',
    '<div class="main-header">🎬 Faceless AI Short Studio <span style="font-size: 0.4em; color: #888;">v1.1.1</span></div>'
)

with open('/home/user/faceless-short-studio/app.py', 'w') as f:
    f.write(content)
