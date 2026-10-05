import sys

with open('/home/user/faceless-short-studio/app.py', 'r') as f:
    content = f.read()

content = content.replace(
    '<span style="font-size: 0.4em; color: #888;">v1.2.1</span>',
    '<span style="font-size: 0.4em; color: #888;">v1.2.2</span>'
)

with open('/home/user/faceless-short-studio/app.py', 'w') as f:
    f.write(content)
