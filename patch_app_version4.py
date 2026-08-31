import sys

with open('/home/user/faceless-short-studio/app.py', 'r') as f:
    content = f.read()

content = content.replace(
    '<span style="font-size: 0.4em; color: #888;">v1.1.3</span>',
    '<span style="font-size: 0.4em; color: #888;">v1.1.4</span>'
)

with open('/home/user/faceless-short-studio/app.py', 'w') as f:
    f.write(content)
