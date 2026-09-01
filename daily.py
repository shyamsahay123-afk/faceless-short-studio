import traceback
# ==============================================================================
# DAILY AUTOPILOT — the consistency machine. Your time is the scarce resource,
# so this exists to make videos WITHOUT you sitting at the PC.
#
#   py daily.py                     -> next topic from queue.txt, render, publish
#   py daily.py --count 5           -> 5 videos in one run (run it when the PC
#                                      is on + powered; walks the queue)
#   py daily.py --topic "my idea"   -> render THIS topic (queue untouched)
#   py daily.py --lang hi           -> Hindi voice variant (same visual identity)
#   py daily.py --no-publish        -> render only (no git push to the videos repo)
#
# Windows schedule — one evening command a week is enough; the PC just has to
# be ON + plugged in when it fires:
#   schtasks /create /sc weekly /d MON /st 21:00 /tn "ShortsBatch" /tr "py D:\2\myuse\daily.py --count 2"
#
# Flow: queue -> script composer (hook-score gated) -> render (locked style)
#       -> database -> QC self-audit -> publish to the GitHub videos repo
#       -> daily_log.txt
# ==============================================================================
import os
import sys
import json
import shutil
import argparse
import subprocess
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import db_manager as db
import video_engine as video
from script_engine import generate_script_with_score, best_hook_line


def read_key(name):
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        try:
            return open(p, "r", encoding="utf-8").read().strip()
        except Exception:
            return ""
    return ""


def load_settings():
    p = os.path.join(BASE, "daily_settings.json")
    defaults = {
        "topic_style": "Dramatic",          # script vibe
        "caption_style": "hormozi",         # gold word-pop captions
        "bg_style": "grid",
        "accent": "yellow",
        "clip_mode": "blend",
        "b_roll_source": "pexels",          # stock = fast + reliable on autopilot
        "voice_preset": "Deep Narrator Male",
        "music_volume": 0.09,
        "sfx_level": 0.7,
        "videos_repo": "shyamsahay123-afk/videos",
        "hook_min_score": 60,
    }
    if os.path.exists(p):
        try:
            defaults.update(json.load(open(p, "r", encoding="utf-8")))
        except Exception as e:
            print(f"[daily] settings file broken ({e}) — using defaults")
    return defaults


