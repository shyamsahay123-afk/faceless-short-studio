# ==============================================================================
# SCRIPT ENGINE — topic -> (title, script, tags, trigger) + HOOK SCORECARD
# Lives outside app.py so daily.py (the CLI autopilot) can import it without
# starting Streamlit.
# ==============================================================================
import re
import random


# ------------------------------------------------------------------------------
# HOOK SCORECARD (pre-render quality gate — save 2.5 min of rendering a bad hook)
# Research consensus on Shorts hooks: 5-15 words, a number, "you", a curiosity
# gap, an interrupt opener, no emoji, assertive ending.
# ------------------------------------------------------------------------------
_GAP_WORDS = {
    "secret", "secrets", "hidden", "nobody", "no one", "truth", "wrong", "mistake",
    "lie", "stop", "never", "actually", "exposed", "reason", "why", "warning",
    "danger", "trap", "scam", "bizarre", "strange", "dark", "hidden rule",
    "nobody talks", "no one talks", "hides", "hiding", "uncomfortable",
}
_INTERRUPT_STARTS = (
    "stop", "never", "only", "why", "what", "when", "how", "the reason",
    "here", "you are", "you\u2019re", "most people", "everyone", "almost",
    "99%", "97%", "95%", "90%", "9 out", "1 in", "100%", "bad", "wrong",
)


def score_hook(hook_line):
    """Score a hook line 0-100 + a checklist. Used live in the UI and as a
    retry gate in daily.py (regenerate until the hook scores >= threshold)."""
    raw = str(hook_line or "")
    text = re.sub(r"\[.*?\]", "", raw).strip()
    text = re.sub(r"\[Topic\]|\[Niche\]", "the topic", text).strip()
    words = text.split()
    low = " " + text.lower() + " "
    if not words:
        return 0, [("Hook exists", False)]

    score = 0
    checks = []

    # 1) length (25)
    if 5 <= len(words) <= 15:
        score += 25
        checks.append((f"Length {len(words)} words (ideal 5-15)", True))
    elif 3 <= len(words) <= 20:
        score += 12
        checks.append((f"Length {len(words)} words (target 5-15)", False))
    else:
        checks.append((f"Length {len(words)} words (target 5-15)", False))

    # 2) a number (15) — concrete claims retain better
    if re.search(r"\d", text):
        score += 15
        checks.append(("Contains a number", True))
    else:
        checks.append(("Contains a number", False))

    # 3) addresses the viewer (15)
    if " you " in low or " your " in low or low.endswith(" you"):
        score += 15
        checks.append(("Speaks to 'you'", True))
    else:
        checks.append(("Speaks to 'you'", False))

    # 4) curiosity gap (25) or interrupt opener (10)
    has_gap = any(g in low for g in _GAP_WORDS)
    first = low.strip().split(" ")[0].strip(",.!?")
    has_interrupt = any(low.startswith(o) for o in _INTERRUPT_STARTS) or first in {"99%", "97%", "95%", "90%", "only", "stop", "never", "why", "what", "the"}
    if has_gap:
        score += 25
        checks.append(("Curiosity gap words", True))
    elif has_interrupt:
        score += 10
        checks.append(("Curiosity gap words (interrupt opener only)", False))
    else:
        checks.append(("Curiosity gap words", False))
    if has_interrupt:
        score += 10
        checks.append(("Pattern-interrupt opener", True))
    else:
        checks.append(("Pattern-interrupt opener", False))

    # 5) no emoji (10) — they read as spam in a premium niche
    if not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]", text):
        score += 10
        checks.append(("No emoji", True))
    else:
        checks.append(("No emoji", False))

    # 6) assertive ending (10)
    if text.endswith("?") or text.endswith("!"):
        score += 10
        checks.append(("Assertive ending", True))
    else:
        checks.append(("Assertive ending (ends .)", False))

    # 7) unsubstituted placeholder = fatal
    if "[Topic]" in raw or "[Niche]" in raw:
        return 0, [("Unsubstituted [Topic] placeholder — fatal", False)]

    return min(100, score), checks


