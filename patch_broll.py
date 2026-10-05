import sys

with open('video_engine.py', 'r') as f:
    content = f.read()

# We need to add a state tracker for recently used broll categories.
new_broll_logic = """
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
    import zlib
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

"""

# Patching expand_keyword_to_concept
if "# --- KEYWORD EXTRACTOR FOR AUTOMATED B-ROLL SEARCH ---" in content:
    content = content.replace("# --- KEYWORD EXTRACTOR FOR AUTOMATED B-ROLL SEARCH ---", new_broll_logic + "# --- KEYWORD EXTRACTOR FOR AUTOMATED B-ROLL SEARCH ---")

# Patching the fallback logic in get_b_roll
content = content.replace(
    'expanded = COSMIC_POOL[zlib.crc32(str(query).encode("utf-8")) % len(COSMIC_POOL)]',
    'expanded = get_variety_cosmic_concept(query)'
)

with open('video_engine.py', 'w') as f:
    f.write(content)

print("Patched video_engine.py with variety engine")
