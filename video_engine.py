import zlib
import os
import re
import json
import glob
import gc
import threading
import numpy as np
import requests
import time
import random
import db_manager as db_settings
from moviepy import (
    VideoClip, ImageClip, VideoFileClip, AudioFileClip, AudioClip, CompositeVideoClip, TextClip, CompositeAudioClip, concatenate_audioclips
)
from PIL import Image, ImageDraw, ImageFont
try:
    import style_engine as se
except Exception as _se_err:
    se = None
    print(f"[Warning] style_engine failed to load: {_se_err}")
try:
    import pro_editor as pe
except Exception as _pe_err:
    pe = None
    print(f"[Warning] pro_editor failed to load: {_pe_err}")
try:
    from huggingface_hub import InferenceClient
except ImportError:
    import subprocess
    import sys
    try:
        print("[System Info] 'huggingface_hub' package not found. Programmatically installing it now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
        from huggingface_hub import InferenceClient
    except Exception as e:
        print(f"[Warning] Failed to automatically install 'huggingface_hub': {e}")
        class InferenceClient:
            def __init__(self, *args, **kwargs):
                raise ImportError("Please run: pip install huggingface_hub")

# ==============================================================================
# --- PROACTIVE WINDOWS & PYTHON 3.14 COMPATIBILITY PATCHES ---
# ==============================================================================

original_poll = subprocess.Popen.poll
def safe_poll(self):
    try:
        return original_poll(self)
    except OSError as e:
        if getattr(e, 'winerror', None) == 6 or "handle is invalid" in str(e).lower():
            return 0
        raise
subprocess.Popen.poll = safe_poll

def run_async_in_thread(coro):
    result = []
    exception = []
    def worker():
        try:
            import sys
            import asyncio
            if sys.platform == 'win32':
                try:
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                except:
                    pass
            res = asyncio.run(coro)
            result.append(res)
        except Exception as e:
            exception.append(e)
            
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    if exception:
        raise exception[0]
    return result[0] if result else None

# ==============================================================================

# B8 FIX: anchor all data dirs to the APP FOLDER (not the working directory),
# so the engine works no matter where `py -m streamlit` is launched from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

AUDIO_DIR = os.path.join(BASE_DIR, "audio_clips")
VIDEO_DIR = os.path.join(BASE_DIR, "video_output")
DEFAULT_DIR = os.path.join(BASE_DIR, "default_assets")
B_ROLL_DIR = os.path.join(BASE_DIR, "b_roll_library")

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(DEFAULT_DIR, exist_ok=True)
os.makedirs(B_ROLL_DIR, exist_ok=True)

# ==============================================================================
# TEMP FILE DISCIPLINE (fixes B5 disk leak, B9 Windows file locks, O1 growth)
# A killed render (power cut, OOM, crash) used to leak seg_*.mp4 / moviepy temp
# audio / seed images forever — the disk slowly filled and the ZIPs got heavy.
# ==============================================================================
def _force_delete(path, tries=3):
    """Windows-tolerant delete: file handles can stay locked a few ticks after
    a clip is closed. Retry, then give up quietly (the next startup sweep
    catches anything left behind)."""
    for _i in range(tries):
        try:
            if path and os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception:
            time.sleep(0.25)
    return False


_TEMP_SWEEP_PATTERNS = (
    "seg_*.mp4",               # B5: per-cut segment extractions (the big leak)
    "TEMP_MPY_wvf_snd.*",      # B5: moviepy temp audio (crash leftovers)
    "voice_chain_input.wav",   # B5: pro voice-chain scratch
    "temp_gen_*.jpg",          # B5: AI seed images
    "*_frame_tmp.jpg",         # B5: thumbnail frame scratch
)


def sweep_temp_files():
    """Delete render leftovers from crashed/killed runs. Runs at startup."""
    removed = 0
    for pattern in _TEMP_SWEEP_PATTERNS:
        for d in (BASE_DIR, AUDIO_DIR, os.getcwd()):
            try:
                for name in glob.glob(os.path.join(d, pattern)):
                    if os.path.isfile(name) and _force_delete(name, tries=1):
                        removed += 1
            except Exception:
                pass
    return removed


def prune_output_dirs(keep_videos=12, keep_broll=400):
    """O1: bound disk growth — keep the newest N outputs, delete older.
    Never touches files newer than 2 minutes (a running render)."""
    removed = 0
    now = time.time()
    for d, keep in ((VIDEO_DIR, keep_videos), (B_ROLL_DIR, keep_broll)):
        try:
            files = []
            for name in os.listdir(d):
                if not name.startswith(("short_", "pexels_", "pixabay_", "generative_ai_")):
                    continue
                p = os.path.join(d, name)
                if os.path.isfile(p) and (now - os.path.getmtime(p)) > 120:
                    files.append((os.path.getmtime(p), p))
            files.sort()
            for _mt, p in files[: max(0, len(files) - keep)]:
                if _force_delete(p):
                    removed += 1
        except Exception:
            pass
    return removed


sweep_temp_files()

# --- ADVANCED SEMANTIC CONCEPT EXPANDER ---
CONCEPT_EXPANSIONS = {
    "percent": "luxury penthouse view night",
    "disciplined": "workout training morning sweat",
    "minds": "brain connection cyber glow",
    "mind": "glowing human brain macro",
    "neuro": "glowing digital synapses grid",
    "focus": "macro focus eye iris",
    "boundary": "dark locked gate neon light",
    "harvard": "classic library old books bookshelf",
    "studies": "cinematic retro clock ticking",
    "show": "projector screen lens flare",
    "lock": "cyber padlock key close up",
    "screen": "code matrix lines green",
    "brain": "neon brain holographic rotation",
    "deep": "galaxy deep space cosmic nebulas",
    "friction": "running shoes asphalt fast pace",
    "immediately": "lightning storm striking clouds",
    "automate": "industrial robotic arms assembly",
    "morning": "morning sun rays through foggy forest",
    "performers": "elite executive walking slow motion",
    "waste": "hourglass sand spilling macro",
    "scrolling": "smart phone screen scrolling glow close up",
    "money": "luxury gold bars vault safe",
    "cash": "counting dollar bills hands slow motion",
    "secrets": "mysterious figure shadow smoke",
    "truth": "hundred percent 100 badge neon",
    "mistake": "crumpled paper trash basket",
    "destroying": "fire flames burning close up",
    # Upgrade: Dynamic Semantic mappings for generic stock keywords
    "people": "cinematic silhouettes luxury dark city night",
    "place": "dark moody luxury room background neon glowing",
    "chatting": "shadowy figures talking smoky dark lounge cinematic",
    "phone": "glowing smartphone screen close up dark room hands",
    "talk": "cinematic shadowy silhouettes talking lounge",
    "man": "shadowy man silhouette walking dark street slow motion",
    "woman": "cinematic woman walking dark rain night light close up",
    "think": "close up looking thoughtful moody library warm light",
    "look": "deep focused eye macro cinematic reflections",
    "work": "dark luxury office screen glowing code close up",
    "office": "empty dark luxury office warm lamp light",
    "study": "dark library old bookshelves glowing warm candle",
    "time": "vintage golden hourglass sand running macro dark",
    "busy": "hyperlapse busy city street traffic lights night",
    "success": "luxury sports car driving city night neon",
    "wealth": "gold bars stack vaults dark shadow cinematic",
    "consistency": "slow cinematic ticking grandfather clock gear close up"
}

# --- THE METAPHOR BRAIN: abstract words → cinematic visual metaphors ---
# Pro technique: you never search "dopamine video". You search the FEELING-AS-IMAGE.
# (dopamine → neurons firing, willpower → chain breaking, habit → spinning gears...)
METAPHOR_EXPANSIONS = {
    # --- mind / psychology (your main niche) ---
    "dopamine": "glowing brain neurons firing electric synapses dark macro",
    "serotonin": "calm golden light through abstract waves dark",
    "willpower": "iron chain links breaking slow motion dark",
    "motivation": "spark igniting flame slow motion dark",
    "discipline": "soldier marching through fog silhouette",
    "habit": "spinning mechanical gears loop macro dark",
    "addiction": "rope chains binding hands dark close up",
    "fear": "shadow figure standing in dark hallway",
    "anxiety": "tangled wires electric tension close up",
    "stress": "water pressure waves dark macro",
    "trauma": "cracked glass slow motion dark",
    "memory": "old film reel spinning warm light",
    "overthinking": "spinning maze top view dark",
    "decision": "fork in the road in fog",
    "choice": "fork in the road in fog",
    "confidence": "person walking through glass doors slow motion",
    "self-control": "hand pressing glowing control button dark",
    "patience": "hourglass sand slow motion warm",
    "anger": "red embers burning close up dark",
    "regret": "fading old photograph dissolving",
    "guilt": "heavy chains dragging floor dark",
    "shame": "face hidden in shadow dark",
    "pride": "head raised against sunrise silhouette",
    "ego": "cracked mirror reflection",
    "identity": "face half in shadow half in light",
    "self-worth": "gold coin in hand spotlight",
    "purpose": "single beam of light through darkness",
    "meaning": "deep forest light beams",
    "dream": "drifting clouds golden sunrise",
    "ambition": "climber reaching mountain peak storm",
    "success": "gold trophy on podium spotlight",
    "failure": "chess piece knocked over slow motion",
    "risk": "tightrope walker over void dark",
    "reward": "gold coins falling slow motion",
    "comfort": "warm candle flame cozy dark",
    "struggle": "hands climbing rock wall close up",
    "peace": "still lake mirror reflection dawn",
    "calm": "mist over still water slow",
    "chaos": "shattered glass frozen explosion",
    "order": "perfectly aligned chess pieces dark",
    "loop": "circular neon light track rotating dark",
    "cycle": "rotating clock hands time lapse",
    "pattern": "neon fractal pattern forming dark",
    "trigger": "finger on glowing button dark close up",
    "signal": "pulsing neon light waves dark",
    "reaction": "lightning bolt strike dark clouds",
    "instinct": "animal eyes glowing in dark",
    "impulse": "sparks jumping between metal dark",
    "control": "hand on glowing control wheel dark",
    "freedom": "bird silhouette flying into sunrise",
    "free": "bird silhouette flying into sunrise",
    "demand": "crowd reaching up toward light dark",
    "stuck": "tangled rope knot close up dark",
    "different": "two diverging paths fog light",
    "top": "summit peak above clouds sunrise",
    "neuroscience": "glowing brain circuit dark macro",
    "real": "crystal clear water surface light",
    "strict": "metal ruler straight edge close up",
    "true": "scales balanced light dark",
    "pattern": "neon fractal pattern forming dark",
    "hidden": "mysterious figure shadow smoke dark",
    "trap": "sinking into quicksand silhouette",
    "loop": "circular neon light track rotating dark",
    "trapped": "gloves in barbed wire dark",
    "escape": "door opening into bright light dark room",
    "wall": "concrete wall single crack light",
    "ceiling": "looking up at dark ceiling light",
    "floor": "looking down dark stairs",
    "foundation": "deep building foundations concrete",
    "root": "tree roots in dark soil macro",
    "core": "glowing core center dark sphere",
    "balance": "yogi balancing silhouette beam",
    "harmony": "chord ripples in water",
    "conflict": "two shadows facing off dark",
    "tension": "stretched rubber band extreme close up",
    "release": "dam gates opening water rush",
    "pressure": "deep sea water pressure dark",
    "weight": "heavy iron weights lifting gym",
    "burden": "back bent under heavy load silhouette",
    "rise": "sunrise over dark horizon time lapse",
    "fall": "leaves falling in wind slow motion",
    "climb": "hand gripping climbing hold dark",
    "peak": "mountain peak above clouds sunrise",
    "momentum": "bowling ball rolling dark lane",
    "flow": "ink flowing in water slow motion",
    "current": "river current fast dark",
    "stream": "river stream forest light",
    "ocean": "ocean waves dark storm",
    "wave": "ocean wave crest dark",
    "tide": "ocean tide pulling rocks",
    "thunder": "thunderstorm dark clouds lightning",
    "lightning": "lightning strike dark night",
    "ash": "ash particles floating dark",
    "mist": "mist drifting through forest",
    "fog": "fog rolling over dark city",
    "cloud": "dramatic clouds time lapse",
    "sky": "vast dark sky stars",
    "sun": "sun breaking through clouds",
    "moon": "full moon dark sky",
    "star": "single bright star dark sky",
    "spark": "sparks flying slow motion dark",
    "ember": "glowing ember close up dark",
    "flame": "flame dancing dark background",
    "smoke": "smoke curling in dark light",
    "shadow": "long shadow walking dark street",
    "light": "single light beam through darkness",
    "dark": "deep darkness single light",
    "darkness": "deep darkness single light",
    "bright": "bright light burst dark",
    "midnight": "midnight city skyline dark",
    "reset": "clean empty desk morning light",
    "restart": "engine starting garage dark",
    "transform": "caterpillar butterfly macro",
    "change": "pages flipping fast close up",
    "shift": "switch flipping light dark",
    "grow": "plant sprout growing timelapse dark soil",
    "shrink": "balloon deflating slow motion",
    "expand": "balloon inflating close up",
    "simple": "single line on white minimal",
    "complex": "tangled knot ropes close up",
    "clear": "clear water ripples light",
    "confuse": "spiral staircase top view",
    "understand": "light bulb turning on dark",
    "realize": "eyes opening close up light",
    "believe": "hand holding small light dark",
    "doubt": "scales tipping dark close up",
    "hope": "single candle in storm",
    "faith": "hand reaching up to light",
    "luck": "four leaf clover macro",
    "chance": "door ajar with light",
    "destiny": "star map glowing dark",
    "fate": "cards being dealt table",
    "story": "old book opening pages",
    "journey": "road disappearing into mountains",
    "path": "narrow path through dark forest",
    "road": "empty road night headlights",
    "start": "runner breaking starting blocks",
    "finish": "crossing finish line ribbon",
    "end": "setting sun horizon dark",
    "beginning": "first crack of dawn",
    "middle": "bridge over valley",
    "turn": "car turning corner night light",
    "step": "footsteps on wet pavement night",
    "progress": "neon progress bar filling dark",
    "improve": "rising graph line neon dark",
    "level": "neon level up dark",
    "upgrade": "arrow up through glass dark",
    "master": "master chess move close up",
    "expert": "precise hands working dark",
    "beginner": "first step onto dark stage",
    "student": "student studying lamp night",
    "teacher": "chalk writing board close up",
    "mentor": "hand guiding another hand",
    "leader": "leader silhouette facing crowd",
    "team": "team huddle silhouettes night",
    "solo": "one figure vast landscape",
    "crowd": "crowd from above night lights",
    "audience": "theater seats dark light",
    "public": "city crowd time lapse night",
    "private": "closed door keyhole light",
    "social": "many connected lights dark",
    "media": "screens wall glow dark room",
    "internet": "neon network globe dark",
    "world": "earth from space dark",
    "society": "building skyline night",
    "culture": "traditional mask collection dark",
    "family": "hands stacked together warm",
    "friend": "two chairs by fire",
    "stranger": "face in crowd blur night",
    "enemy": "dark figure across table",
    "partner": "two hands one rope",
    # --- relationships / intimacy ---
    "love": "two hands holding candle warm dark",
    "trust": "two hands firm handshake close up",
    "attraction": "magnets pulling sparks close up",
    "chemistry": "chemical reaction flask glow dark",
    "intimacy": "two silhouettes close warm light",
    "connection": "two lights connecting beam dark",
    "betrayal": "broken ring in half dark",
    "jealousy": "red mist over eyes dark",
    "respect": "hand over heart warm light",
    "apology": "hand extended across table",
    "fight": "sparks between metal dark close up",
    "forgiveness": "broken chain released light",
    "commitment": "rings on velvet box dark",
    "distance": "two figures far apart bridge",
    "close": "two faces close silhouette",
    "kiss": "lips close up slow motion",
    "touch": "fingertips touching close up",
    "hug": "embrace silhouette warm light",
    "argue": "shattered mirror dark",
    "break": "breaking rope slow motion dark",
    "together": "two puzzle pieces locking",
    "apart": "two boats drifting apart sea",
    "reunion": "door opening two silhouettes light",
    "heart": "glowing heart beating macro dark",
    "soul": "glowing spirit dark background",
    "desire": "burning ember close up dark",
    "passion": "flame rising dark background",
    "romance": "candle light dinner table dark",
    "secret": "locked diary candle light",
    "promise": "hand over heart candle",
    "loyalty": "dog silhouette guarding gate",
    # --- money / growth ---
    "debt": "chains of coins binding dark",
    "invest": "hand planting seed in soil",
    "return": "returning arrow to bow",
    "profit": "rising green chart neon dark",
    "earn": "coins dropping into jar",
    "save": "gold coins into vault safe",
    "spend": "bills flying out of hand",
    "cost": "scales weighing gold coins",
    "price": "price tag on gold bar",
    "bank": "bank vault door opening",
    "loan": "hand over signed contract",
    "income": "coins pouring from pipe",
    "salary": "envelope with cash on desk",
    "budget": "calculator with coins close up",
    "luxury": "luxury car interior night",
    "status": "gold nameplate office",
    "power": "lightning in glass jar dark",
    "influence": "one domino knocking many dark",
    "network": "neon connection nodes dark",
    "deal": "handshake over contract",
    "scam": "card trick hands close up",
    "trap": "sinking into quicksand silhouette",
    "game": "chess board close up dark",
    "play": "dice rolling close up dark",
    "bet": "casino chips stacking",
    "win": "confetti falling gold",
    "lose": "chess piece falling table",
    "compete": "two runners starting line",
    "rival": "two silhouettes facing off dark",
    # --- time / focus / action ---
    "hour": "vintage clock ticking macro dark",
    "minute": "clock hands moving macro",
    "second": "stopwatch counting dark",
    "fast": "speeding car light trails night",
    "slow": "slow motion water droplets",
    "rush": "crowd moving fast blur night",
    "pause": "paused film frame dark",
    "deadline": "red alarm clock spinning",
    "schedule": "calendar pages flipping",
    "routine": "identical doors in a row dark",
    "distraction": "phone light in dark room",
    "attention": "searchlight beam dark",
    "concentrate": "lens focusing light beam dark",
    "relax": "steam rising from tea cup",
    "rest": "sleeping cat by window",
    "sleep": "moon over sleeping city",
    "wake": "sunrise over bed curtain",
    "train": "athlete training gym dark",
    "learn": "open book pages flipping candle",
    "knowledge": "library of glowing books dark",
    "wisdom": "ancient scroll candle light",
    "skill": "hand playing piano close up",
    "talent": "light bulb glowing dark",
    "genius": "brain circuit glowing dark",
    "smart": "neon brain connection dark",
    "intelligent": "glowing digital synapses grid dark",
    "lazy": "empty bed unmade morning light",
    "effort": "sweat drop close up dark",
    "hard": "rock wall climbing dark",
    "easy": "smooth rolling ball light",
    "execute": "fist striking target dark",
    "action": "runner exploding start dark",
    "act": "hand raising light dark",
    "build": "hands building blocks light",
    "create": "hands sculpting light dark",
    "destroy": "crashing wave dark",
    "fix": "hands repairing machinery light",
    "heal": "hands holding light dark",
    "cure": "medicine bottle light dark",
    "poison": "dark liquid dripping",
    "dose": "measuring spoon close up",
    "pump": "pump handle pumping dark",
    "inject": "syringe close up dark",
    "habit": "spinning mechanical gears loop macro dark",
    "morning": "morning sun rays through foggy forest",
    "evening": "evening sky city lights",
    "night": "midnight city skyline dark",
    "work": "dark luxury office screen glowing code close up",
    "office": "empty dark luxury office warm lamp light",
    "study": "dark library old bookshelves glowing warm candle",
    "time": "vintage golden hourglass sand running macro dark",
    "busy": "hyperlapse busy city street traffic lights night",
    "success": "luxury sports car driving city night neon",
    "wealth": "gold bars stack vaults dark shadow cinematic",
    "consistency": "slow cinematic ticking grandfather clock gear close up",
    "money": "luxury gold bars vault safe",
    "cash": "counting dollar bills hands slow motion",
    "secrets": "mysterious figure shadow smoke",
    "truth": "hundred percent 100 badge neon",
    "mistake": "crumpled paper trash basket",
    "destroying": "fire flames burning close up",
    "people": "cinematic silhouettes luxury dark city night",
    "place": "dark moody luxury room background neon glowing",
    "chatting": "shadowy figures talking smoky dark lounge cinematic",
    "phone": "glowing smartphone screen close up dark room hands",
    "talk": "cinematic shadowy silhouettes talking lounge",
    "man": "shadowy man silhouette walking dark street slow motion",
    "woman": "cinematic woman walking dark rain night light close up",
    "think": "close up looking thoughtful moody library warm light",
    "look": "deep focused eye macro cinematic reflections",
    "brain": "neon brain holographic rotation",
    "mind": "glowing human brain macro",
    "neuro": "glowing digital synapses grid",
    "focus": "macro focus eye iris",
    "boundary": "dark locked gate neon light",
    "lock": "cyber padlock key close up",
    "screen": "code matrix lines green",
    "deep": "galaxy deep space cosmic nebulas",
    "friction": "running shoes asphalt fast pace",
    "immediately": "lightning storm striking clouds",
    "automate": "industrial robotic arms assembly",
    "performers": "elite executive walking slow motion",
    "waste": "hourglass sand spilling macro",
    "scrolling": "smart phone screen scrolling glow close up",
    "percent": "luxury penthouse view night",
    "disciplined": "workout training morning sweat",
    "minds": "brain connection cyber glow",
    "harvard": "classic library old books bookshelf",
    "studies": "cinematic retro clock ticking",
    "show": "projector screen lens flare",
}

# merge the metaphor brain into the concept expander
CONCEPT_EXPANSIONS.update(METAPHOR_EXPANSIONS)

# --- COSMIC B-ROLL VOCABULARY (GOONINGGNG mode) ---
# The reference channel's entire visual world = Cosmos + Time + Mind, dark-graded.
# In void mode the metaphor engine is overridden by this map: no cities, no
# people, no stock "man walking" — only deep-space, clocks, and brains.
COSMIC_SEARCHES = {
    "brain": "dark galaxy nebula space",
    "mind": "milky way stars night sky dark",
    "neuro": "brain neurons dark macro",
    "dopamine": "neurons firing dark macro",
    "time": "vintage clock face roman numerals dark",
    "clock": "vintage clock face roman numerals dark",
    "habit": "vintage clock face roman numerals dark",
    "fear": "dark red nebula space",
    "anxiety": "dark nebula space storm",
    "trap": "dark nebula space vortex",
    "stuck": "dark space nebula slow",
    "escape": "comet stars night sky",
    "freedom": "stars night sky wide",
    "focus": "single star night sky dark",
    "attention": "shooting star night sky",
    "decision": "two stars night sky dark",
    "willpower": "vintage clock face roman numerals dark",
    "discipline": "vintage clock face roman numerals dark",
    "overthinking": "spiral galaxy dark",
    "sleep": "moon stars night sky dark",
    "dream": "nebula purple dark space",
    "truth": "moon dark sky stars",
    "secret": "dark nebula space mystery",
    "power": "eclipse dark space",
    "energy": "nebula bright core space",
    "death": "dark space stars void",
    "life": "nebula stars birth space",
    "change": "galaxy swirl dark space",
    "danger": "dark red nebula space",
    "calm": "still stars night sky",
    "chaos": "nebula swirl dark space",
    "money": "dark space nebula gold",
    "love": "two stars binary night sky",
    "heart": "red nebula dark space",
    "soul": "nebula glow dark space",
    "habit_": "clock dark macro",
}
COSMIC_POOL = [
    "dark nebula space slow", "galaxy stars night sky", "vintage clock face roman numerals",
    "brain neurons dark", "comet star field night", "milky way stars dark",
    "eclipse dark space", "moon stars night sky", "spiral galaxy dark",
    "vintage clock face roman numerals", "ink in water dark", "dark ocean wave night",
]

# --- VTT-SYNCED B-ROLL SELECTION (pro fix: the clip must match the word being
# SPOKEN at that moment — never a rotating list from the whole script) ---
GENERIC_WORDS = {
    # pronouns / people-generic (these caused "a girl in different worlds")
    "she", "her", "hers", "he", "him", "his", "they", "them", "their", "it", "its",
    "you", "your", "yours", "we", "us", "our", "i", "my", "me",
    "woman", "women", "girl", "girls", "man", "men", "people", "person",
    "somebody", "someone", "everyone", "nobody", "anyone", "face", "faces",
    "eye", "eyes", "hand", "hands", "body", "head", "hair", "voice", "voices",
    # function words / adverbs (searching these returns garbage like "too" → flowers)
    "too", "very", "really", "just", "only", "even", "still", "now", "then", "here",
    "there", "this", "that", "these", "those", "what", "which", "who", "when",
    "where", "how", "why", "can", "could", "will", "would", "should", "do", "does",
    "did", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "not", "no", "yes", "and", "but", "or", "if", "so", "as", "at", "by", "for",
    "from", "into", "of", "on", "onto", "up", "with", "without", "about", "after",
    "before", "between", "over", "under", "again", "further", "once", "during",
    "while", "because", "through", "until", "against", "both", "each", "few",
    "more", "most", "other", "some", "such", "than", "own", "same", "also",
    "well", "back", "little", "yet", "the", "a", "an", "in", "to", "of", "and",
}


# Concrete nouns that are SAFE to search raw on Pexels (they have real footage).
# Anything not on this list (and not in the metaphor map) → hold previous visual.
CONCRETE_NOUNS = {
    "kitchen", "kitchen", "ocean", "sea", "river", "lake", "pool", "water", "ice",
    "stone", "rock", "sand", "soil", "seed", "seeds", "leaf", "leaves", "tree",
    "trees", "forest", "jungle", "desert", "beach", "wave", "waves", "tide",
    "mountain", "mountains", "hill", "valley", "cave", "city", "town", "village",
    "street", "road", "path", "bridge", "tunnel", "building", "buildings",
    "house", "home", "room", "office", "desk", "chair", "table", "bed", "door",
    "doors", "window", "windows", "wall", "walls", "floor", "ceiling", "roof",
    "garden", "park", "school", "library", "museum", "theater", "cinema",
    "church", "temple", "hospital", "lab", "factory", "farm", "field",
    "coffee", "tea", "wine", "bread", "food", "book", "books", "paper", "pen",
    "pencil", "key", "keys", "lock", "gate", "clock", "watch", "hourglass",
    "candle", "candles", "sun", "moon", "star", "stars", "sky", "cloud",
    "clouds", "rain", "snow", "storm", "lightning", "smoke", "ash", "flame",
    "flames", "fire", "ember", "embers", "spark", "sparks", "light", "shadow",
    "shadows", "mirror", "camera", "phone", "screen", "screens", "code", "guitar",
    "piano", "violin", "music", "glove", "gloves", "ring", "rings", "chain",
    "chains", "rope", "rope", "coin", "coins", "cash", "bills", "money",
    "vault", "safe", "card", "cards", "dice", "chess", "puzzle", "puzzle",
    "ladder", "staircase", "stairs", "elevator", "car", "cars", "bike", "train",
    "plane", "boat", "ship", "balloon", "butterfly", "bird", "birds", "dog",
    "cat", "horse", "lion", "tiger", "eagle", "snake", "wolf", "bear",
}


def spoken_word_in_window(start_t, end_t, vtt_subs, used_words):
    """Find the best searchable word being SPOKEN during [start_t, end_t].
    Priority: words with a metaphor/concept entry. Skips generic words.
    Returns None when nothing meaningful is spoken (→ reuse previous clip)."""
    if not vtt_subs:
        return None
    for s in vtt_subs:
        if s['end'] <= start_t or s['start'] >= end_t:
            continue
        w = re.sub(r'[^a-z0-9]', '', str(s['text']).lower())
        if len(w) < 3 or w in GENERIC_WORDS:
            continue
        if w in CONCEPT_EXPANSIONS and w not in used_words:
            return w
    # second pass: ONLY concrete nouns (kitchen, ocean, watch...) are safe raw
    # searches. Abstract/unknown words → None → the previous visual continues
    # (pro editors hold the visual when they can't illustrate the word).
    for s in vtt_subs:
        if s['end'] <= start_t or s['start'] >= end_t:
            continue
        w = re.sub(r'[^a-z0-9]', '', str(s['text']).lower())
        if w in GENERIC_WORDS or w in used_words:
            continue
        if w in CONCRETE_NOUNS:
            return w
    return None


def expand_keyword_to_concept(word, cosmic=False):
    word_clean = str(word).lower().strip()
    if cosmic:
        if word_clean in COSMIC_SEARCHES:
            return COSMIC_SEARCHES[word_clean]
        for k, v in COSMIC_SEARCHES.items():
            if len(k) > 3 and k in word_clean:
                return v
        return None  # no cosmic match -> caller draws from the cosmic pool
    return CONCEPT_EXPANSIONS.get(word_clean, f"aesthetic {word_clean}")


# --- B-ROLL VARIETY ENGINE ---
RECENT_BROLL_FAMILIES = []

def get_variety_cosmic_concept(query):
    global RECENT_BROLL_FAMILIES
    
    # Categorize the pool into families
    families = {
        "clock": ["vintage clock face roman numerals", "vintage clock face roman numerals dark", "clock dark macro"],
        "brain": ["brain neurons dark", "neurons firing dark macro", "dark macro brain"],
        "nebula": ["dark nebula space slow", "spiral galaxy dark", "dark red nebula space", "dark nebula space vortex", "nebula swirl dark space"],
        "comet": ["comet star field night", "shooting star night sky", "comet stars night sky"],
        "moon": ["moon stars night sky", "moon dark sky stars"],
        "abstract": ["eclipse dark space", "ink in water dark", "dark ocean wave night"]
    }
    
    # What family did the query map to natively?
    seed_idx = zlib.crc32(str(query).encode("utf-8"))
    
    # We want to pick a family that isn't in the last 2 used.
    available_families = [f for f in families.keys() if f not in RECENT_BROLL_FAMILIES[-2:]]
    if not available_families:
        available_families = list(families.keys())
        
    chosen_family = available_families[seed_idx % len(available_families)]
    
    # Pick a shot from that family
    shots = families[chosen_family]
    chosen_shot = shots[seed_idx % len(shots)]
    
    RECENT_BROLL_FAMILIES.append(chosen_family)
    if len(RECENT_BROLL_FAMILIES) > 4:
        RECENT_BROLL_FAMILIES.pop(0)
        
    return chosen_shot

# --- KEYWORD EXTRACTOR FOR AUTOMATED B-ROLL SEARCH ---
def extract_best_keywords(text, num_words=12):
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at', 'with', 'by', 'to', 'for', 'and', 'but', 
        'or', 'if', 'then', 'else', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 
        'my', 'your', 'his', 'her', 'its', 'our', 'their', 'how', 'why', 'what', 'who', 'whom', 'here', 'there', 
        'about', 'stop', 'doing', 'right', 'now', 'your', 'mine', 'all', 'any', 'get', 'gets', 'got', 'use', 'using',
        'has', 'have', 'had', 'been', 'actually', 'thing', 'one', 'two', 'three'
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    
    result = []
    seen = set()
    for w in filtered:
        if w not in seen:
            seen.add(w)
            result.append(w)
            if len(result) >= num_words:
                break
    return result if result else ["abstract"]

# --- PEXELS HOURLY BUDGET GATE (fix F2) ---
# Free tier = 200 API calls/hour. A 5-video batch with ~20 cuts each would
# burn 100+ searches and 429 halfway through. We track calls per hour and
# auto-switch to Pixabay (separate budget) the moment the cap is near.
PEXELS_GATE = {"window_start": 0.0, "count": 0, "blocked_until": 0.0, "announced": False}
PEXELS_HOUR_LIMIT = 190   # safety margin under the 200 cap


def _pexels_gate_open():
    now = time.time()
    if now - PEXELS_GATE["window_start"] >= 3600:
        PEXELS_GATE["window_start"] = now
        PEXELS_GATE["count"] = 0
        PEXELS_GATE["announced"] = False
    return now >= PEXELS_GATE["blocked_until"] and PEXELS_GATE["count"] < PEXELS_HOUR_LIMIT


def _pexels_charge():
    PEXELS_GATE["count"] += 1


def _pexels_trip_block(reason=""):
    PEXELS_GATE["blocked_until"] = time.time() + 3600
    PEXELS_GATE["announced"] = False
    print(f"[Pexels] {reason} — using Pixabay for the rest of this hour.")


# --- PEXELS DYNAMIC VIDEO DOWNLOADER ---
def download_pexels_b_roll(query, api_key):
    clean_query = str(query).replace(" ", "+")

    if not _pexels_gate_open():
        if not PEXELS_GATE["announced"]:
            PEXELS_GATE["announced"] = True
            print("[Pexels] Hourly API budget (200 req/hr) nearly used — switching to Pixabay.")
        return None

    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={clean_query}&per_page=15&orientation=portrait"

    try:
        _pexels_charge()
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 429:
            _pexels_trip_block("rate limit hit (HTTP 429)")
            return None
        if r.status_code == 200:
            data = r.json()
            videos = data.get("videos", [])
            if videos:
                selected_v = random.choice(videos[:min(len(videos), 6)])
                video_id = selected_v.get("id")
                
                local_path = os.path.join(B_ROLL_DIR, f"pexels_{clean_query.lower()}_{video_id}_916.mp4")
                if os.path.exists(local_path):
                    return local_path
                    
                video_files = selected_v.get("video_files", [])
                # SPEED FIX: pick the SMALLEST portrait mp4 (the old code took
                # the first portrait found — often the biggest file = 2-4x slower
                # downloads on every new b-roll word)
                portrait_files = [vf for vf in video_files
                                  if vf.get("file_type") == "video/mp4"
                                  and (vf.get("width") or 0) < (vf.get("height") or 0)
                                  and vf.get("link")]
                if portrait_files:
                    portrait_files.sort(key=lambda vf: vf.get("size") or 999999999)
                    target_link = portrait_files[0].get("link")
                elif video_files:
                    target_link = video_files[0].get("link")
                else:
                    target_link = None
                    
                if target_link:
                    video_res = requests.get(target_link, timeout=40)
                    # CORRUPT-DOWNLOAD GUARD: CDN errors can arrive as HTTP 200
                    # with an HTML body — writing that to .mp4 creates a file
                    # that crashes the render or plays as a dead-black frame.
                    if video_res.status_code == 200:
                        body = video_res.content
                        if len(body) < 50000 or body[4:8] != b"ftyp":
                            print(f"Pexels: bad file for '{clean_query}' (not a valid mp4) — skipping")
                            return None
                        with open(local_path, "wb") as f:
                            f.write(body)
                        return local_path
    except Exception as e:
        print(f"Pexels search failed for '{query}': {e}")
    return None

# --- PIXABAY FREE DYNAMIC VIDEO DOWNLOADER ---
def download_pixabay_b_roll(query, api_key):
    clean_query = str(query).replace(" ", "+")
    key = api_key if api_key and api_key.strip() else "29302502-3c7b3986a7d6537bfbc6f1d2d"
    url = f"https://pixabay.com/api/videos/?key={key}&q={clean_query}&video_type=all&per_page=10"
    
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            if hits:
                selected_h = random.choice(hits[:min(len(hits), 5)])
                video_id = selected_h.get("id")
                local_path = os.path.join(B_ROLL_DIR, f"pixabay_{clean_query.lower()}_{video_id}_916.mp4")
                
                if os.path.exists(local_path):
                    return local_path
                    
                videos_dict = selected_h.get("videos", {})
                video_url = None
                for size in ["medium", "small", "tiny"]:
                    v_info = videos_dict.get(size, {})
                    video_url = v_info.get("url")
                    if video_url:
                        break
                        
                if video_url:
                    video_res = requests.get(video_url, timeout=40)
                    if video_res.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(video_res.content)
                        return local_path
    except Exception as e:
        print(f"Pixabay search failed for '{query}': {e}")
    return None

# --- PEXELS/PIXABAY AUTOMATED BACKUP KEYWORD DOWNLOADER WITH COLOR TONE MATCHING ---
def download_pexels_b_roll_with_fallback(query, api_key, source="pexels", color_tone="aesthetic", cosmic=False):
    clean_query = f"{query} {color_tone}" if color_tone else query
    expanded = expand_keyword_to_concept(clean_query, cosmic=cosmic)
    if cosmic and expanded is None:
        # no cosmos match for this word: deterministic draw from the cosmic pool
                expanded = get_variety_cosmic_concept(query)
    
    clip = None
    if source == "pixabay":
        clip = download_pixabay_b_roll(expanded, api_key)
    else:
        clip = download_pexels_b_roll(expanded, api_key)
        
    if clip and os.path.exists(clip):
        return clip
        
    backups = [f"moody {color_tone}", f"urban night {color_tone}", f"focused student {color_tone}", f"ticking clock {color_tone}", f"rain window {color_tone}"]
    backup_query = random.choice(backups)
    
    if source == "pixabay":
        return download_pixabay_b_roll(backup_query, api_key)
    return download_pexels_b_roll(backup_query, api_key)

# --- TRUE DYNAMIC GENERATIVE AI TEXT-TO-VIDEO INTEGRATION (WITH ADVANCED SECURE DNS FALLBACK ENGINES!) ---
# F4: HF inference credits often 402 after depletion, and each failed attempt
# costs ~40s per clip. Circuit breaker: 2 consecutive failures → skip HF for
# 10 minutes and go straight to the backup layer (Pollinations / stock).
HF_CIRCUIT = {"fails": 0, "open_until": 0.0}


def load_pollinations_key():
    """B3: optional Pollinations key (sk_/pk_) = no rate limit, no watermark.
    Source: pollinations_key.txt in the app folder, or the POLLINATIONS_KEY env."""
    try:
        v = os.environ.get("POLLINATIONS_KEY", "").strip()
        if v:
            return v
        p = os.path.join(BASE_DIR, "pollinations_key.txt")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


# ==============================================================================
# PIECE 4 — CHARACTER BIBLE: the channel's locked visual identity.
# One description + ONE fixed seed = the SAME look in every video (kills
# identity drift: "even identical prompts produce different results" is fixed
# by pinning the seed + a fixed character description).
# ==============================================================================
CHARACTER_BIBLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "character_bible.json")
DEFAULT_CHARACTER_BIBLE = {
    "enabled": True,
    "name": "The Narrator",
    "description": "cinematic young man, short dark hair, black leather jacket, calm confident expression, cinematic rim lighting",
    "style_suffix": "dark cinematic atmosphere, moody cinematic lighting, 8k, photorealistic, vertical 9:16 composition",
    "seed": 421337,
}