def best_hook_line(script_text):
    """First content line (the actual hook)."""
    for l in str(script_text).split("\n"):
        ls = l.strip()
        if ls and not (ls.startswith("[") and ls.endswith("]")):
            return ls
    return ""


def generate_script_with_score(topic, style_choice, min_score=60, tries=6):
    """Retry the script generator until the hook scores >= min_score (or best of N).
    This is what daily.py uses — no more rendering weak hooks on autopilot."""
    best = None
    for _ in range(max(1, tries)):
        title, script, tags, trigger = auto_generate_script_local(topic, style_choice)
        if title == "Safety Warning":
            return title, script, tags, trigger, 0
        hook = best_hook_line(script)
        s, _checks = score_hook(hook)
        if best is None or s > best[4]:
            best = (title, script, tags, trigger, s)
        if s >= min_score:
            break
    return best


# ==============================================================================
# THE SCRIPT GENERATOR (moved verbatim from app.py — behavior unchanged)
# ==============================================================================
def auto_generate_script_local(topic, style_choice):
    topic_lower = str(topic).lower()
    if any(k in topic_lower for k in ["bomb", "terror", "explosive", "weapon", "child abuse", "abuse", "murder"]):
        return "Safety Warning", "[SCRIPT BLOCKED] For personal and algorithmic safety, content involving explosives, terrorism, or severe violence cannot be compiled. Please choose another creative topic!", "safety, warning", "Safety Block"
        
    if "Romance" in style_choice or "Intimacy" in style_choice:
        hook_category = "Romance & Intimacy"
        trigger_desc = "Connect directly with core emotional desires, chemistry secrets, and deep intimacy loops."
        hooks = [
            "9 out of 10 people understand this backwards. Here is the raw truth about [Topic] that nobody says out loud.",
            "There is a hidden rule of [Topic] the top 1% never break. It takes 30 minutes a night.",
            "What is the silent signal your brain sends when real chemistry starts? Psychologists have a name for it: [Topic].",
        ]
        value_delivery = """[VALUE DELIVERY]
Here is the raw relationship shift:
You chase temporary physical traits, BUT raw chemistry is about emotional safety, THEREFORE passive attraction fails [SOUND_DROP].
That is mistake number one. The second one is ten times worse [MICRO_MEME: romantic_focus].
Lock in undivided, focused attention for 30 minutes every single night.
[SAVE_TRIGGER_LIST: 1. Deep Presence | 2. 30m Intimacy Loop | 3. Absolute Trust]"""
        cta = "[Save this video so you don't lose it + Follow for daily elite frameworks ❤️]"
        
    elif "Dramatic" in style_choice:
        hook_category = "Curiosity Gap"
        trigger_desc = "Create an open loop in the first 2 seconds that makes the brain demand closure."
        hooks = [
            "99% of people get this entirely wrong. Here is the exact truth nobody talks about: [Topic].",
            "There is a hidden pattern behind [Topic] that intelligent people use before 6 AM. It takes only 20 minutes.",
            "What is the most dangerous habit your brain runs on? Scientists have a name for it. It starts with [Topic].",
        ]
        value_delivery = """[VALUE DELIVERY]
Here is the exact neuroscience breakdown:
You analyze too many variables, BUT this creates micro-friction, THEREFORE your prefrontal cortex shuts down [SOUND_DROP].
That is mistake number one. The second one is ten times worse [MICRO_MEME: brain_overload].
To stop overthinking, establish a strict 20-minute daily execution sprint.
[SAVE_TRIGGER_LIST: 1. Reduce Choice | 2. 20m Daily Sprint | 3. Morning Automation]"""
        cta = "[Save this video so you don't lose it + Follow for daily elite frameworks 📈]"
        
    elif "Motivational" in style_choice:
        hook_category = "Identity Signaling"
        trigger_desc = "Make the viewer feel they belong to a higher-status group (smart, disciplined, successful)."
        hooks = [
            "Only 1 in 100 people do this every single day. Here is the exact system: [Topic].",
            "Intelligent people don't rely on motivation. They use this hidden 20-minute rule instead.",
            "What separates the top 1% from everyone else? It's not talent. It's this one [Topic] system.",
        ]
        value_delivery = """[VALUE DELIVERY]
Here is the elite performance strategy:
Amateurs wait for motivation, BUT motivation is a fluctuating emotion, THEREFORE execution flatlines [SOUND_DROP].
That is mistake number one. The second one is ten times worse [MICRO_MEME: extreme_focus].
Lock yourself in a room with zero devices and write for 90 minutes.
[SAVE_TRIGGER_LIST: 1. Reject Motivation | 2. 90m Focus Lock | 3. Zero-Device Sprints]"""
        cta = "[Drop a 🔥 in the comments if you are executing this today!]"
        
    else:
        hook_category = "Loss Aversion"
        trigger_desc = "Highlight what the viewer will lose if they don’t act."
        hooks = [
            "You are losing 2 hours a day to this. Here is the exact fix nobody teaches you: [Topic].",
            "99% of people stay stuck because of one hidden trap. It's called [Topic] — and it's fixable in 3 steps.",
            "Every day you ignore this, your brain gets 1% weaker. The exact reason: [Topic].",
        ]
        value_delivery = """[VALUE DELIVERY]
Stop throwing away your focus:
Your phone is a slot machine, BUT every cheap scroll drains your dopamine, THEREFORE your attention span drops to zero [SOUND_DROP].
That is mistake number one. The second one is ten times worse [MICRO_MEME: dopamine_drain].
Move your phone to another room before you start your morning routine.
[SAVE_TRIGGER_LIST: 1. Phone is Slot Machine | 2. Dopamine Exhaustion | 3. Morning Phone Quarantine]"""
        cta = "[Save this video so you don't lose it + Follow for daily elite frameworks 📈]"
        
    selected_hook = random.choice(hooks)
    custom_hook = selected_hook.replace("[Topic]", topic).replace("[Niche]", topic).replace("[Role/Niche]", "performer").replace("[Role/Goal]", "leader").replace("[Bad Habit/Mistake]", "wasting focus").replace("[Money/Time/Health]", "focus")
    custom_hook = custom_hook.replace("[X]", "intelligence").replace("[Y]", "consistency").replace("[Key Strategy]", "Habit Automation")
    
    # Force clean, highly optimized infinite loop structures for max watch time metrics!
    first_word = custom_hook.split()[0].replace(".", "").replace(",", "").replace("?", "").replace("!", "").strip().lower()
    
    full_script = f"""[0-3 sec HOOK]\n{custom_hook}\n\n[PSYCHOLOGY TRIGGER: {hook_category}]\n{trigger_desc}\n\n{value_delivery} and that is because...\n\n[ENGAGEMENT CTA]\n{cta}"""
    title = f"{custom_hook[:45]}..." if len(custom_hook) > 45 else custom_hook
    tags = f"{topic.lower().replace(' ', '')}, shorts, viral, psychology, {hook_category.lower().replace(' ', '')}"
    
    return title, full_script, tags, hook_category


