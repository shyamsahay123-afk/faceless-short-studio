import json
import requests
import re
import random

SYSTEM_PROMPT_BIBLE = """You are an elite YouTube Shorts AI Director (2026 Meta).
Your goal is to write a highly retaining, viral script for a Faceless channel operating in the 'dark luxury / psychology / self-improvement' niche.

MANDATORY RULES:
1. THE LOOPING STRUCTURE: The last sentence of the video MUST flow seamlessly back into the first sentence. 
2. PACED COUNTDOWN LISTS: Do NOT list things all at once. Present items sequentially. (e.g., "Number one: [Explain it for 5 seconds]. Number two: [Explain it]...").
3. 6TH GRADE READING LEVEL: Use punchy, active verbs. Short sentences. NO complex jargon.
4. ENGAGEMENT BAIT (THE DELIBERATE MISTAKE): Hide exactly ONE minor, deliberate mistake in the script (like a slight misspelling or a contradictory claim) that viewers will rush to the comments to correct.
5. NO EMOJIS: Do not use a single emoji in the script array. It breaks the renderer.
6. NO MEMES/JOKES: Keep the tone dark, serious, and luxurious. Zero cartoonish humor.
7. B-ROLL QUERIES: Provide 1 visual query per sentence/thought (4-6 seconds). They must be dark, cosmic, or abstract (e.g., "dark neurons firing", "vintage clock in the dark").

You MUST return ONLY a valid JSON object. No markdown formatting outside the JSON, no pleasantries.

JSON SCHEMA:
{
  "script": "The exact spoken text. No bracketed instructions. Just the words.",
  "b_roll_queries": ["dark galaxy", "vintage pocket watch", "stormy ocean night"],
  "seo": {
    "title": "Compelling Title With Curiosity Gap",
    "description": "2-3 sentence description.",
    "tags": "comma, separated, tags"
  },
  "thumbnail_prompt": "Describe a high-contrast, text-based thumbnail. e.g., 'Left side red text BROKE, right side green text AWAKE. Dark background.'"
}
"""

def call_groq_api(prompt, api_key, model="llama3-8b-8192"):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_BIBLE},
            {"role": "user", "content": f"Write a viral script about: {prompt}"}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[AI Director] Groq API Error: {e}")
        return None

def generate_smart_script(topic, api_key=None):
    if not api_key:
        print("[AI Director] No Groq API Key provided. Falling back to legacy template engine.")
        return None
        
    print("[AI Director] Consulting LLM for script, SEO, and visual pacing...")
    data = call_groq_api(topic, api_key)
    
    if data and "script" in data:
        return data
    return None
