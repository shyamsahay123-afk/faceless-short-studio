import re

def parse_vtt(vtt_path):
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match blocks like:
    # 1
    # 00:00:00,100 --> 00:00:03,712
    # This is a psychology test for YouTube shorts.
    
    # In VTT, timestamps are usually 00:00:00.100 or 00:00:00,100
    pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*\n((?:(?!\n\n).)*)',
        re.DOTALL
    )
    
    matches = pattern.findall(content)
    
    def time_to_sec(t_str):
        t_str = t_str.replace(',', '.')
        parts = t_str.split(':')
        h = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s

    subtitles = []
    for start_str, end_str, text in matches:
        start = time_to_sec(start_str)
        end = time_to_sec(end_str)
        cleaned_text = text.strip().replace('\n', ' ')
        if cleaned_text:
            subtitles.append({
                'start': start,
                'end': end,
                'text': cleaned_text
            })
    return subtitles

print(parse_vtt('test.vtt'))