# ==============================================================================
# THE TRICK DIRECTOR — psychology tricks system (spec: psychology_tricks.md)
# "Indirectly signal that this channel holds secrets and power" +
# comment-trigger mechanics (the planted-flaw principle, systematized).
# Frequency rules matter more than the tricks: a trick used every video
# dies by video 8. Rotation state is derived from the video id (deterministic).
# ==============================================================================
TRICK_GATEKEEPER = [
    "99% of people will close this in the next ten seconds. That is the point.",
    "If this found you, you have been feeling this for months.",
    "Most people will skip the next part. Do not.",
]
TRICK_QUESTION_CTA = [
    "Comment it: which one were you, day one or year one?",
    "Sound off below: is this your morning or your night?",
    "Tell me in the comments, what is your version of this?",
]
TRICK_EXCLUSIVE_CLOSE = [
    "You did not find this video by accident.",
    "Most people will never see this. Save it before it is gone.",
]
TRICK_DEBATE_BEAT = [
    "Early risers are just anxious people with a routine.",
    "Motivational quotes are for people who cannot build systems.",
    "Multitasking is what happens when focus dies.",
]
NAMED_SECRET_POOL = [
    "the dopamine tax", "micro-friction", "the twenty minute loop", "the attention debt",
    "the willpower tax", "the friction trap", "the reward loop", "the focus leak",
]
# A1 planted flaw: near-miss spellings (must be *almost* right so the fix is easy)
FLAW_SWAPS = {
    "discipline": "discpline", "dopamine": "dompamine", "habit": "habbit",
    "focus": "foucs", "secret": "secert", "brain": "bran", "success": "sucess",
}
# A5 planted wrong answer — nuance zone only (never something harmful)
WRONG_ANSWER_LINE = "The prefrontal cortex makes all of your decisions."


