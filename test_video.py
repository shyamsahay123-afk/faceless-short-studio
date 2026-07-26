from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, TextClip
from test_vtt import parse_vtt

def build_test_video():
    # 1. Background
    bg = ImageClip("default_assets/bg_curiosity.jpg")
    
    # 2. Audio
    audio = AudioFileClip("test.mp3")
    bg = bg.with_duration(audio.duration)
    bg = bg.with_audio(audio)
    
    # 3. Subtitles
    subs = parse_vtt("test.vtt")
    
    # Fix overlaps
    for i in range(len(subs) - 1):
        if subs[i]['end'] > subs[i+1]['start']:
            subs[i]['end'] = subs[i+1]['start']
            
    text_clips = []
    for s in subs:
        t_start = s['start']
        t_end = s['end']
        text = s['text']
        duration = t_end - t_start
        
        if duration <= 0.01:
            continue
            
        txt_clip = TextClip(
            text=text,
            font_size=55,
            color='yellow',
            stroke_color='black',
            stroke_width=2,
            method='caption',
            size=(640, None),
            text_align='center'
        )
        # Position centered or slightly lower
        txt_clip = (txt_clip
                    .with_duration(duration)
                    .with_start(t_start)
                    .with_position('center'))
        text_clips.append(txt_clip)
        
    final_video = CompositeVideoClip([bg] + text_clips)
    final_video.write_videofile("test_output.mp4", fps=24, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    build_test_video()