def load_character_bible():
    try:
        if os.path.exists(CHARACTER_BIBLE_PATH):
            with open(CHARACTER_BIBLE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_CHARACTER_BIBLE)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_CHARACTER_BIBLE)


def save_character_bible(data):
    try:
        with open(CHARACTER_BIBLE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def _bible_prompt(prompt, bible, seed_offset):
    """Build the consistent character prompt + deterministic seed (piece 4)."""
    if bible and bible.get("enabled", True) and bible.get("description"):
        full_prompt = f"{bible['description']}, scene: {prompt}, {bible.get('style_suffix', 'dark cinematic, 8k, photorealistic, vertical 9:16')}"
        seed = int(bible.get("seed", 421337)) + int(seed_offset)
    else:
        full_prompt = f"aesthetic portrait 9:16 vertical close up of {prompt}, dark luxury atmosphere, highly cinematic, 8k resolution, photorealistic"
        seed = random.randint(1, 999999)
    return full_prompt, seed


def generate_true_ai_video_clip(prompt, hf_token, bible=None, seed_offset=0, prefer_pollinations=False):
    """
    PIECES 4+5 — AI clip generator with CHARACTER BIBLE + AUTO MODE.
    Order: prefer_pollinations=True (Auto mode) -> Pollinations first (keyless,
    never depletes), HF second. Default: HF first, Pollinations second.
    Bible locks the character (fixed description + fixed seed) so video #50
    looks like video #1.
    """
    import urllib.parse
    clean_prompt = str(prompt).replace(" ", "_").lower()
    local_path = os.path.join(B_ROLL_DIR, f"generative_ai_{clean_prompt[:20]}_916.mp4")

    if os.path.exists(local_path):
        return local_path

    temp_img_path = os.path.join(B_ROLL_DIR, f"temp_gen_{clean_prompt[:20]}.jpg")
    img_obtained = False
    full_prompt, seed = _bible_prompt(prompt, bible, seed_offset)

    def _try_hf():
        if time.time() < HF_CIRCUIT["open_until"]:
            return False   # F4: circuit open — skip the 40s dead attempt
        try:
            print(f"Generative AI: Attempting Hugging Face InferenceClient...")
            client = InferenceClient(provider="fal-ai", api_key=hf_token)
            img = client.text_to_image(full_prompt, model="black-forest-labs/FLUX.1-dev")
            img.save(temp_img_path, format="JPEG")
            print("Generative AI: Seed image drawn via Hugging Face.")
            HF_CIRCUIT["fails"] = 0
            return True
        except Exception as e:
            HF_CIRCUIT["fails"] += 1
            if HF_CIRCUIT["fails"] >= 2:
                HF_CIRCUIT["open_until"] = time.time() + 600
                HF_CIRCUIT["fails"] = 0
                print("Generative AI: HF failing repeatedly (likely credits 402/depleted) — skipping HF for 10 min, using backup layer.")
            else:
                print(f"Generative AI: Hugging Face failed ({e}). Trying next layer...")
            return False

    def _try_pollinations():
        try:
            # B3: with a key (sk_/pk_) = no rate limit, no watermark, faster lane
            poll_key = load_pollinations_key()
            print(f"Generative AI: Drawing seed image via Pollinations.ai ({'keyed' if poll_key else 'keyless, rate-limited'}, fixed seed {seed})...")
            encoded_prompt = urllib.parse.quote(full_prompt)
            pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&model=flux&seed={seed}"
            headers = {}
            if poll_key:
                pollinations_url += f"&key={urllib.parse.quote(poll_key)}"
                headers = {"Authorization": f"Bearer {poll_key}"}
            response = requests.get(pollinations_url, headers=headers, timeout=120)
            if response.status_code == 200 and len(response.content) > 5000:
                with open(temp_img_path, "wb") as f:
                    f.write(response.content)
                print("Generative AI: Seed image drawn via Pollinations.")
                return True
            print(f"Generative AI: Pollinations invalid response (code: {response.status_code}).")
            return False
        except Exception as e:
            print(f"Generative AI: Pollinations drawing failed: {e}")
            return False

    # --- LAYER ORDER (AUTO MODE: Pollinations primary — keyless, never 402) ---
    if prefer_pollinations:
        img_obtained = _try_pollinations()
        if not img_obtained and hf_token and hf_token.strip():
            img_obtained = _try_hf()
    else:
        if hf_token and hf_token.strip():
            img_obtained = _try_hf()
        if not img_obtained:
            img_obtained = _try_pollinations()
            
    # --- STEP 3: ANIMATE THE IMAGE INTO A GORGEOUS 24FPS VIDEO LOOP! ---
    if img_obtained and os.path.exists(temp_img_path):
        try:
            print(f"Generative AI: Animating seed image with native 15% smooth Ken Burns slideshow engine...")
            clip = make_ken_burns_clip(temp_img_path, duration=4.0)
            
            # Save clip as MP4 passing the Windows Media Player black-screen safe yuv420p pixel format
            clip.write_videofile(
                local_path,
                fps=24,
                codec="libx264",
                audio=False,
                ffmpeg_params=["-pix_fmt", "yuv420p"]
            )
            clip.close()
            
            # Clean up temporary seed image
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)
                
            print(f"Generative AI: Dynamic Ken Burns vertical video compiled successfully: {local_path}")
            return local_path
        except Exception as e:
            print(f"Generative AI: Slideshow compilation stage failed: {e}")
            if os.path.exists(temp_img_path):
                try:
                    os.remove(temp_img_path)
                except Exception:
                    pass
                
    return None