def pop_queue_topic():
    q = os.path.join(BASE, "queue.txt")
    if not os.path.exists(q):
        return None
    lines = [l.strip() for l in open(q, "r", encoding="utf-8").read().splitlines()]
    lines = [l for l in lines if l and not l.startswith("#")]
    if not lines:
        return None
    topic = lines[0]
    with open(q, "w", encoding="utf-8") as f:
        f.write("\n".join(lines[1:]) + "\n")
    with open(os.path.join(BASE, "done_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | {topic}\n")
    return topic


def publish_to_videos_repo(video_path, thumb_path, repo, token):
    """Push the rendered video + thumbnail to the private videos repo (git)."""
    work = os.path.join(BASE, "_videos_publish_tmp")
    url = f"https://{token}@github.com/{repo}.git"
    try:
        if not os.path.isdir(os.path.join(work, ".git")):
            if os.path.exists(work):
                shutil.rmtree(work, ignore_errors=True)
            print(f"[daily] cloning {repo} ...")
            subprocess.run(["git", "clone", "--depth", "1", url, work],
                           check=True, timeout=180, stdout=subprocess.DEVNULL)
        else:
            subprocess.run(["git", "-C", work, "fetch", "origin"], timeout=120,
                           stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", work, "reset", "--hard", "origin/HEAD"],
                           timeout=60, stdout=subprocess.DEVNULL)
        shutil.copy(video_path, os.path.join(work, os.path.basename(video_path)))
        if thumb_path and os.path.exists(thumb_path):
            shutil.copy(thumb_path, os.path.join(work, os.path.basename(thumb_path)))
        subprocess.run(["git", "-C", work, "add", "-A"], check=True, timeout=60)
        subprocess.run(["git", "-C", work, "commit",
                        "-m", f"add {os.path.basename(video_path)}",
                        "-c", "user.name=daily-bot", "-c", "user.email=daily@local"],
                       check=True, timeout=60, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", work, "push", "origin", "HEAD"],
                       check=True, timeout=180, stdout=subprocess.DEVNULL)
        print("[daily] published to videos repo ✓")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[daily] publish failed (exit {e.returncode}) — video is still local in video_output/")
        return False


VOICE_MAP = {
    "en": ("Deep Narrator Male", "en-GB-RyanNeural"),
    "hi": ("Deep Narrator Male", "hi-IN-MadhurNeural"),
}


def render_one(topic, st, args):
    """Render + QC + publish ONE video. Returns 0 on success, 1 on failure."""
    print("=" * 62)
    print(f"FACELESS AI SHORT STUDIO — AUTOPILOT: {topic[:50]}")
    print("=" * 62)

    print(f"[1/6] Topic: {topic}")

    # 2) SCRIPT (hook-score gated: regenerates weak hooks)
    t0 = time.time()
    title, script, tags, trigger, hook_score = generate_script_with_score(
        topic, st["topic_style"], min_score=int(st["hook_min_score"]), tries=6)
    if title == "Safety Warning":
        print("Blocked by safety filter — skipping this topic.")
        return 1
    print(f"[2/6] Script drafted (hook score {hook_score}/100) in {time.time()-t0:.0f}s")
    print(f"      Hook: {best_hook_line(script)[:90]}")

    # 3) DATABASE
    db.init_db()
    channels = db.get_all_channels()
    if not channels:
        db.add_channel("My Faceless Empire", "Self Improvement", "10k")
        channels = db.get_all_channels()
    short_id = db.add_short(channels[0][0], title, script, trigger,
                            f"{title}\n\nDaily autopilot generated.", tags)
    print(f"[3/6] Saved to database (id {short_id})")

    # 4) RENDER (locked channel identity)
    voice_preset, voice_code = VOICE_MAP[args.lang]
    _bible = video.load_character_bible()
    if st.get("watermark"):
        _bible["watermark"] = st["watermark"]
    pexels_key = read_key("pexels_key.txt")
    pixabay_key = read_key("pixabay_key.txt")
    eleven_key = read_key("elevenlabs_key.txt")
    hf_token = read_key("huggingface_token.txt")
    t0 = time.time()
    try:
        v_path, a_path, srt_path, thumb_path = video.create_hybrid_ai_video(
            short_id, script, None, voice_code, "yellow",
            bg_music_path="auto", bg_music_volume=float(st["music_volume"]),
            pexels_api_key=pexels_key or (pixabay_key if st["b_roll_source"] == "pixabay" else ""),
            elevenlabs_api_key=eleven_key or None,
            caption_style=st["caption_style"],
            b_roll_source=st["b_roll_source"],
            meme_sfx_name="None",
            hf_token=hf_token or None,
            style_bg=st["bg_style"],
            style_accent=st["accent"],
            clip_mode=st["clip_mode"],
            voice_preset=voice_preset,
            sfx_level=float(st["sfx_level"]),
            pacing=st.get("pacing", "cinematic"),
            character_bible=_bible,
        )

    except Exception as e:
        crash_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CRASH_REPORT.txt")
        error_trace = traceback.format_exc()
        
        # --- PC WATCHDOG LOGGING ---
        # Capture exact reason: Network, API limit, crash, ZIP, etc.
        reason = "Unknown Crash"
        if "timeout" in str(e).lower() or "connection" in str(e).lower():
            reason = "Network Drop / Timeout"
        elif "402" in str(e) or "429" in str(e) or "budget" in str(e).lower():
            reason = "API Limit / Quota Exceeded"
        elif "zip" in str(e).lower() or "extract" in str(e).lower():
            reason = "Corrupt Download / ZIP Error"
        elif "memory" in str(e).lower():
            reason = "Out of Memory (OOM)"
            
        with open(crash_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== PC WATCHDOG CRASH REPORT ===\n")
            f.write(f"Time: {time.ctime()}\n")
            f.write(f"Topic: {topic}\n")
            f.write(f"Guessed Reason: {reason}\n")
            f.write(f"Error: {e}\n\n")
            f.write(f"Full Traceback:\n{error_trace}\n")
            f.write(f"================================\n")
            
        print(f"\n[!] WATCHDOG TRIGGERED: {reason}")
        print(f"[!] RENDER FAILED: {e}")
        print(f"[!] Wrote full crash details to {crash_log_path}")
        print(f"[!] HALTING autopilot to save your time.\n")
        
        try:
            db.update_short_status(short_id, "failed")
        except Exception:
            pass
        
        # We exit completely instead of continuing to next topic to stop eating 3 hours
        sys.exit(1)

    db.update_short_video(short_id, v_path, a_path, srt_path, status="created")
    print(f"[4/6] Render complete in {time.time()-t0:.0f}s")
    print(f"      Video:  {os.path.basename(v_path)}")
    print(f"      Thumb:  {os.path.basename(thumb_path) if thumb_path else 'n/a'}")
    try:
        _code = db.get_setting("last_code", "")
        if _code:
            print(f"      Code:   {_code}  (outro card — pin it or leave it for the hunters)")
    except Exception:
        pass

    # 5) CONFORMANCE AUDIT — the render witnesses itself before you watch it
    try:
        report = video.run_qc_report(v_path, srt_path,
                                     cosmic=(st.get("bg_style") == "void"),
                                     watermark=st.get("watermark"))
        print("[5/6] QC self-audit (dead frames / style / outro / watermark / audio / captions):")
        for line in report:
            print("      " + line)
        if any(l.startswith(("⚠", "")) for l in report):
            print("      >>> QC FOUND ISSUES — check the timestamps above before uploading")
    except Exception as e:
        print(f"[5/6] QC skipped: {e}")

    # 6) PUBLISH
    if args.no_publish:
        print("[6/6] --no-publish: skipped")
    else:
        token = read_key("github_token.txt")
        if token:
            ok = publish_to_videos_repo(v_path, thumb_path, st["videos_repo"], token)
            print("[6/6] publish " + ("OK" if ok else "FAILED (video is local)") )
        else:
            print("[6/6] no github_token.txt — skipping publish (video is local in video_output/)")

    with open(os.path.join(BASE, "daily_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | {topic} | hook {hook_score} | "
                f"{os.path.basename(v_path)}\n")
    print("-" * 62)
    print("DONE with this video.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Faceless AI Short Studio — daily autopilot")
    ap.add_argument("--topic", help="render THIS topic (queue untouched)")
    ap.add_argument("--count", type=int, default=1,
                    help="render N queued videos in one run (the 'make a batch while I sleep' flag)")
    ap.add_argument("--lang", choices=["en", "hi"], default="en", help="voice language")
    ap.add_argument("--no-publish", action="store_true", help="skip the git push")
    args = ap.parse_args()

    st = load_settings()

    # single explicit topic: render just that one
    if args.topic:
        return render_one(args.topic, st, args)

    # queue batch: pop up to `count` topics, render each, keep going on failure
    done = failed = 0
    for _ in range(max(1, args.count)):
        topic = pop_queue_topic()
        if not topic:
            print("queue.txt is empty — add one topic per line to keep the line moving.")
            break
        rc = render_one(topic, st, args)
        if rc == 0:
            done += 1
        else:
            failed += 1
    print("=" * 62)
    print(f"BATCH COMPLETE: {done} rendered, {failed} failed. "
          f"Topics left in queue: see queue.txt.")
    return 0 if done >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
