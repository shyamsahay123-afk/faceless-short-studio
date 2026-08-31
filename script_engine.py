# ==============================================================================
# SCRIPT ENGINE — topic -> (title, script, tags, trigger) + HOOK SCORECARD
# Lives outside app.py so daily.py (the CLI autopilot) can import it without
# starting Streamlit.
# ==============================================================================
import re
import json
import time
import random
import db_manager as db_settings


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
        title, script, tags, trigger_data = auto_generate_script_local(topic, style_choice)
        trigger = "AI Director" if isinstance(trigger_data, dict) else trigger_data
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

import os
import ai_director

def auto_generate_script_local(topic, style_choice):
    topic_lower = str(topic).lower()
    if any(k in topic_lower for k in ["bomb", "terror", "explosive", "weapon", "child abuse", "abuse", "murder"]):
        return "Safety Warning", "[SCRIPT BLOCKED] For personal and algorithmic safety, content involving explosives, terrorism, or severe violence cannot be compiled. Please choose another creative topic!", "safety, warning", "Safety Block"
        
    groq_key_path = os.path.join(os.path.dirname(__file__), "groq_key.txt")
    groq_key = None
    if os.path.exists(groq_key_path):
        groq_key = open(groq_key_path, "r", encoding="utf-8").read().strip()
        
    if groq_key:
        print("[ScriptEngine] Groq Key found! Routing to AI Director (LLM)...")
        ai_data = ai_director.generate_smart_script(topic, groq_key)
        if ai_data:
            title = ai_data.get("seo", {}).get("title", topic)
            script = ai_data.get("script", "Fallback script")
            tags = ai_data.get("seo", {}).get("tags", "shorts, viral")
            
            # Save the extended data to the script text temporarily or side-load it?
            # It's cleaner to return it, but that breaks the tuple unpacking in app.py.
            # Let's attach the thumbnail prompt and seo description to the tags or trigger string
            # to avoid breaking app.py signatures, or just update app.py too.
            # Let's update app.py tuple unpacking!
            return title, script, tags, ai_data
            
    print("[ScriptEngine] No Groq Key or API failed. Falling back to template engine...")
    return legacy_generate_script(topic, style_choice)
    
def legacy_generate_script(topic, style_choice):

    """SCRIPT COMPOSER (v2) — replaces the old 4-template generator.
    The old code had ONE hardcoded body per style: video #1 and video #100
    read the same paragraph. Now every video is COMPOSED from per-style
    pools (problems, mechanisms, turns, solutions, save-lists, CTAs, hooks)
    with a no-repeat memory (last 30 compositions stored in the db)."""
    topic_lower = str(topic).lower()
    if any(k in topic_lower for k in ["bomb", "terror", "explosive", "weapon", "child abuse", "abuse", "murder"]):
        return "Safety Warning", "[SCRIPT BLOCKED] For personal and algorithmic safety, content involving explosives, terrorism, or severe violence cannot be compiled. Please choose another creative topic!", "safety, warning", "Safety Block"

    if "Romance" in style_choice or "Intimacy" in style_choice:
        key, hook_category = "romance", "Romance & Intimacy"
    elif "Dramatic" in style_choice:
        key, hook_category = "dramatic", "Curiosity Gap"
    elif "Motivational" in style_choice:
        key, hook_category = "motivation", "Identity Signaling"
    else:
        key, hook_category = "focus", "Loss Aversion"

    P = STYLE_POOLS[key]
    seed = _next_script_seed(topic)
    memory = _load_script_memory()

    # compose without repeating any recent (problem, mechanism, solution-triple)
    h_i = p_i = m_i = t_i = c_i = op_i = None
    sols = None
    fp = None
    for attempt in range(8):
        rng = random.Random(f"script:{seed}:{attempt}")
        h_i = rng.randrange(len(P["hooks"]))
        op_i = rng.randrange(len(P["openers"]))
        p_i = rng.randrange(len(P["problems"]))
        m_i = rng.randrange(len(P["mechanisms"]))
        t_i = rng.randrange(len(P["turns"]))
        c_i = rng.randrange(len(P["ctas"]))
        sols = rng.sample(P["solutions"], 3)
        fp = _fp_key(key, p_i, m_i, sols)
        if fp not in memory:
            break
    _remember_script(fp, memory)

    hooks = [h.replace("[Topic]", str(topic)).replace("[Niche]", str(topic))
             .replace("[Role/Niche]", "performer").replace("[Role/Goal]", "leader")
             .replace("[Bad Habit/Mistake]", "wasting focus").replace("[Money/Time/Health]", "focus")
             .replace("[X]", "intelligence").replace("[Y]", "consistency")
             .replace("[Key Strategy]", "Habit Automation") for h in P["hooks"]]
    hook = hooks[h_i]
    meme = P["meme"]

    solutions = [s[1].replace("[Topic]", str(topic)) for s in sols]
    labels = [s[0] for s in sols]

    full_script = f"""[0-3 sec HOOK]
{hook}


[VALUE DELIVERY]
{P["openers"][op_i]}
{P["problems"][p_i]} — {P["mechanisms"][m_i]} [SOUND_DROP].
{P["turns"][t_i]} [MICRO_MEME: {meme}]
{solutions[0]}
{solutions[1]}
{solutions[2]}
[SAVE_TRIGGER_LIST: {labels[0]} | {labels[1]} | {labels[2]}] and that is because...

[ENGAGEMENT CTA]
{P["ctas"][c_i]}"""

    title = f"{hook[:45]}..." if len(hook) > 45 else hook
    tags = f"{str(topic).lower().replace(' ', '')}, shorts, viral, psychology, {hook_category.lower()}"
    return title, full_script, tags, hook_category