# --- NATIVE AUTOMATIC ROYALTY-FREE BACKGROUND MUSIC DOWNLOADER ---
def download_free_soundtrack(track_name):
    local_path = os.path.join(DEFAULT_DIR, f"music_{track_name}.mp3")
    if os.path.exists(local_path):
        return local_path
        
    urls = {
        "dramatic": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "ambient": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        "lofi": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"
    }
    
    url = urls.get(track_name.lower())
    if url:
        try:
            print(f"Downloading free background soundtrack loop: '{track_name.upper()}'...")
            r = requests.get(url, timeout=25)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return local_path
        except Exception as e:
            print(f"Free soundtrack download failed: {e}")
    return None

# --- NATIVE AUTOMATIC ROYALTY-FREE MEME SOUND EFFECTS DOWNLOADER ---
# REFERENCE SFX PACK — real SFX extracted from the viral reference short the
# user provided (ref_video3). Local first (zero download time, zero drift);
# the archive.org URLs below remain as the classic fallbacks.
SFX_LIBRARY_DIR = os.path.join(BASE_DIR, "sfx_library")
SFX_LIBRARY_MAP = {
    "energy_flare": "fx_flare_1.wav",       # electric flare on the nebula (6.8s)
    "flare_tail": "fx_flare_2.wav",         # sustained crackle tail (7.8s)
    "tick_tock": "fx_tick.wav",             # clock scene ticks (13.1s)
    "comet_whoosh": "fx_comet_whoosh.wav",  # rising whoosh on the comet (21.5s)
    "clock_hit": "fx_clock_hit.wav",        # tick + low thud on the clock (40.4s)
    "warp_whoosh": "fx_warp_whoosh.wav",    # warp/speed-line whoosh (43.4s)
    "riser": "fx_riser.wav",                # build-up before the climax (53.3s)
    "climax_impact": "fx_climax_impact.wav",# the "wake up" hit (59.5s)
    "sub_boom": "fx_sub_boom.wav",          # sub-bass boom on the logo outro (61.8s)
}


def _synthesize_legacy_sfx(name):
    """BROKEN-URL FIX: the old archive.org links 404/503 — these two classics
    are now generated locally (deterministic), so the option always works,
    even with zero internet. Returns a wav path or None."""
    sr = 44100
    path = os.path.join(DEFAULT_DIR, f"meme_{name}_synth.wav")
    if os.path.exists(path):
        return path
    import wave as _w
    rng = np.random.default_rng(7)
    if name == "record_scratch":
        n = int(sr * 0.5)
        t = np.arange(n) / sr
        noise = rng.uniform(-1, 1, n)
        # two fast "scrape" passes with pitch wobble = the scratch feel
        wobble = 0.5 + 0.5 * np.sin(2 * np.pi * 14 * t)
        env = np.exp(-3.2 * t) * (0.35 + 0.65 * wobble)
        sig = noise * env
    elif name == "bass_drop":
        n = int(sr * 0.9)
        t = np.arange(n) / sr
        # sub sine sweep 62 -> 31 Hz with a hard attack
        f = 31 + 31 * np.exp(-4 * t)
        sub = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-2.6 * t)
        # lowpassed noise transient at the drop
        noise = rng.uniform(-1, 1, n)
        k = np.ones(31) / 31
        noise_lp = np.convolve(noise, k, mode="same") * np.exp(-9 * t) * 0.5
        sig = sub * 0.9 + noise_lp
    else:
        return None
    sig = sig / max(1e-6, np.abs(sig).max()) * 0.9
    with _w.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


def download_free_meme_sfx(sfx_name):
    name_clean = str(sfx_name).lower().replace(" ", "_")
    # 1) local reference pack (instant, exact sound)
    if name_clean in SFX_LIBRARY_MAP:
        local_pack = os.path.join(SFX_LIBRARY_DIR, SFX_LIBRARY_MAP[name_clean])
        if os.path.exists(local_pack):
            return local_pack
    local_path = os.path.join(DEFAULT_DIR, f"meme_{name_clean}.mp3")
    if os.path.exists(local_path):
        return local_path
        
    # anime_wow's archive.org link is dead (404) and a voice sample can't be
    # synthesized — the option was removed from the UI. The two remaining
    # classics are SELF-HEALING: URL first, local synthesis as the fallback,
    # so the option can never be silently broken again.
    urls = {
        "record_scratch": "https://archive.org/download/RecordScratchSoundEffectPlotTwistSound/Record%20Scratch%20Sound%20Effect%21%20%28%20Plot%20Twist%20Sound%29.mp3",
        "bass_drop": "https://archive.org/download/bass-drop_202108/bass-drop.mp3"
    }

    url = urls.get(name_clean)
    if url:
        try:
            print(f"Downloading viral meme sound effect: '{sfx_name.upper()}'...")
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return local_path
            print(f"Meme SFX download failed (HTTP {r.status_code}) — using local synthesis.")
        except Exception as e:
            print(f"Meme SFX download failed: {e} — using local synthesis.")
    synth = _synthesize_legacy_sfx(name_clean)
    if synth:
        return synth
    return None

# --- PROCEDURAL EDITORIAL GRAPHIC CARD GENERATOR ---
def make_solid_color_card_clip(duration, color_tuple=(30, 58, 138)):
    width, height = 720, 1280
    base_img = Image.new("RGB", (width, height), color=color_tuple)
    draw = ImageDraw.Draw(base_img, "RGBA")
    
    cx, cy = 360, 640
    for r in range(10, 600, 30):
        opacity = int(max(0, 45 - (r / 600) * 45))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, opacity), width=2)
        
    grid_color = (255, 255, 255, 8)
    for gx in range(1, 6):
        draw.line([(gx * 120, 0), (gx * 120, height)], fill=grid_color, width=1)
    for gy in range(1, 10):
        draw.line([(0, gy * 128), (width, gy * 128)], fill=grid_color, width=1)
        
    draw.rectangle([18, 18, width-18, height-18], outline=(255, 255, 255, 25), width=2)
    
    img_array = np.array(base_img)
    return ImageClip(img_array).with_duration(duration)

# --- CINEMATIC FILM GRAIN AND SCENIC OVERLAY MAKER ---
def make_cinematic_overlay(duration):
    width, height = 720, 1280
    np.random.seed(42)
    noise_frames = []
    for _ in range(8):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        for _ in range(random.randint(4, 9)):
            rx = random.randint(30, width-30)
            ry = random.randint(30, height-30)
            rs = random.randint(1, 3)
            draw.ellipse([rx-rs, ry-rs, rx+rs, ry+rs], fill=(255, 255, 255, random.randint(25, 45)))
        for _ in range(random.randint(1, 3)):
            x_line = random.randint(50, width-50)
            len_line = random.randint(120, 450)
            y_start = random.randint(100, height-500)
            draw.line([(x_line, y_start), (x_line + random.randint(-1, 1), y_start + len_line)], fill=(255, 255, 255, random.randint(35, 75)), width=1)
        noise_frames.append(np.array(img))
    def make_frame(t):
        frame_idx = int((t * 24) % 8)
        return noise_frames[frame_idx]
    return VideoClip(make_frame, duration=duration)

# --- KEN BURNS SLIDESHOW GENERATOR WITH SMOOTH CONSTANT ZOOM ---
def make_ken_burns_clip(img_path, duration):
    base_img = Image.open(img_path).convert("RGB")
    bw, bh = base_img.size
    target_w, target_h = 720, 1280
    
    img_aspect = bw / bh
    target_aspect = target_w / target_h
    
    if img_aspect > target_aspect:
        crop_w = int(bh * target_aspect)
        left = (bw - crop_w) // 2
        base_img_cropped = base_img.crop((left, 0, left + crop_w, bh))
    else:
        crop_h = int(bw / target_aspect)
        top = (bh - crop_h) // 2
        base_img_cropped = base_img.crop((0, top, bw, top + crop_h))
        
    cw, ch = base_img_cropped.size

    def make_frame(t):
        scale = 1.0 + 0.15 * (t / duration)
        vw, vh = cw / scale, ch / scale
        left, top = (cw - vw) / 2, (ch - vh) / 2
        cropped = base_img_cropped.crop((left, top, left + vw, top + vh))
        
        arr = np.array(cropped.resize((target_w, target_h), Image.Resampling.LANCZOS))
        # Apply premium dark grade (mid-gray darkening + contrast + saturation comp)
        if se is not None:
            try:
                return se.grade_frame(arr)
            except Exception:
                pass
        return arr
        
    return VideoClip(make_frame, duration=duration)

# --- CINEMATIC RADIAL VIGNETTE OVERLAY (EYE FUNNEL MASK) ---
def make_vignette_overlay(duration):
    width, height = 720, 1280
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    max_r = int(np.sqrt(cx**2 + cy**2))
    
    # Draw concentric black circles with increasing opacity towards the edges
    for r in range(max_r, 0, -8):
        opacity = int((r / max_r) ** 2.2 * 170)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, opacity), width=8)
        
    img_arr = np.array(img)
    return ImageClip(img_arr).with_duration(duration)

# --- DYNAMIC LIGHT LEAK TRANSITION FLASHES ---
def make_light_leak_flash(start_t, duration=0.25):
    width, height = 720, 1280
    # Generate transparent overlay with massive soft glowing warm orange center
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    draw.ellipse([cx - 400, cy - 400, cx + 400, cy + 400], fill=(255, 130, 0, 95))
    img_arr = np.array(img)
    
    clip = ImageClip(img_arr).with_start(start_t).with_duration(duration)
    # Ramps opacity up and down smoothly during the flash (cross-version safe, no .fl)
    def opacity_fn(gf, t):
        f = np.sin(t * (np.pi / duration)) if 0 <= t <= duration else 0.0
        return gf(t) * f
    if se is not None:
        try:
            return se.clip_fl(clip, opacity_fn)
        except Exception:
            pass
    try:
        return clip.transform(opacity_fn)
    except Exception:
        return clip

