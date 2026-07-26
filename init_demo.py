import db_manager as db
import video_engine as video
import os

def create_stunning_demo_short():
    # 1. Add Channel
    channels = db.get_all_channels()
    if not channels:
        db.add_channel("Elite Mindset Shorts", "Self Improvement & Psychology", "12.4k")
        channels = db.get_all_channels()
    
    ch_id = channels[0][0]
    ch_niche = channels[0][2]
    
    # 2. Add Short Idea
    title = "The Bizarre Secret to Unstoppable Consistency 🎯"
    script = """[0-3 sec HOOK]
Why do 99% of people fail to stay consistent with their goals? The answer will shock you.

[PSYCHOLOGY TRIGGER: Curiosity Gap]
Create an open loop in the first 2 seconds that makes the brain demand closure.

[VALUE DELIVERY]
It has nothing to do with willpower.
It is entirely about cognitive friction.
Step 1: Eliminate the #1 friction point immediately.
Step 2: Lock in for 90 minutes deep work every morning.
Top performers automate their habits so they never have to think.

[ENGAGEMENT CTA]
Drop a 🔥 in the comments if you are executing this today!"""
    
    trigger = "Curiosity Gap"
    description = f"""{title}\n\nStop relying on willpower. Here is the exact psychology breakdown on how elite top performers stay relentless every single day.\n\n#SelfImprovement #Psychology #Shorts"""
    tags = "selfimprovement, psychology, consistency, mindset, shorts, viral"
    
    short_id = db.add_short(ch_id, title, script, trigger, description, tags, status='idea')
    print(f"Demo Short added with ID: {short_id}")
    
    # 3. Compile actual HD video
    bg_asset = "default_assets/bg_curiosity.jpg"
    print("Compiling professional 9:16 vertical video...")
    v_path, a_path, vtt_path = video.create_video_from_script(
        short_id,
        script,
        bg_asset,
        voice_name="en-US-ChristopherNeural",
        font_color="yellow"
    )
    
    db.update_short_video(short_id, v_path, a_path, vtt_path, status='created')
    print("✨ Fantastic! Stunning demo short compiled successfully and stored in the database!")

if __name__ == "__main__":
    create_stunning_demo_short()
