# YouTube SEO & Viral metadata Engine (Fully automated, zero OAuth linking, 100% foolproof)

def generate_viral_seo_pack(title, spoken_script, niche, trigger):
    """
    Generates the ultimate algorithmic SEO copy pack for YouTube Shorts, TikTok, and Reels.
    Completely bulletproof against None or empty variables.
    """
    if not title: title = "Elite Psychology Secret 🎯"
    if not spoken_script: spoken_script = "Discover the ultimate digital mindset shift."
    if not niche: niche = "Mindset Domain"
    if not trigger: trigger = "Curiosity Mechanism"

    # Safely format variables
    niche_clean = str(niche).replace(" ", "").replace("&", "").replace("-", "").strip()
    trigger_clean = str(trigger).replace(" ", "").strip()

    base_tags = [str(niche).lower(), "shorts", "viral", "psychology", str(trigger).lower()]
    extra_tags = ["how to", "mindset", "success tips", "life hacks", "motivation", "secret", niche_clean.lower()]
    all_tags = list(set([t.strip() for t in (base_tags + extra_tags) if t.strip()]))
    
    tags_str = ", ".join(all_tags)
    hashtags_str = f"#{niche_clean} #Shorts #ViralVideo #Psychology #{trigger_clean} #Success"

    optimized_title = f"{str(title)[:85]} 🎯" if not str(title).strip().endswith("🎯") else str(title)[:90]

    optimized_desc = f"""{optimized_title}

{spoken_script}

Here is exactly why this psychology secret works:
When you use the [{trigger}] mechanism, you build undeniable leverage in {niche}. Stop acting like amateur performers—build an elite future today.

🔔 Hit Subscribe to join the top 1% dominating {niche}!

{hashtags_str}"""

    return {
        "title": optimized_title,
        "description": optimized_desc,
        "tags": tags_str,
        "hashtags": hashtags_str
    }