# --- GENERATE CONTINUOUS DEEP SUB-BASS ATMOSPHERIC HUM (STANDARD LIBRARY WAV GENERATOR) ---
# ==============================================================================
# PIECE 11 — AUTO THUMBNAIL GENERATOR (the "same pattern on upload" piece).
# Frame @1s + locked channel styling (dark top gradient + hook text in the
# channel font/accent) = a 1280x720 thumbnail that looks like every other
# thumbnail on the channel. "The template is a set of visual rules."
# ==============================================================================
def _finish_thumbnail(frame_path, out_path, hook_text, accent_rgb, text_y=60, bar="left"):
    """PIL body of the thumbnail (kept separate so the frame file has a
    guaranteed try/finally cleanup in generate_thumbnail)."""
    img = Image.open(frame_path).convert("RGBA")
    # YouTube Shorts Thumbnails must be vertical 720x1280 (not 1280x720)
    img = img.resize((720, 1280))
    # 1) darken the top band so the hook text reads (locked rule)
    dark = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dark)
    Wd, Hd = img.size
    for y in range(min(540, Hd)):
        dd.line([(0, y), (Wd, y)], fill=(0, 0, 0, int(195 * (1 - y / 540))))
    img = Image.alpha_composite(img, dark)
    d = ImageDraw.Draw(img, "RGBA")
    # 2) hook text: first 2-3 meaningful words, UPPERCASE, channel font + accent
    words = re.sub(r"\[.*?\]", "", str(hook_text or "")).split()[:3]
    words = [w for w in words if len(w) > 2] or (str(hook_text or "WATCH THIS").split()[:2])
    txt = " ".join(words).upper() or "WATCH THIS"
    # 3) size-to-fit (max width 1160), channel accent color
    size = 110
    font = None
    while size > 40:
        font = None
        # Devanagari-safe: Hindi/other scripts auto-route to a unicode font
        fp = se.get_font_path_for_text(txt, size, bold=True) if se else None
        try:
            font = ImageFont.truetype(fp, size) if fp else ImageFont.load_default(size=size)
        except Exception:
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), txt, font=font, stroke_width=6)
        if bbox[2] - bbox[0] <= 1160:
            break
        size -= 4
    tw = d.textbbox((0, 0), txt, font=font, stroke_width=6)
    tw_w = tw[2] - tw[0]
    d.text(((1280 - tw_w) // 2 - tw[0], text_y - tw[1]), txt, font=font,
           fill=tuple(accent_rgb) + (255,), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    # 4) signature mark (position varies per variant; A/B learns what clicks)
    if bar == "left":
        d.rectangle([(60, 40), (68, 120)], fill=tuple(accent_rgb) + (255,))
    elif bar == "right":
        d.rectangle([(1212, 40), (1220, 120)], fill=tuple(accent_rgb) + (255,))
    img.convert("RGB").save(out_path, quality=90)
    return out_path


# 3 variants so the channel can A/B what its audience clicks:
#   frame time / text y / signature bar position
THUMB_VARIANTS = {
    0: {"frame_t": 1.0, "text_y": 60,  "bar": "left"},
    1: {"frame_t": 2.5, "text_y": 95,  "bar": "right"},
    2: {"frame_t": 0.5, "text_y": 125, "bar": "none"},
}


# ==============================================================================
# PERFORMANCE LOG — the template that LEARNS.
# The user pastes CTR/views from YouTube after each upload; the log remembers
# which thumbnail variant won, and the next render's PRIMARY thumb defaults to
# the best-performing variant. (No API needed — 20 seconds of manual data
# entry beats a broken OAuth chain.)
# ==============================================================================
PERFORMANCE_LOG_PATH = os.path.join(BASE_DIR, "performance_log.json")


def log_performance(video_basename, title, ctr=None, views=None, avg_retention=None, thumb_variant=0):
    log = {}
    if os.path.exists(PERFORMANCE_LOG_PATH):
        try:
            log = json.load(open(PERFORMANCE_LOG_PATH, "r", encoding="utf-8"))
        except Exception:
            log = {}
    log[video_basename] = {
        "title": str(title)[:120],
        "ctr": ctr,
        "views": views,
        "avg_retention": avg_retention,
        "thumb_variant": int(thumb_variant),
        "logged": time.strftime("%Y-%m-%d"),
    }
    with open(PERFORMANCE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    return log


def read_performance_log():
    try:
        return json.load(open(PERFORMANCE_LOG_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}


def best_thumb_variant():
    """Variant with the best logged CTR (0 if nothing logged yet)."""
    best_v, best_ctr = 0, -1.0
    for entry in read_performance_log().values():
        try:
            c = float(entry.get("ctr") or 0)
        except Exception:
            continue
        if c > best_ctr:
            best_ctr, best_v = c, int(entry.get("thumb_variant", 0))
    return best_v if best_ctr > 0 else 0


def generate_thumbnail(video_path, hook_text, accent_rgb=(255, 215, 0), out_path=None, variant=0):
    return None  # User requested manual thumbnails via Creator Hub Prompt
    try:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        vnum = int(variant) % 3
        var = THUMB_VARIANTS[vnum]
        if out_path is None:
            base = video_path.rsplit(".", 1)[0]
            # variant 0 keeps the classic name; 1/2 get numbered sidecars
            out_path = base + ("_thumbnail.jpg" if vnum == 0 else f"_thumbnail_{vnum + 1}.jpg")
        frame_path = out_path.rsplit(".", 1)[0] + "_frame_tmp.jpg"
        subprocess.run(
            [ff, "-y", "-loglevel", "error", "-ss", f"{var['frame_t']:.1f}", "-i", video_path,
             "-frames:v", "1", "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
             frame_path], check=True, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            return _finish_thumbnail(frame_path, out_path, hook_text, accent_rgb,
                                     text_y=var["text_y"], bar=var["bar"])
        finally:
            _force_delete(frame_path)   # B5: temp frame removed even on crash
    except Exception as e:
        print(f"[Thumbnail] generation failed: {e}")
        return None


def generate_sub_bass_wav(path, duration, frequency=40, sample_rate=44100):
    import wave
    import struct
    
    num_samples = int(duration * sample_rate)
    with wave.open(path, 'wb') as wav:
        # Stereo (2 channels), 16-bit (2 bytes per sample), sample_rate
        wav.setparams((2, 2, sample_rate, num_samples, 'NONE', 'not compressed'))
        
        frames = []
        for i in range(num_samples):
            t = float(i) / sample_rate
            val = int(32767 * np.sin(2 * np.pi * frequency * t))
            frames.append(struct.pack('<hh', val, val))
            
        wav.writeframes(b''.join(frames))

# ==============================================================================
# PIECE 13 — SIGNATURE STINGER (audio identity)
# A fixed 0.5s stinger is mixed into EVERY video at 0.0s, same volume, same
# waveform. Pro channels are recognized by SOUND before the first frame
# resolves — this is the ear's version of the character bible (locked face).
# Deterministic (fixed seed) = identical on every render, every machine.
# ==============================================================================
def generate_signature_stinger():
    path = os.path.join(DEFAULT_DIR, "signature_stinger.wav")
    if os.path.exists(path):
        return path
    sr = 44100
    dur = 0.5
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(20260828)
    # 1) deep impact sweep 90 -> 38 Hz (the "thud")
    f_imp = 38 + 52 * np.exp(-9 * t)
    imp = np.sin(2 * np.pi * np.cumsum(f_imp) / sr) * np.exp(-6.0 * t)
    # 2) short bright shimmer 1800 -> 2600 Hz (the "ping", quiet)
    f_sh = 1800 + 800 * (t / dur)
    sh = np.sin(2 * np.pi * f_sh * t) * np.exp(-18 * t) * 0.12
    # 3) 2ms attack click (gives the intro a crisp start)
    click = rng.uniform(-1, 1, n) * np.exp(-t * 900) * 0.35
    sig = imp * 0.85 + sh + click
    sig = sig / max(1e-6, np.abs(sig).max()) * 0.9
    import wave as _w
    with _w.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


# --- DYNAMIC MICRO-MEME STICKER OVERLAY ---
def make_micro_meme_sticker(meme_type):
    width, height = 440, 110
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded dark background with gold warning border
    draw.rounded_rectangle(
        [(10, 10), (width - 10, height - 10)],
        radius=20,
        fill=(15, 23, 42, 255), # solid dark
        outline=(255, 215, 0, 255), # Gold
        width=3
    )
    
    # Clean up name for text rendering (NO EMOJI — Windows renders them as broken boxes)
    text = meme_type.upper().replace("_", " ")
    from PIL import ImageFont
    try:
        font = ImageFont.load_default(size=24)
    except TypeError:
        font = ImageFont.load_default()

    text_w = len(text) * 12
    text_x = (width - text_w) // 2
    text_y = (height - 34) // 2
    
    draw.text((text_x, text_y), text, fill=(255, 215, 0, 255), font=font)
    return img

# --- PROCEDURAL HIGH-DENSITY SAVE TRIGGER CARD ---
def make_save_trigger_card(points_text, duration):
    width, height = 580, 480
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Rounded dark box with golden border
    draw.rounded_rectangle(
        [(15, 15), (width - 15, height - 15)],
        radius=30,
        fill=(15, 23, 42, 255), # solid dark
        outline=(255, 215, 0, 255), # Gold
        width=5
    )
    
    # Title
    from PIL import ImageFont
    try: font_title = ImageFont.load_default(size=28)
    except TypeError: font_title = ImageFont.load_default()
    
    draw.text((45, 45), "SAVE TO LOCK MOMENTUM", fill=(255, 215, 0, 255), font=font_title)
    
    # Parse points
    points = [p.strip() for p in points_text.split('|')]
    try: font_body = ImageFont.load_default(size=22)
    except TypeError: font_body = ImageFont.load_default()
    
    y_offset = 120
    for idx, pt in enumerate(points[:3]):
        # Bullet point text
        draw.text((50, y_offset), f"{idx+1}. {pt}", fill=(255, 255, 255, 255), font=font_body)
        y_offset += 100
        
    img_arr = np.array(img)
    return ImageClip(img_arr).with_duration(duration)

# --- DRAMATIC COGNITIVE SOUND DROP ENGINE (v2: smooth sidechain dip, not a hard gate) ---
# Old version slammed music to 8% for 0.4s — to the ear that sounds like a volume glitch
# (the #1 skip trigger). New version: smooth dip to 55% with 100ms attack / 400ms release,
# like the sidechain breathing used in elite faceless edits.
def apply_sound_drop_ducking(music_clip, drop_times):
    if not drop_times:
        return music_clip

    DIP_DEPTH = 0.45   # music swells down to 55%
    ATTACK = 0.10      # 100ms smooth down
    RELEASE = 0.40     # 400ms smooth back

    def gain_at(t):
        g = 1.0
        for dt in drop_times:
            if dt <= t < dt + ATTACK + RELEASE:
                if t < dt + ATTACK:
                    g = min(g, 1.0 - DIP_DEPTH * ((t - dt) / ATTACK))
                else:
                    g = min(g, (1.0 - DIP_DEPTH) + DIP_DEPTH * ((t - dt - ATTACK) / RELEASE))
        return g

    def volume_filter(t):
        if isinstance(t, np.ndarray):
            out = np.ones_like(t, dtype=float)
            for dt in drop_times:
                lo, hi = dt, dt + ATTACK + RELEASE
                m = (t >= lo) & (t < hi)
                if m.any():
                    tt = t[m]
                    g = np.where(
                        tt < dt + ATTACK,
                        1.0 - DIP_DEPTH * ((tt - dt) / ATTACK),
                        (1.0 - DIP_DEPTH) + DIP_DEPTH * ((tt - dt - ATTACK) / RELEASE)
                    )
                    out[m] = np.minimum(out[m], g)
            return np.expand_dims(out, axis=-1)
        return gain_at(t)

    # Ultimate Cross-Version Compatibility (supports MoviePy 1.x, MoviePy 2.x, and custom subclasses!)
    if hasattr(music_clip, "transform"):
        return music_clip.transform(lambda gf, t: gf(t) * volume_filter(t))
    elif hasattr(music_clip, "fl"):
        return music_clip.fl(lambda gf, t: gf(t) * volume_filter(t))
    else:
        orig_get_frame = music_clip.get_frame
        def new_get_frame(t):
            frames = orig_get_frame(t)
            return frames * volume_filter(t)
        music_clip.get_frame = new_get_frame
        return music_clip


# --- ENERGY ARC ENVELOPE: quiet hook -> build -> peak at reveal -> quiet loop ---
def apply_energy_arc(music_clip, peak_t=None, total_duration=30.0):
    if peak_t is None:
        peak_t = max(5.0, total_duration * 0.75)

    def arc_gain(t):
        # 0-2.5s: fade in to 40% (voice-only hook)
        # 2.5s -> peak-2s: build 40% -> 75%
        # peak-2s -> peak: push to 100%
        # peak -> peak+1.5s: crash to 40%
        # after: quiet 40% (loop tail)
        if t < 2.5:
            return 0.4 * (t / 2.5)
        build_start, build_end = 2.5, max(4.0, peak_t - 2.0)
        if t < build_end:
            k = (t - build_start) / max(0.1, build_end - build_start)
            return 0.4 + 0.35 * k
        if t < peak_t:
            k = (t - build_end) / max(0.1, peak_t - build_end)
            return 0.75 + 0.25 * k
        if t < peak_t + 1.5:
            return 1.0 - 0.6 * ((t - peak_t) / 1.5)
        return 0.4

    def volume_filter(t):
        if isinstance(t, np.ndarray):
            out = np.ones_like(t, dtype=float)
            for i, ti in enumerate(t):
                out[i] = arc_gain(float(ti))
            return np.expand_dims(out, axis=-1)
        return arc_gain(float(t))

    if hasattr(music_clip, "transform"):
        return music_clip.transform(lambda gf, t: gf(t) * volume_filter(t))
    elif hasattr(music_clip, "fl"):
        return music_clip.fl(lambda gf, t: gf(t) * volume_filter(t))
    return music_clip

# --- SPEECH CLEANER ---
def clean_script_for_speech(script_text):
    if not script_text: return ""
    clean_text = str(script_text)
    
    # 1. Remove all block headers strictly (e.g. [0-3 sec HOOK], [VALUE DELIVERY], [ENGAGEMENT CTA])
    clean_text = re.sub(r'\[[A-Z0-9\-\s]+\]', '', clean_text)
    
    # 2. Remove the PSYCHOLOGY TRIGGER header AND the instruction sentence immediately following it!
    # The previous regex was missing this, causing the AI to read the prompt instructions aloud.
    clean_text = re.sub(r'\[PSYCHOLOGY TRIGGER:[^\]]+\]\s*(.*?)(?:\n\n|\Z)', '\n\n', clean_text, flags=re.DOTALL)
    
    # 3. Remove inline tags like [MICRO_MEME: ...], [SOUND_DROP], [SAVE_TRIGGER_LIST: ...]
    clean_text = re.sub(r'\[MICRO_MEME:[^\]]+\]', '', clean_text)
    clean_text = re.sub(r'\[SOUND_DROP\]', '', clean_text)
    clean_text = re.sub(r'\[SAVE_TRIGGER_LIST:[^\]]+\]', '', clean_text)
    
    # 4. Remove bracketed text blocks (like the CTA at the end)
    clean_text = re.sub(r'\[.*?\]', '', clean_text)
    
    # 5. Clean up emoji and markdown
    lines = clean_text.split('\n')
    cleaned = []
    for line in lines:
        l = line.strip()
        if not l: continue
        if l.startswith(('-', '•')): l = l[1:].strip()
        l = l.replace('+', 'and').replace('👇', 'below').replace('🔥', 'fire').replace('📈', 'to grow').replace('🧠', 'psychology').replace('🎯', 'target')
        cleaned.append(l)
        
    return " ".join(cleaned).strip()

# --- PROACTIVE THREADED ELEVENLABS SPEECH GENERATOR ---
# VOICE PRESETS (Piece 7 — "tones"): voice_id + per-preset tone settings.
# Research consensus (2026): V3 model, stability 35%, similarity 78%,
# style exaggeration 20%, speaker boost ON = the "human tone" that V1 never had.
VOICE_PRESETS = {
    "Deep Narrator Male": {
        "voice_id": "BHr135B5EUBtaWheVj8S",          # Dan (Elite Documentary)
        "settings": {"stability": 0.25, "similarity_boost": 0.85, "style": 0.35, "speaker_boost": True},
        "speed": 0.95,
    },
    "Energetic Male": {
        "voice_id": "yl2ZDV1MzN4HbQJbMihG",          # Alex (Built for Shorts)
        "settings": {"stability": 0.35, "similarity_boost": 0.80, "style": 0.40, "speaker_boost": True},
        "speed": 1.05,
    },
    "Warm Female": {
        "voice_id": "XfNU2rGpBa01ckF309OY",          # Nichalia (Educational)
        "settings": {"stability": 0.38, "similarity_boost": 0.78, "style": 0.20, "speaker_boost": True},
        "speed": 1.0,
    },
    "Calm British Female": {
        "voice_id": "pFZP5JQG7iQjIQuC4Bku",          # Lily (Placeholder)
        "settings": {"stability": 0.42, "similarity_boost": 0.75, "style": 0.15, "speaker_boost": True},
        "speed": 0.97,
    },
}


# B2 FIX: model chain instead of one hardcoded model.
# eleven_v3 = best human tone (may need a paid tier depending on account)
# eleven_multilingual_v2 / turbo = always available, still human.
# Every fallback prints LOUDLY so you know which engine actually served the voice.
ELEVEN_MODEL_CHAIN = ["eleven_turbo_v2_5", "eleven_v3", "eleven_multilingual_v2"]


def _eleven_settings_for_model(preset, model):
    """v3 uses `speaker_boost`; v1/v2 use `use_speaker_boost` (different key)."""
    s = dict(preset["settings"])
    if model != "eleven_v3":
        s["use_speaker_boost"] = s.pop("speaker_boost", True)
    return s


def generate_elevenlabs_audio(text, api_key, output_basename="voice", voice_preset="Deep Narrator Male"):
    audio_path = os.path.join(AUDIO_DIR, f"{output_basename}.mp3")
    srt_path = os.path.join(AUDIO_DIR, f"{output_basename}.srt")

    preset = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["Deep Narrator Male"])
    voice_id = preset["voice_id"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    last_err = "unknown"
    for model in ELEVEN_MODEL_CHAIN:
        data = {
            "text": text,
            "model_id": model,
            "voice_settings": _eleven_settings_for_model(preset, model),
            "speed": preset["speed"],
        }
        try:
            r = requests.post(url, json=data, headers=headers, timeout=60)
        except Exception as e:
            last_err = str(e)
            print(f"[Voice] ElevenLabs {model} network error: {e} — trying next model...")
            continue
        if r.status_code == 200:
            if model != "eleven_v3":
                print(f"[Voice] ⚠ ElevenLabs V3 unavailable — served this voice with {model} "
                      f"(still human, slightly less emotional). Check your plan/key for V3.")
            with open(audio_path, "wb") as f_aud:
                f_aud.write(r.content)

            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            audio_clip.close()

            words = text.split()
            total_chars = sum(len(w) for w in words)
            start_time = 0.0

            with open(srt_path, "w", encoding="utf-8") as f_srt:
                for idx, w in enumerate(words):
                    w_dur = (len(w) / total_chars) * duration if total_chars > 0 else duration / len(words)
                    end_time = min(start_time + w_dur, duration)

                    def format_time(seconds):
                        hours = int(seconds // 3600)
                        minutes = int((seconds % 3600) // 60)
                        secs = int(seconds % 60)
                        millis = int((seconds % 1) * 1000)
                        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

                    f_srt.write(f"{idx+1}\n")
                    f_srt.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
                    f_srt.write(f"{w.upper()}\n\n")
                    start_time = end_time

            return audio_path, srt_path
        # 401/403/404 = key or voice problem — a different model won't help
        if r.status_code in (401, 403, 404):
            last_err = f"HTTP {r.status_code} ({r.text[:160]}) — likely key/plan/voice problem"
            break
        last_err = f"HTTP {r.status_code} ({r.text[:160]})"
        print(f"[Voice] ElevenLabs {model} failed ({r.status_code}) — trying next model...")
    print(f"[Voice] ❌ ElevenLabs unusable: {last_err}. Voice falls back to edge-tts.")
    return None, None

# --- WORD-LEVEL SRT BUILDERS (fixes edge-tts 7.x: WordBoundary events are gone,
#     replaced by SentenceBoundary events — this is why captions were missing) ---
def _write_word_srt(cues, srt_path):
    def fmt(s):
        s = max(0.0, float(s))
        h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60); ms = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (s, e, t) in enumerate(cues):
            f.write(f"{i+1}\n{fmt(s)} --> {fmt(e)}\n{t}\n\n")


def _sentence_to_word_cues(sentence_cues):
    """Spread each SentenceBoundary window (100ns ticks) over its words,
    proportional to word length — reconstructs word-level timing."""
    cues = []
    for off, dur, txt in sentence_cues:
        words = str(txt or "").split()
        if not words:
            continue
        t0 = off / 1e7
        t1 = t0 + (dur / 1e7 if dur else 0.4 * len(words))
        span = max(t1 - t0, 0.12 * len(words))
        total_chars = sum(len(w) + 1 for w in words)
        tcur = t0
        for w in words:
            wspan = span * (len(w) + 1) / total_chars
            cues.append((tcur, tcur + wspan, w))
            tcur += wspan
    return cues


# --- NATIVE PYTHON TTS GENERATOR ---
def generate_tts_audio(text, voice_name="en-GB-RyanNeural", output_basename="voice", eleven_key=None, voice_preset="Deep Narrator Male"):
    if eleven_key and eleven_key.strip():
        print(f"Calling premium ElevenLabs voiceover (V3, preset: {voice_preset})...")
        aud_path, s_path = generate_elevenlabs_audio(text, eleven_key, output_basename, voice_preset=voice_preset)
        if aud_path and os.path.exists(aud_path):
            return aud_path, s_path
        print("[Voice] ⚠ ElevenLabs failed for the whole model chain — using edge-tts fallback (robotic voice, no V3 tone).")

    audio_path = os.path.join(AUDIO_DIR, f"{output_basename}.mp3")
    srt_path = os.path.join(AUDIO_DIR, f"{output_basename}.srt")

    # v2.5.2 WINDOWS BULLETPROOF TTS: Spawn a completely isolated Python process
    # to run the async edge-tts code. This guarantees 100% immunity against Streamlit's
    # Tornado event-loop thread crashes, and completely solves the identical gTTS fallback bug.
    code = f"""
import asyncio
import edge_tts
import sys
import json

async def main():
    try:
        communicate = edge_tts.Communicate({repr(text)}, {repr(voice_name)}, boundary="WordBoundary")
    except TypeError:
        communicate = edge_tts.Communicate({repr(text)}, {repr(voice_name)})
    
    submaker = None
    try:
        submaker = edge_tts.SubMaker()
    except Exception:
        pass
        
    sentences = []
    with open({repr(audio_path)}, "wb") as f_aud:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f_aud.write(chunk["data"])
            elif chunk["type"] == "WordBoundary" and submaker is not None:
                submaker.feed(chunk)
            elif chunk["type"] == "SentenceBoundary":
                sentences.append((chunk.get("offset", 0), chunk.get("duration", 0), chunk.get("text", "")))
                
    word_srt = submaker.get_srt() if submaker else ""
    with open({repr(srt_path + ".json")}, "w", encoding="utf-8") as f_out:
        json.dump({{"word_srt": word_srt, "sentences": sentences}}, f_out)

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass
try:
    asyncio.run(main())
except Exception as e:
    print(repr(e), file=sys.stderr)
    sys.exit(1)
"""

    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Subprocess edge-tts crashed: {res.stderr}")
            
        import json
        with open(srt_path + ".json", "r", encoding="utf-8") as f:
            boundary_data = json.load(f)
            
        # Clean up the temp JSON
        try:
            os.remove(srt_path + ".json")
        except:
            pass

        # --- Build the word-level SRT: WordBoundary -> SentenceBoundary -> even-spread fallback ---
        if boundary_data.get("word_srt", "").strip():
            with open(srt_path, "w", encoding="utf-8") as f_sub:
                f_sub.write(boundary_data["word_srt"])
        elif boundary_data.get("sentences"):
            _write_word_srt(_sentence_to_word_cues(boundary_data["sentences"]), srt_path)
        else:
            try:
                a = AudioFileClip(audio_path)
                total = a.duration
                a.close()
                words = text.split()
                total_chars = sum(len(w) + 1 for w in words) or 1
                tcur = 0.0
                cues = []
                for w in words:
                    wspan = total * (len(w) + 1) / total_chars
                    cues.append((tcur, tcur + wspan, w))
                    tcur += wspan
                _write_word_srt(cues, srt_path)
            except Exception:
                open(srt_path, "w").close()
        return audio_path, srt_path
    except Exception as e:
        print(f"Native edge-tts failed: {e}. Falling back to gTTS.")
        try:
            from gtts import gTTS
            # Fix gTTS fallback playing the exact same english female voice for every option
            lang_code = 'hi' if 'hi-IN' in voice_name else 'en'
            gTTS(text=text, lang=lang_code).save(audio_path)
            # B4 FIX (P0): NEVER return srt=None. parse_vtt(None)=[] silently
            # killed the ENTIRE caption/beat/SFX/broll-sync layer. gTTS gives
            # no word timings, so build a char-weighted word-level SRT — the
            # whole visual layer now always renders, at worst slightly soft sync.
            try:
                _a = AudioFileClip(audio_path)
                _total = _a.duration
                _a.close()
            except Exception:
                _total = 0.30 * max(1, len(text.split()))
            _words = text.split() or ["..."]
            _tot_chars = sum(len(w) + 1 for w in _words) or 1
            _tcur, _cues = 0.0, []
            for _w in _words:
                _ws = _total * (len(_w) + 1) / _tot_chars
                _cues.append((_tcur, _tcur + _ws, _w))
                _tcur += _ws
            _write_word_srt(_cues, srt_path)
            print("[Voice] ⚠ gTTS fallback active (Google robotic voice) — captions use estimated word timing.")
            return audio_path, srt_path
        except Exception as ge:
            print(f"gTTS fallback failed: {ge}")
            return None, None

# --- WEB VTT / SRT PARSER ---
def parse_vtt(vtt_path):
    if not vtt_path or not os.path.exists(vtt_path): return []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        matches = re.findall(r'(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*\n((?:(?!\n\n).)*)', f.read(), re.DOTALL)
    
    def time_to_sec(t_str):
        parts = t_str.replace(',', '.').split(':')
        return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])

    subtitles = [{'start': time_to_sec(s), 'end': time_to_sec(e), 'text': txt.strip().replace('\n', ' ')} for s, e, txt in matches if txt.strip()]
    for i in range(len(subtitles) - 1):
        if subtitles[i]['end'] > subtitles[i+1]['start']: subtitles[i]['end'] = subtitles[i+1]['start']
    return subtitles

# --- MATHEMATICALLY PERFECT VERTICAL SCALER, CROPPER & COLOR UNIFIER ---
def _subject_anchor_x1(clip, w, h, new_w):
    """PIECE 6 — SUBJECT-ANCHOR CROP: instead of dead-center (which slices
    faces/objects), find the highest visual-energy column band (detail +
    saturation = where the subject is) and anchor the 9:16 crop around it.
    Falls back to center on any failure."""
    try:
        dur = clip.duration
        cols = 12
        profile = np.zeros(cols, dtype=float)
        n_samples = 0
        for frac in (0.1, 0.5, 0.9):
            st = min(max(dur * frac, 0.01), dur - 0.01)
            try:
                f = clip.get_frame(st)
            except Exception:
                continue
            small = f[:max(h // 8, 16), :max(w // 8, 16)]
            col_lum = 0.2126 * small[..., 0].astype(float) + 0.7152 * small[..., 1].astype(float) + 0.0722 * small[..., 2].astype(float)
            col_var = col_lum.std(axis=0)
            mx = small.max(axis=0).astype(float)
            mn = small.min(axis=0).astype(float)
            sat = ((mx - mn) / np.maximum(mx, 1e-6)).mean(axis=0)
            profile += col_var + sat
            n_samples += 1
        if n_samples == 0 or profile.sum() <= 0:
            return (w - new_w) // 2
        profile = profile / profile.sum()
        best = int(np.argmax(profile))
        col_w = w / cols
        center_anchor = (best + 0.5) * col_w
        ideal = int(center_anchor - new_w / 2)
        # clamp: never more than 25% of the crop width off-center
        max_off = int(new_w * 0.25)
        ideal = max((w - new_w) // 2 - max_off, min(ideal, (w - new_w) // 2 + max_off))
        return max(0, min(ideal, w - new_w))
    except Exception:
        return (w - new_w) // 2


def make_vertical_clip(clip, target_w=720, target_h=1280, dark_blend=False, exposure_gain=1.0, cosmic=False):
    w, h = clip.size
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        new_w = int(h * target_aspect)
        x1 = _subject_anchor_x1(clip, w, h, new_w)
        cropped_clip = clip.cropped(x1=x1, y1=0, width=new_w, height=h)
    else:
        new_h = int(w / target_aspect)
        cropped_clip = clip.cropped(x1=0, y1=(h - new_h) // 2, width=w, height=new_h)
        
    resized_clip = cropped_clip.resized(width=target_w, height=target_h)

    # --- COSMIC GRADE (GOONINGGNG filter: sat crush + 22/255 brightness
    #     ceiling — any footage comes through as the same dark graphite) ---
    if cosmic and se is not None:
        try:
            return se.clip_fl(resized_clip, lambda gf, t: se.grade_frame_cosmic(gf(t)))
        except Exception as e:
            print(f"[Grade] cosmic grade failed ({e}); using premium grade")

    # --- PREMIUM DARK GRADE (cross-version safe) + PRO PASS 5 primary
    #     correction (exposure match so every clip sits at the same level) ---
    if se is not None:
        grade_fn = se.grade_clip_dark(0.72) if dark_blend else se.grade_frame
        try:
            if exposure_gain != 1.0:
                def _graded(gf, t):
                    f = gf(t)
                    f = np.clip(f.astype(float) * exposure_gain, 0, 255).astype('uint8')
                    return grade_fn(f)
                return se.clip_fl(resized_clip, _graded)
            return se.clip_fl(resized_clip, lambda gf, t: grade_fn(gf(t)))
        except Exception as e:
            print(f"[Grade] transform failed ({e}); returning ungraded clip")
    return resized_clip

# --- DYNAMIC WORD-BY-WORD CHOPPER ---
def split_subtitles_into_words(subtitles, words_per_clip=1):
    word_subs = []
    for sub in subtitles:
        text = sub['text'].strip()
        words = text.split()
        if not words:
            continue
        
        total_chars = sum(len(w) for w in words)
        start_time = sub['start']
        total_duration = sub['end'] - sub['start']
        
        i = 0
        while i < len(words):
            group = words[i:i+words_per_clip]
            group_text = " ".join(group)
            group_chars = sum(len(w) for w in group)
            
            if total_chars > 0:
                group_dur = (group_chars / total_chars) * total_duration
            else:
                group_dur = total_duration / (len(words) / words_per_clip)
                
            group_start = start_time
            group_end = start_time + group_dur
            
            if group_end > sub['end']:
                group_end = sub['end']
                
            if group_dur > 0.02:
                word_subs.append({
                    'start': group_start,
                    'end': group_end,
                    'text': group_text.upper()
                })
            
            start_time = group_end
            i += words_per_clip
            
    return word_subs

# --- PROCEDURAL HIGH-QUALITY CLICK/POP SOUND GENERATOR ---
def generate_synthetic_pop_sound(duration=0.08, frequency=650):
    sfx_path = os.path.join(AUDIO_DIR, "pop_sfx.wav")
    if os.path.exists(sfx_path):
        return sfx_path
        
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    decay = np.exp(-32 * t)
    freq_sweep = frequency * np.exp(-12 * t)
    wave = np.sin(2 * np.pi * freq_sweep * t) * decay
    
    audio_data = (wave * 32767).astype(np.int16)
    
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
        
    return sfx_path

# --- PROCEDURAL CINEMATIC WHOOSH SOUND GENERATOR (TRANSITIONS) ---
def generate_synthetic_whoosh_sound(duration=0.45, start_freq=150, end_freq=1100):
    sfx_path = os.path.join(AUDIO_DIR, "whoosh_sfx.wav")
    if os.path.exists(sfx_path):
        return sfx_path
        
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    freq = start_freq + (end_freq - start_freq) * (t / duration) ** 1.5
    sine_wave = np.sin(2 * np.pi * freq * t)
    
    envelope = np.sin(np.pi * (t / duration)) ** 2
    np.random.seed(123)
    noise = np.random.uniform(-0.15, 0.15, len(t))
    
    wave = (sine_wave * 0.70 + noise * 0.30) * envelope
    audio_data = (wave * 32767).astype(np.int16)
    
    import wave as wave_module
    with wave_module.open(sfx_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
        
    return sfx_path

# --- RANGE-SAFE SFX CLIP (precomputes the whole SFX into memory — completely
#     avoids a MoviePy 2.x FFmpegAudioReader bug where chunked reads inside a
#     short clip's window crash with a confusing "t=1.00-1.00" boolean-mask error) ---
def make_safe_sfx_clip(path, start_t, total_duration, volume=0.3):
    # Read the WAV directly with the stdlib wave module — 100% bypasses the
    # MoviePy 2.x FFmpegAudioReader chunk-split bug on short files.
    import wave as _wavemod
    samples = None
    sr, nch = 44100, 2
    try:
        with _wavemod.open(path, "rb") as _wf:
            nch = _wf.getnchannels()
            sr = _wf.getframerate()
            raw = _wf.readframes(_wf.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768.0
        samples = samples.reshape(-1, nch)
    except Exception:
        # Not a WAV (e.g. meme MP3) — fall back to MoviePy soundarray
        try:
            base = AudioFileClip(path)
            sr = base.fps if isinstance(base.fps, (int, float)) else 44100
            nch = base.nchannels
            samples = base.to_soundarray(fps=sr, quantize=False)
            try:
                base.close()
            except Exception:
                pass
        except Exception as e:
            print(f"[SFX] Could not load {os.path.basename(path)}: {e} — using silent clip")
            samples = np.zeros((int(sr), nch), dtype=float)
    n_samples = max(1, len(samples))

    def ff(t):
        tarr = np.atleast_1d(np.asarray(t, dtype=float))
        local = tarr - start_t
        out = np.zeros((len(tarr), nch), dtype=float)
        idx = np.round(local * sr).astype(int)
        m = (local >= 0) & (local < n_samples / sr)
        if m.any():
            out[m] = samples[np.clip(idx[m], 0, n_samples - 1)]
        return out * volume

    return AudioClip(ff, duration=total_duration, fps=sr)


# --- CINEMATIC VISUAL PROGRESS BAR OVERLAY ---
def make_progress_bar_clip(duration, width=720, height=1280, bar_height=10, bar_color=(255, 45, 85)):
    def make_frame(t):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        
        pct = min(t / duration, 1.0)
        progress_w = int(pct * width)
        
        if progress_w > 0:
            draw.rectangle(
                [0, height - bar_height, progress_w, height], 
                fill=(bar_color[0], bar_color[1], bar_color[2], 235)
            )
            if progress_w > 5:
                draw.rectangle(
                    [0, height - bar_height - 2, progress_w, height - bar_height], 
                    fill=(bar_color[0], bar_color[1], bar_color[2], 120)
                )
        return np.array(img)
    return VideoClip(make_frame, duration=duration)

# --- UPGRADED CAPTIONS GENERATOR (ADHD POWER WORDS + SEMANTIC COLOUR CODE + SFX TRIGGERS) ---
def build_subtitle_and_sfx_clips(subtitles, target_w=720, font_size=55, color='yellow', caption_style='standard', total_duration=60.0, accent_rgb=(255, 215, 0), sfx_level=1.0):
    display_subs = subtitles
    actual_font_size = font_size
    caption_theme = str(caption_style).lower()
    
    is_word_pop = "hormozi" in caption_theme or "cyberpunk" in caption_theme or "word_pop" in caption_theme
    is_cinematic = "cinematic" in caption_theme
    is_typewriter = "typewriter" in caption_theme

    if is_typewriter:
        # User request: "WORDS PLACING WRONG, didnot edit it can be edited more professionally"
        # 3 words is too chunky and wraps weirdly. 1-2 words looks much more professional and dynamic.
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=1)
        actual_font_size = int(font_size * 0.90)  # Larger, more legible
    elif is_cinematic:
        # Reference #3 style: sentence-level phrases (3 words), no spring bounce,
        # calm gold/white — the narration stays the star
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=3)
        actual_font_size = int(font_size * 1.05)
    elif is_word_pop:
        display_subs = split_subtitles_into_words(subtitles, words_per_clip=1)
        actual_font_size = int(font_size * 0.95) # Compact fitting

    # --- ROBUST FONT RESOLUTION (bundled repo fonts first — works on ANY OS) ---
    if se is not None:
        font_name = se.get_font_path(actual_font_size, bold=True) or se.get_font_path(actual_font_size, bold=False)
    else:
        font_name = None
    if not font_name:
        font_name = "DejaVu Sans"
    # Non-Latin (Hindi/Devanagari): the PIL render path handles it, but the
    # TextClip fallback must also get a unicode font or it renders tofu boxes
    if se is not None and display_subs and se.text_needs_unicode_font(display_subs[0]["text"]):
        font_name = se.get_font_path_for_text(display_subs[0]["text"], actual_font_size, bold=True) or "DejaVu Sans"

    text_clips = []
    sfx_clips = []
    pop_sfx_path = generate_synthetic_pop_sound()

    # POWER WORDS — emphasis via COLOR + SIZE only (no emoji: Windows renders them as broken boxes)
    POWER_WORDS = {
        "money", "cash", "wealth", "rich", "billionaire", "billionaires",
        "fail", "mistake", "mistakes", "wrong", "destroy", "destroying",
        "secret", "secrets", "hidden", "truth", "bizarre",
        "top", "elite", "success", "grow", "growth",
        "brain", "neuroscientist", "psychology", "mind",
        "focus", "goal", "goals",
        "shock", "shocked", "shocking",
        "stop", "danger", "warn", "warning",
        "willpower", "discipline", "unstoppable", "relentless",
        "fire", "hot", "burn"
    }
    # GAP-FIX: SEMANTIC COLOUR CODE — warnings turn RED, gains turn GREEN, numbers take the ACCENT
    WARN_WORDS = {
        "wrong", "mistake", "mistakes", "lie", "lies", "stop", "never", "danger", "dangerous",
        "fail", "fails", "failing", "failed", "kill", "kills", "killing", "lose", "loses",
        "trapped", "trap", "traps", "scam", "bad", "poison", "debt", "poor", "lazy", "weak",
        "broken", "dead", "zero", "shut", "waste", "wasting", "stuck", "overthinking", "overload"
    }
    GAIN_WORDS = {
        "free", "double", "gains", "gain", "elite", "focus", "focused", "success", "grow",
        "growth", "wealth", "rich", "win", "wins", "fast", "faster", "instant", "unlock",
        "unlocking", "secret", "secrets", "truth", "power", "control", "momentum", "boost",
        "level", "levels", "proof", "result", "results", "simple", "easy"
    }
    accent_hex = "#%02X%02X%02X" % tuple(accent_rgb)

    tick_vol = float(db_settings.get_setting("tick_volume", 0.18)) * sfx_level
    power_tick_budget = 3   # v3: max 3 pop-ticks per video (SFX spam = skip trigger)
    
    for s in display_subs:
        duration = s['end'] - s['start']
        if duration <= 0.05: continue
        
        txt = s['text']
        clean_w = re.sub(r'[^\w]', '', txt.lower())
        
        word_color = color
        word_size = actual_font_size
        stroke_color = "black"
        stroke_width = 3   # PRO STANDARD: 2-4px outline (piece 3 caption lock)
        is_power = False

        if is_typewriter:
            word_color, stroke_width = "white", 2
        elif "cyberpunk" in caption_theme:
            word_color = "#00FFFF"
            if re.search(r"\d", txt) or "%" in txt:
                word_color, word_size, is_power = accent_hex, int(actual_font_size * 1.15), True
            elif clean_w in WARN_WORDS:
                word_color, is_power = "#FF4D4D", True
            elif clean_w in GAIN_WORDS:
                word_color, word_size, is_power = "#00E676", int(actual_font_size * 1.12), True
        elif "minimalist" in caption_theme:
            word_color, stroke_width = "#FFFFFF", 2
            if re.search(r"\d", txt) or "%" in txt:
                word_color, word_size, is_power = accent_hex, int(actual_font_size * 1.15), True
            elif clean_w in WARN_WORDS:
                word_color, is_power = "#FF4D4D", True
            elif clean_w in GAIN_WORDS or clean_w in POWER_WORDS:
                word_color, word_size, is_power = "#00E676", int(actual_font_size * 1.10), True
        else:
            if is_cinematic:
                # Cinematic: white base, GOLD for numbers/gains, red only for warnings
                if re.search(r"\d", txt) or "%" in txt:
                    word_color, word_size, is_power = "#D4AF37", int(actual_font_size * 1.12), True
                elif clean_w in WARN_WORDS:
                    word_color, word_size, is_power = "#FF4D4D", int(actual_font_size * 1.10), True
                elif clean_w in GAIN_WORDS or clean_w in POWER_WORDS:
                    word_color, word_size, is_power = "#D4AF37", int(actual_font_size * 1.12), True
            elif re.search(r"\d", txt) or "%" in txt:
                word_color, word_size, is_power = accent_hex, int(actual_font_size * 1.18), True
            elif clean_w in WARN_WORDS:
                word_color, word_size, is_power = "#FF4D4D", int(actual_font_size * 1.14), True
            elif clean_w in GAIN_WORDS or clean_w in POWER_WORDS:
                word_color, word_size, is_power = "#39FF14", int(actual_font_size * 1.18), True

        # v3 FIX: captions are rendered as complete PIL images — MoviePy's
        # TextClip size math ignores stroke width and SLICES the bottom of
        # the glyphs (the "half-cut captions" bug). PIL gives exact bounds.
        txt_clip = None
        if se is not None:
            try:
                from PIL import ImageColor
                c = ImageColor.getrgb(word_color) if isinstance(word_color, str) else tuple(word_color)[:3]
                cap_img = se.render_text_image(
                    txt,
                    font_size=word_size,
                    color=tuple(c),
                    outline_color=(0, 0, 0),
                    outline_width=stroke_width + 1,
                    cursor=False,
                )
                txt_clip = ImageClip(np.array(cap_img), transparent=True)
            except Exception as cap_e:
                print(f"[Captions] PIL render failed ({cap_e}); using TextClip")
        if txt_clip is None:
            txt_clip = TextClip(
                text=txt,
                font=font_name,
                font_size=word_size,
                color=word_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width + 1,
                method='caption',
                size=(target_w - 120, None),
                text_align='center'
            )

        try:
            if ("minimalist" not in caption_theme and "cinematic" not in caption_theme
                    and not is_typewriter):
                # Upgraded: High-fidelity organic spring bounce scales from 0.85 up to 1.12, then settles smoothly to 1.0!
                bouncy_txt_clip = txt_clip.resized(lambda t: (0.85 + 0.27 * np.sin(t * (np.pi / 0.15))) if t < 0.15 else 1.0)
            else:
                bouncy_txt_clip = txt_clip
        except Exception:
            print("[Captions] bounce resize failed for one caption — using static text")
            bouncy_txt_clip = txt_clip
            
        text_clips.append(
            bouncy_txt_clip.with_duration(duration)
                           .with_start(max(0.0, s['start'] - 0.15))  # PRO: captions lead voice by 0.15s
                           .with_position(('center', 940))  # PRO STANDARD: 65-75% down (73.4%), clears bottom UI zone
        )
        
        if is_power and power_tick_budget > 0:
            power_tick_budget -= 1
            try:
                sfx_audio = make_safe_sfx_clip(pop_sfx_path, s['start'], total_duration, tick_vol)
                sfx_clips.append(sfx_audio)
            except Exception:
                pass

    return text_clips, sfx_clips

def build_subtitle_clips(subtitles, target_w=720, font_size=55, color='yellow'):
    tc, _ = build_subtitle_and_sfx_clips(subtitles, target_w, font_size, color, caption_style='standard')
    return tc

# --- SMART BACKGROUND AUDIO MIXER (v2: sidechain dips + energy arc) ---
def load_and_mix_audio(voice_audio_path, bg_music_path=None, bg_music_volume=0.10, drop_times=None, arc_peak_t=None, vtt_subs=None):
    voice_audio = AudioFileClip(voice_audio_path)
    
    if not bg_music_path or not os.path.exists(bg_music_path):
        return voice_audio, voice_audio
        
    music_audio = AudioFileClip(bg_music_path)
    
    voice_audio = voice_audio.with_volume_scaled(1.0)
    music_audio = music_audio.with_volume_scaled(bg_music_volume)
    
    duration = voice_audio.duration
    if music_audio.duration < duration:
        loops_needed = int(np.ceil(duration / music_audio.duration))
        music_audio = concatenate_audioclips([music_audio] * loops_needed)
        
    music_audio = music_audio.with_duration(duration)

    # v3 PRO: music arc = beat-locked intro swell × voice-duck "breathing"
    # (fast attack / slow release) × build-to-climax peak × 1.5s outro fade
    peak = arc_peak_t if arc_peak_t else duration * 0.65
    duck_grid = None
    if pe is not None and vtt_subs:
        try:
            duck_grid = pe.voice_duck_curve(vtt_subs, duration)
        except Exception as e:
            print(f"[ProEditor] duck curve failed: {e}")
    if pe is not None:
        try:
            n_grid = int(duration * 50) + 2
            arc_grid = np.array([
                pe.music_arc_gain(i / 50.0, peak, None) *
                ((duck_grid[i] if duck_grid is not None and i < len(duck_grid) else 1.0))
                for i in range(n_grid)
            ])
            def arc_filter(gf, t):
                if isinstance(t, np.ndarray):
                    idx = np.clip((t * 50).astype(int), 0, len(arc_grid) - 1)
                    return gf(t) * arc_grid[idx][:, None]
                i = min(len(arc_grid) - 1, max(0, int(float(t) * 50)))
                return gf(t) * arc_grid[i]
            if hasattr(music_audio, "transform"):
                music_audio = music_audio.transform(arc_filter)
            elif hasattr(music_audio, "fl"):
                music_audio = music_audio.fl(arc_filter)
        except Exception as e:
            print(f"[ProEditor] music arc failed: {e}")
    
    # v2: Smooth sidechain dips (user [SOUND_DROP] tags + hook→value)
    if drop_times:
        print(f"[Sound Drop Engine] Applying smooth sidechain dips at: {[round(x,1) for x in drop_times]}")
        music_audio = apply_sound_drop_ducking(music_audio, drop_times)
        
    # Upgrade: Mix a continuous deep sub-bass atmospheric hum (40Hz) to create spherical auditory depth!
    sub_bass_path = os.path.join(AUDIO_DIR, "temp_sub_bass_40hz.wav")
    try:
        generate_sub_bass_wav(sub_bass_path, duration=duration, frequency=40)
        sub_bass_audio = AudioFileClip(sub_bass_path).with_volume_scaled(0.045)
        final_audio = CompositeAudioClip([voice_audio, music_audio, sub_bass_audio])
    except Exception as e:
        print(f"[Warning] Failed creating sub-bass hum: {e}")
        final_audio = CompositeAudioClip([voice_audio, music_audio])
        
    return final_audio, voice_audio


# ==============================================================================
# QC REPORT — the 5-line verdict on the FINISHED file (you stop catching
# bad renders by watching: the report tells you before you upload)
# ==============================================================================
def run_qc_report(video_path, srt_path=None, cosmic=False, watermark=None):
    """CONFORMANCE AUDIT — the render witnesses itself.
    Every check corresponds to a complaint class a human would otherwise
    have to find by WATCHING the video. Output: ✅/⚠️ lines with exact
    timestamps, printed + saved to studio.log. This is the gap-filler:
    the machine reports the blank frame before the user does."""
    report = []
    try:
        clip = VideoFileClip(video_path)
        dur = clip.duration

        # 1) duration — Shorts sweet spot
        report.append(f"✅ duration {dur:.1f}s" if 25 <= dur <= 60
                      else f"⚠️ duration {dur:.1f}s (target 25-60s)")

        # 2) DEAD-FRAME SCAN — lists EVERY dead second (the "video is blank
        #    after some time" class; the user used to find these by watching).
        #    Rules that keep the panel honest (no false alarms):
        #    - scans the TOP 75% of the frame (the caption zone can't mask a
        #      dead frame, and caption text isn't a "dead frame" signal)
        #    - a frame with visible text/graphics (keyword cards) is intentional
        #    - in void mode the final 4.5s is the dark outro card (checked
        #      separately by its own test) — not a dead frame
        dead = []
        min_lum, worst_t = 255.0, 0.0
        scan_end = dur - 4.5 if cosmic else dur - 0.2
        t = 0.0
        while t < scan_end:
            try:
                f = clip.get_frame(t)
                top = f[: int(f.shape[0] * 0.75), :, :]
                lum = float(top.mean())
                bright = float((top.max(axis=2) > 100).mean())
                if lum < min_lum:
                    min_lum, worst_t = lum, t
                if lum < 10 and bright < 0.002:
                    dead.append(int(round(t)))
            except Exception:
                pass
            t += 1.0
        if dead:
            report.append(f"⚠️ DEAD FRAME(S) at {dead} — those seconds render black (b-roll failed to fill)")
        else:
            report.append(f"✅ no dead frames (luminance floor {min_lum:.0f}/255)")

        # 3) STYLE CONFORMANCE — measure the render against the reference's
        #    measured numbers (ref_video3: mean lum ~22/255, saturation ~2%)
        if cosmic:
            try:
                fm = clip.get_frame(dur * 0.5)
                lum_m = 0.2126 * fm[..., 0] + 0.7152 * fm[..., 1] + 0.0722 * fm[..., 2]
                mx, mn = fm.max(axis=2), fm.min(axis=2)
                sat = ((mx - mn) / np.maximum(mx, 1)) * (lum_m / 255 + 0.001)
                ok = 10 <= float(lum_m.mean()) <= 34 and float(sat.mean()) < 0.12
                report.append(f"✅ cosmic grade in range (lum {lum_m.mean():.0f}/255, sat {sat.mean()*100:.0f}% — ref ~22/2)"
                              if ok else f"⚠️ cosmic grade OFF-TARGET (lum {lum_m.mean():.0f}, sat {sat.mean()*100:.0f}%) — reference is ~22 lum / 2% sat")
            except Exception:
                pass

        # 4) hook presence — bright text in the top band within 1.2s
        try:
            f1 = clip.get_frame(min(0.6, dur / 2))
            top = f1[:400, :, :]
            bright = (0.2126 * top[..., 0] + 0.7152 * top[..., 1] + 0.0722 * top[..., 2]) > 150
            frac = float(bright.mean())
            report.append(f"✅ hook text visible early ({frac * 100:.0f}% bright top-band)"
                          if frac > 0.02 else "⚠️ no bright text in first 1.2s — hook layer may be missing")
        except Exception:
            report.append("⚠️ hook check failed (frame read)")

        # 5) OUTRO CARD (cosmic): the final 4s should be the dark card
        if cosmic:
            try:
                lum_out = float(clip.get_frame(max(0.5, dur - 1.5)).mean())
                report.append("✅ outro card present (final 4s)" if lum_out < 18
                              else "⚠️ no dark outro card in the final 4s — code/watermark outro missing")
            except Exception:
                pass

        # 6) WATERMARK (if configured): bright pixels in the top-right region
        if watermark and str(watermark).strip() != "":
            try:
                fw = clip.get_frame(min(10, dur - 5))
                region = fw[:70, -300:, :]
                bright = (0.2126 * region[..., 0] + 0.7152 * region[..., 1] + 0.0722 * region[..., 2]) > 120
                report.append("✅ watermark visible top-right" if float(bright.mean()) > 0.0008
                              else "⚠️ watermark NOT visible top-right — check the bible handle")
            except Exception:
                pass

        # 7) audio: loudness + per-second dead-audio scan
        try:
            a = clip.audio
            arr = a.to_soundarray(fps=22050, quantize=False)
            mono = arr.mean(axis=1) if arr.ndim > 1 else arr
            rms = float(np.sqrt(np.mean(mono ** 2)))
            lufs_est = 20 * np.log10(max(rms, 1e-6)) + 10.0   # 0.063 RMS ≈ -14 LUFS
            report.append(f"✅ loudness ≈ {lufs_est:.0f} LUFS (target ≈ -14)"
                          if -18 <= lufs_est <= -11 else f"⚠️ loudness ≈ {lufs_est:.0f} LUFS (target -18..-11)")
            dead_aud = [i for i in range(int(dur))
                        if len(mono[i*22050:(i+1)*22050]) and abs(mono[i*22050:(i+1)*22050]).mean() < 0.004]
            if dead_aud:
                report.append(f"⚠️ DEAD AUDIO at {dead_aud} — voice/music silent in those seconds")
            else:
                report.append("✅ no dead-audio seconds")
        except Exception as e:
            report.append(f"⚠️ audio QC failed: {e}")

        clip.close()

        # 8) captions alive — sample up to 5 cue times, text must be visible
        subs = parse_vtt(srt_path) if srt_path else []
        if subs:
            step_ = max(1, len(subs) // 5)
            sample_ts = [s["start"] + 0.1 for s in subs[::step_]]
            cap_ok, checked = 0, 0
            clip2 = VideoFileClip(video_path)
            for ts_ in sample_ts:
                if ts_ < 1 or ts_ > dur - 5:
                    continue
                checked += 1
                try:
                    fc = clip2.get_frame(ts_)
                    bottom = fc[int(fc.shape[0] * 0.72):, :, :]
                    bright = (0.2126 * bottom[..., 0] + 0.7152 * bottom[..., 1] + 0.0722 * bottom[..., 2]) > 140
                    if float(bright.mean()) > 0.0015:
                        cap_ok += 1
                except Exception:
                    pass
            clip2.close()
            report.append(f"✅ captions alive ({cap_ok}/{checked} sampled cue frames show text)"
                          if cap_ok > 0 else "⚠️ captions NOT visible at sampled cue times — caption layer dead")
        else:
            report.append("⚠️ captions: no SRT found — word-sync layer never built")
    except Exception as e:
        report.append(f"❌ audit failed: {e}")
    for line in report:
        log(f"QC {os.path.basename(str(video_path))}: {line}")
    return report


# ==============================================================================
# AI SFX DIRECTOR — "the AI chooses which sound gets added".
# Rules learned from ref_video3: whoosh on transitions, ticks on time words,
# flare on reveal words, riser before the climax, impact ON the climax line,
# sub-boom on the outro. Cosmic style is sparse: max 6 per video.
# ==============================================================================
SFX_DIRECTOR_KEYWORDS = {
    "tick_tock": ["clock", "time", "second", "minute", "hour", "wait", "slow", "tick", "delay"],
    "warp_whoosh": ["through", "into", "fast", "speed", "run", "chase", "warp", "beyond", "quick"],
    "comet_whoosh": ["escape", "break", "free", "away", "leave", "jump", "out"],
    "energy_flare": ["scientist", "study", "brain", "neuron", "secret", "reveal", "truth", "scientists"],
}


def direct_sfx(scene_boundaries, vtt_subs, duration, climax_t=None):
    """Return up to 6 (sfx_name, t, vol) events for this video's structure."""
    if not scene_boundaries or duration < 8:
        return []
    events = []

    def words_of(i):
        a, b = scene_boundaries[i]
        return " ".join(s["text"].lower() for s in vtt_subs if a <= s["start"] < b)

    # transitions: each inner cut checks the words of the scene it OPENS
    for i in range(1, len(scene_boundaries)):
        t = scene_boundaries[i][0]
        wtext = words_of(i)
        for sfx, kws in SFX_DIRECTOR_KEYWORDS.items():
            if any(k in wtext for k in kws):
                events.append((sfx, t, 0.30))
                break
    # climax: riser 1.8s before, impact ON the reveal
    if climax_t and 3 < climax_t < duration - 3:
        events.append(("riser", max(0.5, climax_t - 1.8), 0.32))
        events.append(("climax_impact", climax_t, 0.38))
    # outro: the sub-bass boom lands as the outro card takes over
    events.append(("sub_boom", max(0.5, duration - 4.2), 0.5))

    # strongest first, dedupe close-in-time, cap 6
    events.sort(key=lambda e: -e[2])
    seen, out = set(), []
    for name, t, v in events:
        key = round(t / 0.8)
        if key in seen:
            continue
        seen.add(key)
        out.append((name, t, v))
        if len(out) >= 6:
            break
    out.sort(key=lambda e: e[1])
    return out


# ==============================================================================
# STUDIO LOG — persistent file log (studio.log next to the app).
# Prints go to the console; the log survives and makes debugging easy after the
# fact ("why did that render use pixabay?" — check the log).
# Auto-truncates at ~1MB so it can never fill the disk.
# ==============================================================================
STUDIO_LOG_PATH = os.path.join(BASE_DIR, "studio.log")


def log(msg):
    try:
        if os.path.exists(STUDIO_LOG_PATH) and os.path.getsize(STUDIO_LOG_PATH) > 1_000_000:
            with open(STUDIO_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-400:]
            with open(STUDIO_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
        with open(STUDIO_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ==============================================================================
# 🧬 THE MASTER HYBRID VIDEO GENERATION PIPELINE 🧬
# ==============================================================================
def create_hybrid_ai_video(short_id, script_text, uploaded_file_paths=None, voice_name="en-GB-RyanNeural", font_color='yellow', **kwargs):
    timestamp = int(time.time())
    output_video_path = os.path.join(VIDEO_DIR, f"short_{short_id}_{timestamp}.mp4")
    _render_t0 = time.time()
    log(f"RENDER START id={short_id} voice={voice_name}")

    progress_cb = kwargs.get("progress_callback", None)

    # B5 FIX: track per-cut temp segment files + their open readers.
    # Old code created seg_{pid}_{ts}_{idx}.mp4 per cut and NEVER deleted them.
    _seg_files = []
    _seg_clips = []
    
    if progress_cb: progress_cb(0.05, "Cleaning script...")
    spoken_text = clean_script_for_speech(script_text)

    # PSYCHOLOGY TRICKS — the trick director alters the script BEFORE TTS:
    # one named secret + rotating comment bait + scheduled planted flaw.
    # Full system spec: psychology_tricks.md
    if kwargs.get("tricks", True):
        try:
            from script_engine import apply_tricks_to_script
            script_text, _tricks_used = apply_tricks_to_script(script_text, short_id)
            spoken_text = clean_script_for_speech(script_text)
            log(f"TRICKS id={short_id}: {_tricks_used}")
        except Exception as e:
            print(f"[Tricks] skipped: {e}")
    
    eleven_key = kwargs.get("elevenlabs_api_key", None)
    
    if progress_cb: progress_cb(0.15, "Generating high-fidelity neural speech voiceover...")
    audio_path, vtt_path = generate_tts_audio(spoken_text, voice_name, f"audio_{short_id}_hybrid", eleven_key=eleven_key, voice_preset=kwargs.get("voice_preset", "Deep Narrator Male"))

    # Fail LOUD: if every TTS engine died (no internet, all keys dead) the old
    # code crashed later with a cryptic ffmpeg error. Now it tells you why.
    if not audio_path or not os.path.exists(audio_path):
        if progress_cb: progress_cb(0.99, "Voice generation FAILED (all TTS engines down)")
        raise RuntimeError(
            "Voiceover generation failed — edge-tts, gTTS and ElevenLabs all failed. "
            "Check internet connection, then re-check your ElevenLabs key in the sidebar."
        )
    # vtt_path None = TTS produced audio but no timing data; guard the pipeline
    if not vtt_path or not os.path.exists(vtt_path):
        print("[Voice] ⚠ No subtitle timing file produced — captions/broll-sync will run on estimates.")
        vtt_path = None

    # PRO PASS 4a — 7-step pro voice chain: HPF → EQ ×2 → compressor →
    # de-esser → air → warmth saturation → glue. (the "warm human tone")
    if pe is not None:
        try:
            chained = pe.apply_voice_chain(audio_path, out_dir=AUDIO_DIR)
            if chained != audio_path:
                print("[ProEditor] 7-step voice chain applied")
                audio_path = chained
        except Exception as e:
            print(f"[ProEditor] voice chain skipped: {e}")
    
    db_caption_style = db_settings.get_setting("caption_style", "word_pop")
    db_music_volume = float(db_settings.get_setting("bg_music_volume", 0.12))
    db_font_size = int(db_settings.get_setting("font_size", 55))
    db_whoosh_volume = float(db_settings.get_setting("whoosh_volume", 0.12))
    # PIECE 9 — SFX KNOB: one slider controls the entire SFX layer (0 = silent, 1 = full)
    sfx_level = float(kwargs.get("sfx_level", 1.0))
    db_whoosh_volume = db_whoosh_volume * sfx_level
    
    bg_music_path = kwargs.get("bg_music_path", None)
    bg_music_volume = kwargs.get("bg_music_volume", db_music_volume)
    
    # Upgrade: Intelligent Music Analyzer & Suitability Selector
    # If no music is specified or "auto" is passed, we automatically choose the perfect genre matching your script's sentiment!
    if not bg_music_path or bg_music_path == "auto" or not os.path.exists(bg_music_path):
        text_lower = spoken_text.lower()
        # v2: LOFI is the default bed (voice-first). Dramatic only for explicit urgency content —
        # busy electronic mids fight the voice and are a top skip trigger.
        if any(w in text_lower for w in ["scam", "exposed", "warning", "danger", "urgent", "emergency", "breaking"]):
            track_tag = "dramatic"
        elif any(w in text_lower for w in ["romance", "intimacy", "love", "passion", "feel", "partner", "kiss"]):
            track_tag = "ambient"
        else:
            track_tag = "lofi" # calm lofi bed — the elite faceless standard
            
        download_free_soundtrack(track_tag)
        bg_music_path = os.path.join(DEFAULT_DIR, f"music_{track_tag}.mp3")
    else:
        # A specific file path was provided, make sure it exists
        if not os.path.exists(bg_music_path):
            track_tag = "dramatic" if "dramatic" in bg_music_path.lower() else ("ambient" if "ambient" in bg_music_path.lower() else "lofi")
            download_free_soundtrack(track_tag)
            bg_music_path = os.path.join(DEFAULT_DIR, f"music_{track_tag}.mp3")
            
    voice_audio = AudioFileClip(audio_path)
    duration = voice_audio.duration
    log(f"VOICE OK {os.path.basename(audio_path)} dur={duration:.1f}s srt={os.path.basename(vtt_path) if vtt_path else 'NONE'}")

    # ====================================================================
    # NEW: ELITE STYLE SYSTEM — background style, accent color, clip mode
    # ====================================================================
    style_bg = str(kwargs.get("style_bg", "grid")).lower()
    style_accent = str(kwargs.get("style_accent", "yellow")).lower()
    clip_mode = str(kwargs.get("clip_mode", "blend")).lower()
    # GOONINGGNG mode: "void" background auto-brings the cosmic grade on all b-roll
    cosmic = (style_bg == "void")
    # PACING MODE — the Video Pacing dropdown (adrenaline/cinematic/mindful/cosmic).
    # Defined HERE (before the expectation gate) so the gate can inspect it.
    pacing = str(kwargs.get("pacing", "cinematic")).lower()
    # PIECE 4 — CHARACTER BIBLE (loaded EARLY: the expectation gate inspects it
    # for the watermark handle. Moving this down was a latent NameError in
    # void mode — the gate ran before the bible existed.)
    channel_bible = kwargs.get("character_bible", None) or load_character_bible()
    # EXPECTATION GATE — warn LOUDLY about config issues BEFORE burning 5
    # minutes on a video that will miss the expected style (the "@yourchannel
    # on the outro" class of surprise, caught pre-render instead of post)
    if cosmic:
        _wm_g = str((channel_bible or {}).get("watermark", "") or "").strip()
        if False: # Removed watermark warning
            pass
        if pacing != "cosmic":
            print(f"[GATE] NOTE: void style with '{pacing}' pacing — the reference grammar is 'cosmic' (4-9s holds).")
        if clip_mode == "blend":
            print("[GATE] NOTE: void + blend mode — the reference shows b-roll 'full' (the clip IS the visual).")
    accent_rgb = (255, 215, 0)
    if se is not None:
        accent_rgb = se.ACCENTS.get(style_accent, (255, 215, 0))

    # L1: ALWAYS-ON dark style background (never pure black — luminance floor)
    style_bg_clip = None
    try:
        if se is not None:
            if progress_cb: progress_cb(0.28, f"Building '{style_bg}' style background with {style_accent} accent glow...")
            style_bg_clip = se.make_style_background_clip(duration, style=style_bg, accent=style_accent)
    except Exception as e:
        print(f"[StyleEngine] Background generation failed: {e}")

    # ====================================================================
    # PRO EDITOR BRAIN — v3 pipeline (research: Cutting Rhythms, pro post
    # workflows, -14 LUFS mixing standard)
    # PASS 0: paper cut (beat map) · Elite layer (reveal = climax)
    # PASS 2: pro rhythm (tension-driven cuts ON spoken words)
    # ====================================================================
    vtt_subs = parse_vtt(vtt_path)

    # Elite text layer — its reveal moment is the CLIMAX of the whole video
    elite_clips = []
    elite_sfx = []
    if se is not None:
        try:
            elite_clips, elite_sfx = se.build_elite_text_layer(
                script_text, vtt_subs, duration, accent=style_accent, sfx_dir=AUDIO_DIR,
                hook_style=("stack_contrast" if cosmic else "uniform"),
                hook_hold=(4.5 if cosmic else 3.2))
        except Exception as e:
            print(f"[StyleEngine] Elite text layer failed: {e}")
    arc_peak_t = next((t for k, t, v in elite_sfx if k == "__ding__"), None)

    # PASS 2 — RHYTHM: tension-based shot lengths, cut-on-word, 2.5s hard
    # cap, 2-fast-then-slow breathing (replaces random pacing)
    if progress_cb: progress_cb(0.29, "PRO EDITOR: paper cut (beat map) + pro rhythm (tension cuts on words)...")
    # PACING MODE (already defined above, before the expectation gate)
    scene_boundaries = None
    if pe is not None:
        try:
            beat_map = pe.build_beat_map(duration, climax_t=arc_peak_t)
            scene_boundaries = pe.build_scene_rhythm(beat_map, vtt_subs, duration, pacing=pacing)
        except Exception as e:
            print(f"[ProEditor] rhythm failed ({e}); falling back to fixed pacing")
    if scene_boundaries is None or not scene_boundaries:
        scene_boundaries = []
        ct = 0.0
        while ct < duration:
            sd = 1.0 if ct < 3.0 else 1.5
            if ct + sd >= duration - 0.3:
                sd = duration - ct
            if sd > 0.05:
                scene_boundaries.append((ct, ct + sd))
            ct += sd

    num_cuts = len(scene_boundaries)
    
    # Upgrade: Parse and Schedule Psychological tags dynamically from script draft lines!
    # Strip bracket lines like [HOOK] during parsing
    script_lines = [l.strip() for l in script_text.split('\n') if l.strip() and not (l.strip().startswith('[') and l.strip().endswith(']'))]
    
    drop_times = []
    meme_overlays = []
    save_trigger_overlays = []
    
    # Always drop music volume at the crucial Hook-to-Value transition!
    if len(scene_boundaries) > 0:
        drop_times.append(scene_boundaries[0][1])
        
    for idx_line, line in enumerate(script_lines):
        if idx_line < len(scene_boundaries):
            start_t, end_t = scene_boundaries[idx_line]
            
            if "[SOUND_DROP]" in line:
                drop_times.append(start_t)
                
            meme_match = re.search(r'\[MICRO_MEME:\s*(.*?)\]', line, re.IGNORECASE)
            if meme_match:
                meme_type = meme_match.group(1).strip()
                meme_overlays.append((start_t, meme_type))
                
            save_match = re.search(r'\[SAVE_TRIGGER_LIST:\s*(.*?)\]', line, re.IGNORECASE)
            if save_match:
                points_text = save_match.group(1).strip()
                save_trigger_overlays.append((start_t, points_text))
                
    # ====================================================================
    # (Elite text layer + arc_peak_t already built in the PRO EDITOR block above)
    # ====================================================================

    if progress_cb: progress_cb(0.30, "PRO PASS 4: voice chain + music arc (intro swell, voice-duck breathing, climax peak)...")
    mixed_audio, voice_audio = load_and_mix_audio(audio_path, bg_music_path, bg_music_volume, drop_times=drop_times, arc_peak_t=arc_peak_t, vtt_subs=vtt_subs)
    
    progress_cb_step_weight = 0.40 / num_cuts
    visual_clips = []
    transition_audio_clips = []
    whoosh_path = generate_synthetic_whoosh_sound()
    
    # Read API keys permanently (B8: app-folder first, CWD fallback)
    def _read_key_file(name):
        for d in (BASE_DIR, os.getcwd()):
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception as e:
                    print(f"[Keys] Could not read {name}: {e}")
        return ""

    pexels_key = kwargs.get("pexels_api_key", None)
    if not pexels_key or not pexels_key.strip():
        pexels_key = _read_key_file("pexels_key.txt")

    pixabay_key = _read_key_file("pixabay_key.txt") or None
            
    custom_files = uploaded_file_paths if uploaded_file_paths else []
    b_roll_source = kwargs.get("b_roll_source", "pexels").lower()
    # (channel_bible was loaded early, before the expectation gate)

    # Read custom storyboard scenarios list if passed!
    custom_scenarios = kwargs.get("custom_scenarios", [])
    
    # --- AUTO-DETERMINE COHESIVE COLOR SCHEME BASED ON VIBE ---
    color_tone = "aesthetic"
    vibe_color_rgb = (30, 58, 138) # Default Blue
    if "romance" in spoken_text.lower() or "intimacy" in spoken_text.lower() or "kiss" in spoken_text.lower():
        color_tone = "rose romantic warm"
        vibe_color_rgb = (127, 29, 29) # Moody Red/Rose
    elif "disciplined" in spoken_text.lower() or "workout" in spoken_text.lower() or "perform" in spoken_text.lower():
        color_tone = "emerald green focused"
        vibe_color_rgb = (6, 78, 59) # Moody Green
    elif "procrastinat" in spoken_text.lower() or "lazy" in spoken_text.lower() or "focus" in spoken_text.lower():
        color_tone = "dark moody violet"
        vibe_color_rgb = (15, 23, 42) # Moody Violet
    
    # Extract different, unique keywords for EVERY cut index!
    # If the AI Director (v2.0) provided explicit queries, USE THEM instead of blind NLP extraction!
    sentence_words = []
    if kwargs.get("ai_data") and isinstance(kwargs["ai_data"], dict):
        sentence_words = kwargs["ai_data"].get("b_roll_queries", [])
    
    if not sentence_words or len(sentence_words) < 2:
        sentence_words = extract_best_keywords(spoken_text, num_words=num_cuts)
    
    # --- PROACTIVE RETENTION UPGRADE: DOWNLOAD MEME SFX LOOP ---
    meme_sfx_name = kwargs.get("meme_sfx_name", None)
    meme_sfx_path = None
    if meme_sfx_name and meme_sfx_name.lower() != "none":
        meme_sfx_path = download_free_meme_sfx(meme_sfx_name)
    
    hf_token = kwargs.get("hf_token", None)

    # ====================================================================
    # NEW: B-ROLL LOADER WITH STYLE-SYSTEM CLIP MODES + ZOOM PUNCH
    # blend = darkened semi-transparent over the style background
    # inset = rounded window over the style background
    # full  = classic full-frame (premium grade applied)
    # none  = text-first elite mode (no clips at all)
    # ====================================================================
    def add_broll(clip_path, start_t, clip_dur, idx):
        try:
            raw_v = VideoFileClip(clip_path)
            # --- BLACK-FRAME GUARD (the dead-black full-frame was the #1
            # "not as expected" artifact): probe candidate windows and only
            # accept one whose content is actually visible. Fades, corrupt
            # mid-sections and all-black sources get rejected -> the scene
            # falls through to the text-first card instead of showing black.
            sub_start = 0.0
            if raw_v.duration > clip_dur + 1.0:
                np.random.seed(idx)
                for _ in range(4):
                    cand = np.random.uniform(0.0, raw_v.duration - clip_dur)
                    sub_start = cand
                    try:
                        # 3-point probe (25/50/75%): a fade anywhere inside the
                        # window must not leave a quarter of the scene black
                        probe_ok = True
                        for _fr in (0.25, 0.5, 0.75):
                            if float(raw_v.get_frame(cand + clip_dur * _fr).mean()) < 8.0:
                                probe_ok = False
                                break
                        if probe_ok:
                            break
                    except Exception:
                        break
            else:
                # short source: the whole thing is the window — probe three
                # points, reject if any is black (a black clip held as
                # "previous visual" is what blanked the whole back half of
                # the NEW3 render)
                try:
                    black_seen = False
                    for _fr in (0.25, 0.5, 0.75):
                        _pt = max(0.05, min(raw_v.duration - 0.05, raw_v.duration * _fr))
                        if float(raw_v.get_frame(_pt).mean()) < 8.0:
                            black_seen = True
                            break
                    if black_seen:
                        raw_v.close()
                        return False   # source is black -> text-first fallback
                except Exception:
                    pass
            # --- MEMORY-SAFE SEGMENT EXTRACTION ---
            # Extract the exact 1-2s segment to a tiny temp file, then close the big
            # source reader immediately. Prevents the ~30 open ffmpeg readers from
            # exhausting RAM on low-memory hosts (Streamlit Cloud free tier).
            seg_path = os.path.join(AUDIO_DIR, f"seg_{os.getpid()}_{int(time.time() * 1000)}_{idx}.mp4")
            seg_ok = False
            try:
                import imageio_ffmpeg
                _ff = imageio_ffmpeg.get_ffmpeg_exe()
                subprocess.run(
                    [_ff, "-y", "-loglevel", "error",
                     "-ss", f"{sub_start:.2f}", "-t", f"{clip_dur:.2f}",
                     "-i", clip_path, "-an",
                     "-c:v", "libx264", "-preset", "ultrafast",
                     "-pix_fmt", "yuv420p", "-r", "24", seg_path],
                    check=True, timeout=120,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                seg_ok = os.path.exists(seg_path) and os.path.getsize(seg_path) > 1000
            except Exception as seg_err:
                print(f"[Broll] Segment extraction failed ({seg_err}); using in-memory subclip")
                _force_delete(seg_path)   # B5: don't leave a partial file behind
            if seg_ok:
                raw_v.close()
                sub_v = VideoFileClip(seg_path)
                _seg_files.append(seg_path)    # B5: delete after final render
                _seg_clips.append(sub_v)       # B5: close after final render
            else:
                sub_v = raw_v.subclipped(sub_start, sub_start + clip_dur)
            # --- SHORT-CLIP GUARD (blank-tail killer): if the usable clip is
            # shorter than its scene window, the tail used to play pure void.
            # Loop the clip to fill the window instead.
            try:
                if sub_v.duration < clip_dur - 0.15:
                    _loops = int(np.ceil(clip_dur / sub_v.duration)) + 1
                    from moviepy import concatenate_videoclips as _catv
                    sub_v = _catv([sub_v] * _loops).subclipped(0, clip_dur)
            except Exception as e:
                print(f"[Broll] loop-fill failed ({e}); tail may be short")
            if clip_mode == "none":
                return True  # text-first mode: background + text only
            dark = (clip_mode == "blend")
            # PRO PASS 5 — primary correction: sample this clip's exposure and
            # match it to the channel's dark-premium target level
            exp_gain = 1.0
            if pe is not None:
                try:
                    fr = [sub_v.get_frame(0.05), sub_v.get_frame(clip_dur / 2.0), sub_v.get_frame(max(0.05, clip_dur - 0.1))]
                    exp_gain = pe.exposure_gain_for_frames(fr)
                except Exception:
                    exp_gain = 1.0
            # v2: brighter blend (0.82) + lighter dark grade — clips must stay clearly visible
            scaled_sub = make_vertical_clip(sub_v, dark_blend=dark, exposure_gain=exp_gain, cosmic=cosmic)
            # User reported 'VIDEO RATIO' bug.
            # The continuous zoom lambda is squashing and distorting the aspect ratio over time.
            # Removed the 1.0 -> 1.06 dynamic resize to keep the 720x1280 ratio locked perfectly.
            if clip_mode == "blend" and se is not None:
                try:
                    scaled_sub = se.set_opacity(scaled_sub, 0.82)
                except Exception:
                    pass
            elif clip_mode == "inset":
                try:
                    win_w, win_h = 620, 1102
                    small = scaled_sub.resized(width=win_w, height=win_h)
                    mask_img = Image.new("L", (win_w, win_h), 0)
                    md = ImageDraw.Draw(mask_img)
                    md.rounded_rectangle([(0, 0), (win_w - 1, win_h - 1)], radius=28, fill=255)
                    if se is not None:
                        small = se.set_mask(small, ImageClip(np.array(mask_img), ismask=True))
                    else:
                        small = small.with_mask(ImageClip(np.array(mask_img), ismask=True))
                    small = small.with_position(((720 - win_w) // 2, 90))
                    scaled_sub = small
                except Exception as ie:
                    print(f"[StyleEngine] Inset window failed: {ie}")
            visual_clips.append(scaled_sub.with_start(start_t))
            return True
        except Exception as e:
            print(f"Failed loading B-roll clip: {e}")
            return False

    used_search_words = set()   # each abstract word searched at most once per video
    used_clip_files = set()     # never reuse the same source clip twice
    prev_clip_file = None       # generic word spoken → carry the previous visual

    # B5: clear STALE segment temp files from a previously crashed/killed render
    # (anything older than 10 minutes is safe to remove; live segments are fresh)
    try:
        for _n in os.listdir(AUDIO_DIR):
            if _n.startswith("seg_") and _n.endswith(".mp4"):
                _p = os.path.join(AUDIO_DIR, _n)
                try:
                    if time.time() - os.path.getmtime(_p) > 600:
                        _force_delete(_p)
                except Exception:
                    pass
    except Exception:
        pass

    for idx in range(num_cuts):
        start_t, end_t = scene_boundaries[idx]
        clip_dur = end_t - start_t
        if clip_dur <= 0.05:
            continue
            
        clip_added = False
        search_word = None
        # SENTENCE-LEVEL CONCEPT SYNC
        # Instead of erratic single-word matching ("brain", then "time", then "infinity"),
        # we pull the dominant thematic concept from the entire sentence.
        sync_word = None
        if idx < len(sentence_words):
            sync_word = sentence_words[idx]
        
        if sync_word:
            used_search_words.add(sync_word)
            search_word = sync_word

        # Scenario A: Use uploaded file first!
        if idx < len(custom_files):
            file_path = custom_files[idx]
            if os.path.exists(file_path):
                if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Slicing and zoom-formatting your uploaded asset {idx+1}...")
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    v_clip = make_ken_burns_clip(file_path, clip_dur).with_start(start_t)
                    visual_clips.append(v_clip)
                    clip_added = True
                elif file_path.lower().endswith(('.mp4', '.mov')):
                    if add_broll(file_path, start_t, clip_dur, idx):
                        clip_added = True
                        
        # --- SCENARIO B - GENERATE TRUE AI VIDEO FROM SCRATCH ---
        # PIECE 5 (AUTO MODE): b_roll_source "auto" = Pollinations PRIMARY (keyless,
        # never depletes), HF secondary. "huggingface" = HF primary, Pollinations backup.
        # PIECE 4 (CHARACTER BIBLE): bible + seed_offset keep the same look every clip.
        is_ai_mode = b_roll_source in ("huggingface", "auto")
        ai_allowed = is_ai_mode and (b_roll_source == "auto" or (hf_token and hf_token.strip()))
        if not clip_added and ai_allowed:
            if idx < len(custom_scenarios) and custom_scenarios[idx].strip():
                search_word = custom_scenarios[idx].strip()
            elif not search_word and len(sentence_words) > 0:
                search_word = sentence_words[idx % len(sentence_words)]
            if search_word:
                if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"AI Generating clip for '{search_word.upper()}'...")
                downloaded_file = generate_true_ai_video_clip(
                    search_word, hf_token,
                    bible=channel_bible, seed_offset=idx,
                    prefer_pollinations=(b_roll_source == "auto"))
                if downloaded_file and os.path.exists(downloaded_file) and downloaded_file not in used_clip_files and add_broll(downloaded_file, start_t, clip_dur, idx):
                    clip_added = True
                    used_clip_files.add(downloaded_file)
                    prev_clip_file = downloaded_file

        # Scenario C: Fetch stock video — VTT-SYNCED to the spoken word!
        if not clip_added:
            target_source = b_roll_source
            if target_source in ("huggingface", "auto"):
                target_source = "pexels" if pexels_key and pexels_key.strip() else "pixabay"
            # F2: pexels hourly budget near/exhausted → auto-switch to pixabay
            if target_source == "pexels" and not _pexels_gate_open():
                if pixabay_key and pixabay_key.strip():
                    target_source = "pixabay"

            active_key = pexels_key if target_source == "pexels" else pixabay_key

            if active_key and active_key.strip():
                if idx < len(custom_scenarios) and custom_scenarios[idx].strip():
                    search_word = custom_scenarios[idx].strip()
                elif not search_word and prev_clip_file:
                    # Generic/abstract word spoken (she/her/woman/real...) →
                    # HOLD the previous visual instead of a NEW random clip
                    if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, "Holding previous visual (word not illustratable)...")

                if search_word:
                    if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Downloading clip for SPOKEN word '{search_word.upper()}'...")
                    downloaded_file = download_pexels_b_roll_with_fallback(
                        search_word, active_key, source=target_source,
                        color_tone=("dark space" if cosmic else color_tone), cosmic=cosmic)
                    if downloaded_file and os.path.exists(downloaded_file) and downloaded_file in used_clip_files:
                        # same clip already used → dedupe: reuse previous instead
                        downloaded_file = None
                    if downloaded_file and os.path.exists(downloaded_file) and add_broll(downloaded_file, start_t, clip_dur, idx):
                        clip_added = True
                        used_clip_files.add(downloaded_file)
                        prev_clip_file = downloaded_file
                elif prev_clip_file and add_broll(prev_clip_file, start_t, clip_dur, idx):
                    clip_added = True

        # Scenario D: TEXT-FIRST fallback (pro Tool 3) — the word ITSELF becomes
        # the visual: style background + huge accent word. Only when real footage
        # is unavailable; no more random "aesthetic" clips for abstract words.
        if not clip_added and clip_mode != "none":
            kw = (search_word or "").split()[0] if search_word else ""
            kw = kw if 2 <= len(kw) <= 16 else ""
            if kw and se is not None:
                try:
                    if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, f"Text-first beat for '{kw.upper()}'...")
                    kw_clip = se.make_keyword_clip(kw, clip_dur, accent=style_accent, style=style_bg)
                    visual_clips.append(kw_clip.with_start(start_t))
                    clip_added = True
                except Exception as e:
                    print(f"[StyleEngine] keyword clip failed: {e}")
            if not clip_added:
                if progress_cb: progress_cb(0.35 + idx * progress_cb_step_weight, "Generating custom-color editorial backup graphic card...")
                p_clip = make_solid_color_card_clip(clip_dur, color_tuple=vibe_color_rgb).with_start(start_t)
                visual_clips.append(p_clip)
            
        # PRO PASS 6 — NO per-cut transitions. The pro edit is INVISIBLE:
        # hard cuts carry 90%+ of the edit; flashes are reserved for the
        # 3 structural moments (added after the loop).
                
    # PRO PASS 6 — transition flash reserved for the 3 STRUCTURAL moments only:
    # hook→content, the reveal (climax), and the ending. Never on every cut.
    log(f"BROLL DONE source={b_roll_source} clips={len(visual_clips)}")
    for _fl_t in (scene_boundaries[0][1] if scene_boundaries else 3.0,
                  arc_peak_t,
                  duration - 2.0):
        if _fl_t and 0.5 < _fl_t < duration - 0.5:
            try:
                visual_clips.append(make_light_leak_flash(_fl_t, duration=0.25))
            except Exception:
                pass

    if meme_sfx_path and os.path.exists(meme_sfx_path):
        try:
            sfx_clip = make_safe_sfx_clip(meme_sfx_path, scene_boundaries[0][1] if len(scene_boundaries) > 0 else 2.0, duration, 0.18)
            transition_audio_clips.append(sfx_clip)
        except Exception as e:
            print(f"Failed mixing meme SFX: {e}")

    # ====================================================================
    # ====================================================================
    # NEW: ELITE TEXT LAYER — built earlier (before the audio mix) so its
    # reveal moment can drive the energy arc. SFX budget: max 5 per video.
    # ====================================================================
    _sfx_cache = {}
    def _sfx_path(key):
        if key not in _sfx_cache:
            if key == "__hit__":
                _sfx_cache[key] = se.generate_sfx_hit(AUDIO_DIR)
            elif key == "__pop__":
                _sfx_cache[key] = generate_synthetic_pop_sound()
            elif key == "__whoosh__":
                _sfx_cache[key] = whoosh_path
            elif key == "__riser__":
                _sfx_cache[key] = se.generate_sfx_riser(AUDIO_DIR)
            elif key == "__impact__":
                _sfx_cache[key] = se.generate_sfx_impact(AUDIO_DIR)
            elif key == "__ding__":
                _sfx_cache[key] = se.generate_sfx_ding(AUDIO_DIR)
            else:
                _sfx_cache[key] = None
        return _sfx_cache[key]

    for sfx_key, sfx_t, sfx_vol in elite_sfx:
        try:
            p = _sfx_path(sfx_key)
            if p:
                c = make_safe_sfx_clip(p, max(0.0, min(sfx_t, duration - 0.05)), duration, sfx_vol * sfx_level)
                transition_audio_clips.append(c)
        except Exception as e:
            print(f"[StyleEngine] SFX {sfx_key} failed: {e}")

    # Upgrade: Dynamic Micro-Meme Overlay Sticker Injector!
    for start_t, meme_type in meme_overlays:
        try:
            if start_t < duration:
                if progress_cb: progress_cb(0.70, f"Integrating dynamic micro-meme Reaction overlay for '{meme_type.upper()}'...")
                meme_badge = make_micro_meme_sticker(meme_type)
                meme_dur = min(1.2, duration - start_t)
                meme_clip = ImageClip(np.array(meme_badge)).with_start(start_t).with_duration(meme_dur).with_position(("center", 780))
                visual_clips.append(meme_clip)
                try:
                    pop_sfx = make_safe_sfx_clip(whoosh_path, start_t, duration, db_whoosh_volume * 1.5)
                    transition_audio_clips.append(pop_sfx)
                except Exception:
                    pass
        except Exception as e:
            print(f"Failed overlaying micro-meme sticker: {e}")
            
    # Upgrade: Dynamic High-Density Save Trigger Infographics Card Injector!
    # (skipped when the new elite curiosity card already shows this list)
    _elite_has_card = (se is not None) and bool(se.parse_beats(script_text)[1])
    for start_t, points_text in ([] if _elite_has_card else save_trigger_overlays):
        try:
            if start_t < duration:
                if progress_cb: progress_cb(0.71, "Integrating dynamic high-density Save-Trigger infographic overlay...")
                save_card = make_save_trigger_card(points_text, duration=1.5)
                save_clip = save_card.with_start(start_t).with_position(("center", "center"))
                visual_clips.append(save_clip)
                try:
                    chime_sfx = make_safe_sfx_clip(whoosh_path, start_t, duration, db_whoosh_volume * 1.8)
                    transition_audio_clips.append(chime_sfx)
                except Exception:
                    pass
        except Exception as e:
            print(f"Failed overlaying Save-Trigger card: {e}")
            
    # PRO FIX: in blend mode the channel background (grid + accent glow) is
    # ALSO painted lightly ON TOP of the B-roll, so the brand background is
    # ALWAYS visible — the frame stays unified, no more "no background" feel
    if clip_mode == "blend" and se is not None:
        try:
            grid_overlay = se.make_style_background_clip(duration, style=style_bg, accent=style_accent)
            grid_overlay = se.set_opacity(grid_overlay, 0.28)
            visual_clips.append(grid_overlay)
        except Exception as e:
            print(f"[StyleEngine] grid overlay failed: {e}")

    # Upgrade: Cinematic Vignette Edge-Shading Overlay (Eye Funnel Mask)
    try:
        vignette_mask = make_vignette_overlay(duration)
        visual_clips.append(vignette_mask)
    except Exception as e:
        print(f"Failed applying cinematic vignette mask: {e}")
            
    # L1 style background is ALWAYS the base layer — the frame can never die to black
    base_layers = [style_bg_clip] if style_bg_clip is not None else []
    raw_bg_clip = CompositeVideoClip(base_layers + visual_clips, size=(720, 1280)).with_duration(duration)
    
    # Layer film scratch overlay
    if progress_cb: progress_cb(0.72, "Applying 24fps luxury film grain and retro dust scratches overlay...")
    film_overlay = make_cinematic_overlay(duration)
    bg_clip = CompositeVideoClip([raw_bg_clip, film_overlay]).with_duration(duration)
    
    if progress_cb: progress_cb(0.80, "Slicing word-by-word caption timings and mapping power-word highlights...")
    caption_style = kwargs.get("caption_style", db_caption_style)
    # SPEED FIX: reuse the vtt_subs parsed at the top (was parsed twice)
    text_clips, sfx_clips = build_subtitle_and_sfx_clips(vtt_subs, color=font_color, caption_style=caption_style, font_size=db_font_size, total_duration=duration, accent_rgb=accent_rgb, sfx_level=sfx_level)
    
    # Mix all sound design elements (subtitles pop clicks + transition whooshes + meme triggers) into the main audio track!
    all_sfx = sfx_clips + transition_audio_clips

    # PIECE 13 — signature stinger at 0.0s: the channel's AUDIO identity.
    # Same waveform + same volume in every video (sfx_level scales the whole SFX layer).
    try:
        all_sfx = all_sfx + [make_safe_sfx_clip(generate_signature_stinger(), 0.0, duration, 0.5 * sfx_level)]
    except Exception as e:
        print(f"[Audio] signature stinger skipped: {e}")

    if all_sfx:
        mixed_audio = CompositeAudioClip([mixed_audio] + all_sfx)
        
    bg_clip = bg_clip.with_audio(mixed_audio)
    
    extra_clips = []
    # Progress bar is OFF by default (YouTube UI covers the bottom edge; it read as a bug)
    if kwargs.get("show_progress_bar", False):
        prog_clip = make_progress_bar_clip(duration, bar_color=accent_rgb)
        extra_clips.append(prog_clip)

    # NEW: Elite text layer — hook / beats / cards / arrows (content-driven retention)
    extra_clips.extend(elite_clips)

    # ====================================================================
    # GOONINGGNG MODE (void background) — the signature layers:
    # AI SFX director, outro card + daily code, watermark lock,
    # sigil frame (B5), 1-frame code flash (A3 hidden detail)
    # ====================================================================
    if cosmic:
        # 1) AI SFX DIRECTOR — picks the sounds for this video's structure
        try:
            _director_events = direct_sfx(scene_boundaries, vtt_subs, duration, climax_t=arc_peak_t)
            for _sfx_name, _sfx_t, _sfx_vol in _director_events:
                _p = download_free_meme_sfx(_sfx_name)
                if _p:
                    transition_audio_clips.append(make_safe_sfx_clip(_p, _sfx_t, duration, _sfx_vol * sfx_level))
            if _director_events:
                log(f"SFX DIRECTOR id={short_id}: {[(n, round(t, 1)) for n, t, _ in _director_events]}")
        except Exception as e:
            print(f"[SFX] director failed: {e}")
        # 2) OUTRO CARD (final 4s) + DAILY CODE (B4) + 1-frame code flash (A3)
        try:
            _handle = (channel_bible or {}).get("watermark", "")
            _code = se.daily_code() if se else "0-0-0"
            _card = None # se.make_outro_card disabled to preserve loops
            if _card is not None:
                extra_clips.append(ImageClip(np.array(_card)).with_start(duration - 4.0).with_duration(4.0))
            try:
                db_settings.set_setting("last_code", _code)
            except Exception:
                pass
            log(f"OUTRO CODE {time.strftime('%Y-%m-%d')}: {_code}")
            try:
                _fl = se.render_text_image(_code, font_size=26, color=(255, 215, 0), outline_width=0, pad=4)
                _fa = np.array(_fl).astype(np.float32)
                _fa[..., 3] *= 0.5
                extra_clips.append(ImageClip(_fa.astype(np.uint8), transparent=True)
                                   .with_start(duration * 0.70).with_duration(1.0 / 24.0)
                                   .with_position(("center", int(se.HEIGHT * 0.42))))
            except Exception:
                pass
        except Exception as e:
            print(f"[StyleEngine] outro card failed: {e}")
        # 3) SIGIL frame (B5 — the insider mark)
        try:
            extra_clips.append(se.make_sigil_overlay(duration, seed=int(short_id)))
        except Exception as e:
            print(f"[StyleEngine] sigil failed: {e}")
        # 4) WATERMARK lock (top-right, every frame)
        try:
            _wm = se.make_watermark_clip((channel_bible or {}).get("watermark", ""), duration)
            if _wm is not None:
                extra_clips.append(_wm)
        except Exception as e:
            print(f"[StyleEngine] watermark failed: {e}")
    if progress_cb: progress_cb(0.88, "Compiling multi-track layers & starting FFmpeg rendering encoder...")
    # --- COMBINED ROBUST WINDOWS COLORSPACE & CODEC FIXED FORMAT + SPEED PRESET SPEEDUP ---
    
    # --- STRICT 59.5 SECOND TRIM (YouTube Shorts Compliance) ---
    final_comp = CompositeVideoClip([bg_clip] + text_clips + extra_clips)
    
    # CRITICAL AUDIO FIX: MoviePy 2.x CompositeVideoClip does NOT always inherit audio automatically.
    # We must explicitly re-attach the mixed audio track to the final composition layer.
    if bg_clip.audio is not None:
        final_comp = final_comp.with_audio(bg_clip.audio)
        
    if duration > 59.5:
        print(f"[Engine] WARNING: Raw duration {duration:.2f}s exceeds Shorts limit. Hard trimming to 59.5s.")
        final_comp = final_comp.subclipped(0, 59.5)
        
    # BULLETPROOF AUDIO MULTIPLEXER (Fixing MoviePy 2.x audio drop bug)
    temp_vid = output_video_path.replace(".mp4", "_tempv.mp4")
    temp_aud = output_video_path.replace(".mp4", "_tempa.mp3")
    
    # 1. Write muted video
    final_comp.write_videofile(
        temp_vid, 
        fps=24, 
        codec="libx264", 
        audio=False, 
        preset="ultrafast",
        logger=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    
    # 2. Write master audio
    mixed_audio.write_audiofile(temp_aud, fps=44100, logger=None)
    
    # 3. Merge perfectly using FFMPEG directly
    import subprocess
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    # Map video from input 0, audio from input 1 explicitly to avoid silent track selection
    subprocess.run([
        ffmpeg_exe, "-y", "-i", temp_vid, "-i", temp_aud, 
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", output_video_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Cleanup temps
    try:
        os.remove(temp_vid)
        os.remove(temp_aud)
    except:
        pass
    
    if progress_cb: progress_cb(0.98, "Releasing local system file locks and saving database state...")
    try:
        mixed_audio.close()
        voice_audio.close()
        bg_clip.close()
        for tc in text_clips: tc.close()
        for ec in extra_clips: ec.close()
        for sc in sfx_clips: sc.close()
        for wc in transition_audio_clips: wc.close()
    except Exception:
        pass

    # B5/B9: release the per-cut segment readers, THEN delete the temp files
    # (deleting before close = the classic Windows "file in use" lock bug)
    for _sc in _seg_clips:
        try:
            _sc.close()
        except Exception:
            pass
    for _sf in _seg_files:
        _force_delete(_sf)
    # O2: free the frame buffers the render just held (batch mode = 5 in a row)
    gc.collect()
    # O1: keep the disk bounded (newest 12 videos, newest 400 b-roll clips)
    try:
        prune_output_dirs()
    except Exception:
        pass
        
    # PIECE 11 — auto thumbnail (same visual rules every upload)
    thumb_path = None
    try:
        hook_line = ""
        for _l in str(script_text).split("\n"):
            _l2 = _l.strip()
            if _l2 and not (_l2.startswith("[") and _l2.endswith("]")):
                hook_line = re.sub(r"\[.*?\]", "", _l2).strip()
                break
        # primary thumb = best-CTR variant so far (the template learns),
        # numbered sidecars for the other two so the user can A/B in Studio
        _primary = best_thumb_variant()
        thumb_path = generate_thumbnail(output_video_path, hook_line, accent_rgb=accent_rgb, variant=_primary)
        for _v in range(3):
            if _v != _primary:
                try:
                    generate_thumbnail(output_video_path, hook_line, accent_rgb=accent_rgb, variant=_v)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Thumbnail] skipped: {e}")

    if progress_cb: progress_cb(1.00, "Render complete!")
    log(f"RENDER DONE {os.path.basename(output_video_path)} in {time.time()-_render_t0:.0f}s thumb={os.path.basename(thumb_path) if thumb_path else 'none'}")
    # auto-backup the database (keeps the newest 3 daily snapshots)
    try:
        db_settings.backup_db()
    except Exception:
        pass
    return output_video_path, audio_path, vtt_path, thumb_path