# ==============================================================================
# STYLE POOLS — the composer's raw material. Every video draws from these with
# a per-video seed + the no-repeat memory, so bodies never repeat in 30 videos.
# ==============================================================================
STYLE_POOLS = {
"dramatic": {
    "trigger_desc": "Create an open loop in the first 2 seconds that makes the brain demand closure.",
    "meme": "brain_overload",
    "hooks": [
        "99% of people get this entirely wrong. Here is the exact truth nobody talks about: [Topic].",
        "There is a hidden pattern behind [Topic] that intelligent people use before 6 AM. It takes only 20 minutes.",
        "What is the most dangerous habit your brain runs on? Scientists have a name for it. It starts with [Topic].",
        "Your brain is running a script you never approved. It is called [Topic], and it is quiet.",
        "Nobody warns you about [Topic]. By the time you notice it, it has already decided your day.",
        "If your focus feels broken, it is not. [Topic] is working exactly as designed.",
        "The smartest people you know have one habit in common. It is not discipline. It is [Topic].",
        "You have been told [Topic] is about willpower. That is the most expensive lie in psychology.",
    ],
    "openers": [
        "Here is the exact neuroscience breakdown:",
        "Here is what is actually happening in your head:",
        "Here is the mechanism, in plain words:",
        "Here is the loop your brain is running:",
        "Here is the cost, measured:",
        "Here is the pattern, stripped of the fluff:",
        "Here is what the research actually says:",
        "Here is the real cost of the habit:",
    ],
    "problems": [
        "You analyze too many variables",
        "You call it thinking, but your brain calls it looping",
        "You think you are preparing, but you are actually hiding",
        "You treat every option like it matters, but most of them cancel out",
        "You wait for motivation to start, but it only arrives after the first rep",
        "You collect strategies like trophies, but none of them execute you",
        "You scroll for answers, but the scroll is the problem",
        "You plan the perfect start, but the perfect start is a myth",
        "You believe you need more information, but you need less noise",
        "You protect your time, but you keep handing it to the feed",
    ],
    "mechanisms": [
        "this creates micro-friction and your prefrontal cortex shuts down",
        "every decision burns glucose you do not have",
        "attention residue follows you into the next task",
        "the default mode network hijacks your focus",
        "your reward prediction error keeps you on the feed",
        "working memory drowns in open loops",
        "your dopamine baseline resets to cheap and fast",
        "execution dies in the gap between thought and action",
    ],
    "turns": [
        "That is mistake number one. The second one is ten times worse.",
        "That is the trap. And it gets worse at night.",
        "Most people stop here. The ones who escape do one thing differently.",
        "That is the loop. Breaking it takes less than you think.",
        "This is where the average person quits. Keep going.",
        "And here is the part nobody warns you about.",
    ],
    "solutions": [
        ("Reduce Choice", "Cut your daily decisions in half. One outfit. One breakfast. One path."),
        ("20m Execution Sprint", "Run a strict 20-minute execution sprint every single day. Timer on, phone off."),
        ("Morning Automation", "Automate the first 60 minutes of your day. No choices before noon."),
        ("Dopamine Detox Hour", "Give your brain one screen-free hour a day. Boredom is the reset."),
        ("2-Minute Rule", "If it takes under two minutes, do it now. Everything else gets scheduled."),
        ("Phone Quarantine", "Your phone sleeps in another room. Full stop. No exceptions tonight."),
        ("Single-Task Window", "One task, one tab, ninety minutes. Nothing else exists in that window."),
        ("Evening Shutdown", "Run a 10-minute shutdown ritual that closes every open loop before bed."),
        ("Friction Design", "Add friction to the bad habit. Remove it from the good one. That is the whole system."),
        ("Identity Repetition", "Repeat the action until the identity catches up. You are not doing it. You are being it."),
        ("Boredom Block", "Schedule boredom on purpose. Your brain solves problems when you stop feeding it noise."),
        ("Digital Sunset", "Screens off ninety minutes before sleep. Your prefrontal cortex recovers overnight."),
    ],
    "ctas": [
        "[Save this video so you don't lose it + Follow for daily elite frameworks 📈]",
        "[Save this before it disappears + Follow. One framework a day, no fluff.]",
        "[If this hit different, save it. Follow for the next one.]",
        "[Save it. Screenshot it. Do it tomorrow. Follow for daily.]",
        "[The next video breaks mistake number two. Follow so you do not miss it.]",
        "[Save this for your low-energy days. Follow for the system.]",
    ],
},
"focus": {
    "trigger_desc": "Highlight what the viewer will lose if they do not act. Quantify the leak.",
    "meme": "dopamine_drain",
    "hooks": [
        "You are losing 2 hours a day to this. Here is the exact fix nobody teaches you: [Topic].",
        "99% of people stay stuck because of one hidden trap. It's called [Topic] — and it's fixable in 3 steps.",
        "Every day you ignore this, your brain gets 1% weaker. The exact reason: [Topic].",
        "Your attention is the most expensive asset you own. [Topic] is how it leaks.",
        "You do not have a focus problem. You have a [Topic] problem. There is a difference.",
        "The average person checks their phone 58 times a day. [Topic] is how to cut it in half.",
        "Nobody is coming to save your attention. Here is the [Topic] protocol.",
        "You will never find 2 extra hours. You will find them inside the [Topic] fix.",
    ],
    "openers": [
        "Here is where the hours actually go:",
        "Here is the leak, mapped:",
        "Here is the fix, in order:",
        "Here is what protects your attention:",
        "Here is the protocol:",
        "Here is the math nobody shows you:",
    ],
    "problems": [
        "Your phone is a slot machine",
        "Every cheap scroll drains dopamine",
        "You switch tasks 47 times a day",
        "You protect your calendar but not your attention",
        "You confuse busyness with progress",
        "You start everything and finish nothing",
        "You wait for calm instead of building it",
        "You give your best hours to other people's systems",
    ],
    "mechanisms": [
        "every interruption costs 23 minutes of real focus",
        "your attention span shrinks with every cheap reward",
        "context switching taxes working memory",
        "the feed is engineered to defeat your prefrontal cortex",
        "unfinished loops keep the brain in low-grade alarm",
        "busyness feels like output but it is not",
        "willpower is a budget, and you are overdrawing it",
        "calm is a byproduct of structure, not a mood",
    ],
    "turns": [
        "That is the leak. Here is the plug.",
        "That is the cost. The fix is cheaper than the damage.",
        "That is the trap door. Close it in 3 steps.",
        "That is the math. Now the protocol.",
        "That is the drain. Here is the shutoff valve.",
        "That is the hole in the bucket. Fix the bucket first.",
    ],
    "solutions": [
        ("Phone Quarantine", "Your phone sleeps in another room. Full stop. No exceptions tonight."),
        ("20m Execution Sprint", "Run a strict 20-minute execution sprint every single day. Timer on, phone off."),
        ("Morning Automation", "Automate the first 60 minutes of your day. No choices before noon."),
        ("Single-Task Window", "One task, one tab, ninety minutes. Nothing else exists in that window."),
        ("Boredom Block", "Schedule boredom on purpose. Your brain solves problems when you stop feeding it noise."),
        ("Digital Sunset", "Screens off ninety minutes before sleep. Your prefrontal cortex recovers overnight."),
        ("Reduce Choice", "Cut your daily decisions in half. One outfit. One breakfast. One path."),
        ("Evening Shutdown", "Run a 10-minute shutdown ritual that closes every open loop before bed."),
        ("Friction Design", "Add friction to the bad habit. Remove it from the good one. That is the whole system."),
        ("2-Minute Rule", "If it takes under two minutes, do it now. Everything else gets scheduled."),
    ],
    "ctas": [
        "[Save this video so you don't lose it + Follow for daily elite frameworks 📈]",
        "[The 2-hour leak ends today. Save it. Follow for the next plug.]",
        "[Save it for the next time you feel the drain. Follow for daily.]",
        "[Your attention is the asset. Protect it. Save + Follow.]",
        "[The next video shows the shutdown ritual. Follow so you get it.]",
        "[Save this for your low-energy days. Follow for the system.]",
    ],
},
"motivation": {
    "trigger_desc": "Make the viewer feel they belong to a higher-status group (smart, disciplined, successful).",
    "meme": "extreme_focus",
    "hooks": [
        "Only 1 in 100 people do this every single day. Here is the exact system: [Topic].",
        "Intelligent people don't rely on motivation. They use this hidden 20-minute rule instead.",
        "What separates the top 1% from everyone else? It's not talent. It's this one [Topic] system.",
        "The top 1% do not feel ready. They do the [Topic] system anyway. That is the whole secret.",
        "Discipline is not a personality trait. It is a [Topic] protocol. Here it is.",
        "You are one system away from the person you wanted to be last January. It is [Topic].",
        "Motivation is a gas station, not a highway. [Topic] is the engine.",
        "The gap between you and the top 1% is not talent. It is [Topic].",
    ],
    "openers": [
        "Here is the system, step by step:",
        "Here is what the top 1% actually do:",
        "Here is the identity shift:",
        "Here is the protocol:",
        "Here is the standard:",
        "Here is the playbook:",
    ],
    "problems": [
        "You wait for motivation to start",
        "You rely on how you feel",
        "You set goals but no standards",
        "You chase big wins and skip tiny reps",
        "You admire the top 1% but copy their lifestyle, not their systems",
        "You quit at the exact moment it gets boring",
        "You measure output, but the top 1% measure reps",
        "You want results this week but refuse reps this month",
    ],
    "mechanisms": [
        "motivation is a fluctuating emotion, so execution flatlines",
        "feelings are weather, and weather does not build anything",
        "goals without standards evaporate under pressure",
        "the brain rewards repetition, not intention",
        "you copy outcomes you cannot sustain because you skipped the reps",
        "boredom is the filter that keeps average people average",
        "identity follows action, and action follows a system",
        "small reps compound into a reputation",
    ],
    "turns": [
        "That is the gap. Here is the bridge.",
        "That is the excuse. Here is the replacement.",
        "That is the lie. Here is the standard.",
        "That is the shortcut that is not one. Here is the real one.",
        "That is where most people stop. Do not.",
        "That is the bottleneck. Here is how the top 1% removes it.",
    ],
    "solutions": [
        ("20m Execution Sprint", "Run a strict 20-minute execution sprint every single day. Timer on, phone off."),
        ("Morning Automation", "Automate the first 60 minutes of your day. No choices before noon."),
        ("Identity Repetition", "Repeat the action until the identity catches up. You are not doing it. You are being it."),
        ("Reduce Choice", "Cut your daily decisions in half. One outfit. One breakfast. One path."),
        ("Single-Task Window", "One task, one tab, ninety minutes. Nothing else exists in that window."),
        ("Evening Shutdown", "Run a 10-minute shutdown ritual that closes every open loop before bed."),
        ("Phone Quarantine", "Your phone sleeps in another room. Full stop. No exceptions tonight."),
        ("Boredom Block", "Schedule boredom on purpose. The boring rep is the winning rep."),
    ],
    "ctas": [
        "[Drop a 🔥 in the comments if you are executing this today!]",
        "[Comment the first rep you will do today. Then do it. Follow for daily.]",
        "[Save this and run the first sprint today. Follow for the system.]",
        "[You are in the 1% for reading this far. Act like it. Save + Follow.]",
        "[The next video is the 90-minute window. Follow so you get it.]",
        "[Standards over goals. Save this. Follow for daily.]",
    ],
},
"romance": {
    "trigger_desc": "Connect directly with core emotional desires, chemistry secrets, and deep intimacy loops.",
    "meme": "romantic_focus",
    "hooks": [
        "9 out of 10 people understand this backwards. Here is the raw truth about [Topic] that nobody says out loud.",
        "There is a hidden rule of [Topic] the top 1% never break. It takes 30 minutes a night.",
        "What is the silent signal your brain sends when real chemistry starts? Psychologists have a name for it: [Topic].",
        "Real chemistry is not a spark. It is a [Topic] system, and it is learnable.",
        "You do not attract what you want. You attract what you are safe enough to show. That is [Topic].",
        "The people who seem effortless at love are running a hidden protocol. It is called [Topic].",
        "Intimacy is not a mood. It is a [Topic] practice. Here is the practice.",
        "Most people mistake intensity for intimacy. [Topic] is the difference.",
    ],
    "openers": [
        "Here is the raw relationship shift:",
        "Here is what chemistry actually runs on:",
        "Here is the intimacy protocol:",
        "Here is the difference, precisely:",
        "Here is the hidden rule, plainly:",
        "Here is the practice, step by step:",
    ],
    "problems": [
        "You chase temporary physical traits",
        "You mistake intensity for intimacy",
        "You perform instead of showing up",
        "You scroll for chemistry instead of building it",
        "You wait to be chosen instead of choosing presence",
        "You confuse availability with attention",
        "You optimize the conversation and starve the silence",
        "You protect your heart by going shallow",
    ],
    "mechanisms": [
        "raw chemistry is about emotional safety, so passive attraction fails",
        "the nervous system reads safety before it reads desire",
        "performance raises cortisol and kills the very warmth you want",
        "the feed trains you to collect options instead of building depth",
        "being chosen is a prize, presence is a practice",
        "availability without attention feels like indifference",
        "talking fills silence, but intimacy lives inside it",
        "shallow keeps you safe and keeps you lonely at the same time",
    ],
    "turns": [
        "That is the trap. The fix is 30 minutes a night.",
        "That is the mistake. Here is the correction.",
        "That is the shallow loop. Here is the deep one.",
        "That is the pattern. Here is the break.",
        "That is the wall. Here is the door.",
        "That is the habit. Here is the practice.",
    ],
    "solutions": [
        ("30m Intimacy Loop", "Thirty undivided minutes a night. Phones face down. Eyes present. That is the whole loop."),
        ("Deep Presence", "Give one full conversation without planning your next line. Presence is the signal."),
        ("Recall Ritual", "Ask one real question a day and remember the answer. Recall is the quiet form of desire."),
        ("Touch Anchor", "One intentional, non-sexual touch a day. The nervous system logs it as safety."),
        ("Vulnerability Window", "Share one real thing before you perform one impressive thing. Reverse the ratio."),
        ("Curiosity Protocol", "Ask about the feeling, not the facts. Feelings are where intimacy lives."),
        ("Digital Sunset", "Screens off ninety minutes before sleep. You cannot be present on a dead battery."),
        ("Reduce Choice", "Cut the daily noise in half so the evening has room to breathe."),
    ],
    "ctas": [
        "[Save this video so you don't lose it + Follow for daily elite frameworks ❤️]",
        "[Save it for tonight. Do the 30 minutes. Follow for the next practice.]",
        "[If this felt true, save it. Follow for daily.]",
        "[Intimacy is a practice, not a luck draw. Save + Follow.]",
        "[The next video is the recall ritual. Follow so you get it.]",
        "[Do one of these tonight. Save + Follow for daily.]",
    ],
},
}


def _next_script_seed(topic):
    """Monotonic counter in the db: composition seeds are unique across
    sessions, so two renders of the same topic are never the same video."""
    try:
        c = int(db_settings.get_setting("script_counter", 0)) + 1
        db_settings.set_setting("script_counter", c)
        return c
    except Exception:
        return int(time.time() * 1000)


def _fp_key(key, p_i, m_i, sols):
    """Hashable, JSON-safe fingerprint of a composition."""
    return f"{key}|{p_i}|{m_i}|{'-'.join(sorted(s[0] for s in sols))}"


def _load_script_memory():
    try:
        raw = db_settings.get_setting("script_memory", "[]")
        return set(json.loads(raw))
    except Exception:
        return set()


def _remember_script(fp, memory):
    try:
        memory.add(fp)
        db_settings.set_setting("script_memory", json.dumps(list(memory)[-30:]))
    except Exception:
        pass


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
