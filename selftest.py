# ==============================================================================
# SELF-TEST — run once after every install/overwrite:
#     py selftest.py
# Renders a 12-second dummy video through the FULL pipeline (same settings as
# daily_settings.json) and runs the conformance audit on it. Proves the
# machine is healthy (fonts, ffmpeg, TTS, b-roll, grade, audit) BEFORE you
# burn a real video. Exits 0 = healthy, 1 = something is broken.
# ==============================================================================
import os
import sys
import json

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import video_engine as ve
import db_manager as db

def read_key(name):
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        try:
            return open(p, "r", encoding="utf-8").read().strip()
        except Exception:
            return ""
    return ""

def main():
    st = {}
    sp = os.path.join(BASE, "daily_settings.json")
    if os.path.exists(sp):
        try:
            st = json.load(open(sp, "r", encoding="utf-8"))
        except Exception:
            pass

    print("=" * 60)
    print("SELF-TEST: rendering a 12s dummy through the full pipeline")
    print("=" * 60)

    script = ("[0-3 sec HOOK]\n"
              "Your brain is not broken. It is trained.\n"
              "[PSYCHOLOGY TRIGGER: Curiosity Gap]\n"
              "Every swipe is a tiny reward. The clock never stops.\n"
              "[ENGAGEMENT CTA]\nSave this video so you do not lose it.\n")

    try:
        v, a, s, th = ve.create_hybrid_ai_video(
            1, script, None, "en-US-ChristopherNeural", "yellow",
            bg_music_path="auto", bg_music_volume=float(st.get("music_volume", 0.09)),
            pexels_api_key=read_key("pexels_key.txt") or None,
            b_roll_source=st.get("b_roll_source", "pexels"),
            caption_style=st.get("caption_style", "typewriter"),
            style_bg=st.get("bg_style", "void"),
            style_accent=st.get("accent", "yellow"),
            clip_mode=st.get("clip_mode", "full"),
            voice_preset=st.get("voice_preset", "Deep Narrator Male"),
            sfx_level=float(st.get("sfx_level", 0.7)),
            pacing=st.get("pacing", "cosmic"),
            tricks=False,
            character_bible={"enabled": True, "watermark": st.get("watermark", "")},
            progress_callback=lambda p, t: print(f"[{p*100:5.1f}%] {t}"),
        )
        print(f"\nrender OK: {os.path.basename(v)}")
    except Exception as e:
        print(f"\nRENDER FAILED: {e}")
        return 1

    report = ve.run_qc_report(v, s, cosmic=(st.get("bg_style") == "void"),
                              watermark=st.get("watermark"))
    print("\nSELF-TEST CONFORMANCE AUDIT:")
    bad = []
    for line in report:
        print("  " + line)
        if line.startswith(("⚠", "❌")) and "duration" not in line:
            bad.append(line)   # duration warning is expected on a 12s dummy

    # cleanup the dummy
    try:
        if os.path.exists(v):
            os.remove(v)
        for extra in (os.path.basename(v).replace(".mp4", "_thumbnail.jpg"),
                      os.path.basename(v).replace(".mp4", "_thumbnail_2.jpg"),
                      os.path.basename(v).replace(".mp4", "_thumbnail_3.jpg")):
            p2 = os.path.join(ve.VIDEO_DIR, extra)
            if os.path.exists(p2):
                os.remove(p2)
    except Exception:
        pass

    print("\n" + "=" * 60)
    if bad:
        print(f"SELF-TEST: {len(bad)} ISSUE(S) — fix before real renders:")
        for b in bad:
            print("  - " + b)
        return 1
    print("SELF-TEST: ALL CLEAR — the machine is healthy. Go render.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
