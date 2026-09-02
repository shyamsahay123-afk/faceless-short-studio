import os
import sys
import json
import subprocess

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("Run: pip install youtube-transcript-api yt-dlp")
    sys.exit(1)

def extract_video_id(url):
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
    return url

def analyze(url):
    vid_id = extract_video_id(url)
    print(f"==================================================")
    print(f"📡 FACELESS STUDIO COMPETITOR ANALYZER")
    print(f"Targeting Video ID: {vid_id}")
    print(f"==================================================")
    
    # 1. Metadata via yt-dlp
    print("[1/2] Ripping YouTube Metadata (Views, Title, Tags)...")
    res = subprocess.run(["yt-dlp", "--dump-json", url], capture_output=True, text=True)
    if res.returncode == 0:
        meta = json.loads(res.stdout)
        title = meta.get("title", "Unknown")
        views = meta.get("view_count", 0)
        tags = meta.get("tags", [])
    else:
        title, views, tags = "Unknown", 0, []
        print("      ⚠️ Metadata rip failed. Is the video private?")
        
    # 2. Transcript
    print("[2/2] Extracting internal Transcript skeleton...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(vid_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])
    except Exception as e:
        transcript_text = f"[Transcript blocked or unavailable: {e}]"
        
    # 3. Report
    os.makedirs("competitor_research", exist_ok=True)
    out_path = f"competitor_research/{vid_id}_analysis.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# Competitor Breakdown: {title}\n")
        f.write(f"- Views: {views:,}\n")
        f.write(f"- Tags: {', '.join(tags)}\n\n")
        f.write(f"## Full Transcript Blueprint\n{transcript_text}\n")
        
    print(f"✅ Analysis Complete! Blueprint saved to: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python yt_analyzer.py <youtube_url>")
    else:
        analyze(sys.argv[1])