def choose_tricks(video_id):
    """Deterministic trick selection per video id (rotation memory)."""
    vid = int(video_id)
    baits = ["open_question", "hidden_detail", "debate_split"]
    return {
        "named_secret": NAMED_SECRET_POOL[vid % len(NAMED_SECRET_POOL)],
        "bait": baits[vid % len(baits)],
        "flaw": (vid % 10 == 7),          # A1: one planted flaw per ~10 videos
        "wrong_answer": (vid % 15 == 11),  # A5: one planted wrong answer per ~15
    }


def apply_tricks_to_script(script_text, video_id):
    """Mutate the script with the chosen tricks. Returns (new_script, tricks_used).
    Rules: named secret goes after the first content line; the flaw hits a
    LATER line (never the hook); the CTA bait replaces the last content line;
    the debate beat lands mid-value."""
    t = choose_tricks(video_id)
    lines = str(script_text).split("\n")
    is_content = lambda l: bool(l.strip()) and not (l.strip().startswith("[") and l.strip().endswith("]"))
    content_idx = 0
    content_positions = [i for i, l in enumerate(lines) if is_content(l)]
    new_lines = list(lines)

    if content_positions:
        # B2 — the named secret (the core trick): one concept, one name, every video
        first_i = content_positions[0]
        new_lines[first_i] = lines[first_i] + f" There is a name for this. It is called {t['named_secret']}."

        # A1 — planted flaw on the 2nd content line (only if the word exists)
        if t["flaw"] and len(content_positions) > 1:
            i = content_positions[1]
            low = lines[i].lower()
            for good, bad in FLAW_SWAPS.items():
                if good in low:
                    new_lines[i] = lines[i].replace(good, bad) if good in lines[i] else lines[i].replace(good.capitalize(), bad)
                    break

        # A5 — planted wrong answer on the 3rd content line
        if t["wrong_answer"] and len(content_positions) > 2:
            i = content_positions[2]
            new_lines[i] = lines[i] + " " + WRONG_ANSWER_LINE

        # A4 — debate split: appended to the middle content line
        # (append to new_lines so it stacks on top of any earlier mutation)
        if t["bait"] == "debate_split" and len(content_positions) > 2:
            i = content_positions[len(content_positions) // 2]
            new_lines[i] = new_lines[i] + " " + TRICK_DEBATE_BEAT[int(video_id) % len(TRICK_DEBATE_BEAT)]

        # A2/B6 — CTA baits replace the LAST content line
        last_i = content_positions[-1]
        if t["bait"] == "open_question":
            new_lines[last_i] = TRICK_QUESTION_CTA[int(video_id) % len(TRICK_QUESTION_CTA)]
        elif t["bait"] == "exclusive_close":
            new_lines[last_i] = TRICK_EXCLUSIVE_CLOSE[int(video_id) % len(TRICK_EXCLUSIVE_CLOSE)]
        # 'hidden_detail' bait = no script change (the 1-frame code flash does the work)

    return "\n".join(new_lines), t
