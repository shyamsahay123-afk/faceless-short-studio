import re

def clean_script_for_speech(script_text):
    # Remove any block enclosed in [...]
    # We can remove lines that start with [ and end with ]
    lines = script_text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith('[') and line_s.endswith(']'):
            continue
        # Remove bullet points
        if line_s.startswith('-') or line_s.startswith('•'):
            line_s = line_s[1:].strip()
        # Replace certain symbols for smoother reading
        line_s = line_s.replace('+', 'and')
        line_s = line_s.replace('👇', 'below')
        line_s = line_s.replace('🔥', 'fire')
        line_s = line_s.replace('📈', 'to grow')
        line_s = line_s.replace('🧠', 'psychology')
        line_s = line_s.replace('🎯', 'target')
        cleaned_lines.append(line_s)
        
    final_text = " ".join(cleaned_lines)
    # Remove any remaining brackets just in case
    final_text = re.sub(r'\[.*?\]', '', final_text)
    return final_text.strip()

test_script = """[0-3 sec HOOK]  
What happens when you combine psychology with shorts?  
  
[PSYCHOLOGY TRIGGER: Curiosity Gap]  
Create an open loop in the first 2 seconds that makes the brain demand closure.  
  
[VALUE DELIVERY - 3 to 45 sec]  
- Deliver one powerful point  
- Use one strong example or number  
- Keep it fast and visual  
  
[ENGAGEMENT CTA]  
Like if this hit hard + Comment your thoughts 👇"""

print(clean_script_for_speech(test_script))
