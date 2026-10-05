import re

script = """
[0-3 sec HOOK]
99% of people get this entirely wrong. Here is the exact truth nobody talks about: How to overcome morning laziness.

[PSYCHOLOGY TRIGGER: Curiosity Gap]
Create an open loop in the first 2 seconds that makes the brain demand closure.

[VALUE DELIVERY]
Here is the exact neuroscience breakdown:
You call it thinking, but your brain calls it looping — every decision burns glucose you do not have [SOUND_DROP].
That is mistake number one. The second one is ten times worse. [MICRO_MEME: brain_overload]
Screens off ninety minutes before sleep. Your prefrontal cortex recovers overnight.
Run a strict 20-minute execution sprint every single day. Timer on, phone off.
Your phone sleeps in another room. Full stop. No exceptions tonight.
[SAVE_TRIGGER_LIST: Digital Sunset | 20m Execution Sprint | Phone Quarantine] and that is because...

[ENGAGEMENT CTA]
[Save this for your low-energy days. Follow for the system.]
"""

def clean_script_for_tts(raw_script):
    clean_text = str(raw_script)
    # Remove block headers like [0-3 sec HOOK], [VALUE DELIVERY], [ENGAGEMENT CTA]
    clean_text = re.sub(r'\[[A-Z0-9\-\s]+\]', '', clean_text)
    # Remove the psychology trigger header AND the sentence immediately following it
    clean_text = re.sub(r'\[PSYCHOLOGY TRIGGER:[^\]]+\]\s*(.*?)(\n\n|\Z)', '\n\n', clean_text, flags=re.DOTALL)
    # Remove micro memes and sound drops
    clean_text = re.sub(r'\[MICRO_MEME:[^\]]+\]', '', clean_text)
    clean_text = re.sub(r'\[SOUND_DROP\]', '', clean_text)
    # Remove save trigger lists
    clean_text = re.sub(r'\[SAVE_TRIGGER_LIST:[^\]]+\]', '', clean_text)
    # Remove bracketed CTA blocks
    clean_text = re.sub(r'\[.*?\]', '', clean_text)
    
    # Strip empty lines
    clean_text = "\n".join([line.strip() for line in clean_text.splitlines() if line.strip()])
    return clean_text

print(clean_script_for_tts(script))
