import os, requests, json, subprocess, gc, random, socket, math
import urllib.parse
import urllib3.util.connection as urllib3_cn
import moviepy.editor as mpe
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, TextClip
import moviepy.video.fx.all as vfx

# 🛡️ HACKER TRICK: Force IPv4 to bypass Hostinger blocks
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# --- Configuration ---
chat_id = os.environ.get('CHAT_ID')
pexels_key = os.environ.get('PEXELS_API_KEY')
scenes_data = json.loads(os.environ.get('SCENES_DATA', '[]'))
resume_url = os.environ.get('RESUME_URL')

video_title = os.environ.get('TITLE', 'Android Tricks Video')
thumbnail_prompt = os.environ.get('THUMBNAIL_PROMPT', 'Cinematic tech thumbnail')
video_desc = os.environ.get('DESCRIPTION', 'Android tips and tricks video.')
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8606637548:AAFP7W0koQcXtK1cHNS9pSOorojvSq4fRTg')

TARGET_W, TARGET_H = 1920, 1080
HINDI_FONT_FILE = "Hindi.ttf"

used_videos = set()
video_files = []
audio_files = []
last_successful_media = None  

print(f"Total Scenes to render: {len(scenes_data)}")

def get_pexels_video(query):
    try:
        search_terms = [query, query.split(" ")[-1] if " " in query else query, "smartphone", "technology"]
        for term in search_terms:
            res = requests.get(f"https://api.pexels.com/videos/search?query={urllib.parse.quote(term)}&per_page=15&orientation=landscape", headers={"Authorization": pexels_key}, timeout=15).json()
            if res.get('videos'):
                for v in res['videos']:
                    high_res_files = sorted(v['video_files'], key=lambda x: x.get('width', 0), reverse=True)
                    for vf in high_res_files:
                        if vf['link'] not in used_videos:
                            used_videos.add(vf['link'])
                            return vf['link']
    except: pass
    return None

for i, scene in enumerate(scenes_data):
    keyword = scene.get('keyword', 'smartphone').strip()
    image_prompt = scene.get('image_prompt', keyword).strip()
    text_line = scene.get('text', ' ').strip() or " "

    # --- 1. Audio Pipeline ---
    raw_audio_path = f"raw_audio_{i}.mp3"
    norm_audio_path = f"audio_{i}.wav"
    subprocess.run(['edge-tts', '--voice', 'hi-IN-MadhurNeural', '--text', text_line, '--write-media', raw_audio_path], check=False)

    if os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 100:
        try:
            audio_filter = "silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-35dB,bass=g=5:f=110,treble=g=3:f=8000"
            subprocess.run(['ffmpeg', '-y', '-i', raw_audio_path, '-af', audio_filter, '-ar', '44100', '-ac', '2', norm_audio_path], check=True)
            out = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', norm_audio_path])
            # 🔥 FIX 1: Removed +0.2 to perfectly match Global Audio & Video Length
            scene_duration = float(out.decode('utf-8').strip()) 
        except:
            scene_duration = 3.0
            subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(scene_duration), norm_audio_path], check=True)
    else:
        scene_duration = 3.0
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(scene_duration), norm_audio_path], check=True)

    final_audio_path = norm_audio_path
    if os.path.exists("whoosh.mp3") and i > 0:
        mixed_audio = f"mixed_audio_{i}.wav"
        try:
            subprocess.run(['ffmpeg', '-y', '-i', norm_audio_path, '-i', 'whoosh.mp3', '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]', '-map', '[aout]', '-ar', '44100', '-ac', '2', mixed_audio], check=True)
            final_audio_path = mixed_audio
        except: pass

    audio_files.append(final_audio_path)

    # --- 2. Visual Pipeline ---
    video_url = get_pexels_video(keyword)
    norm_video_path = f"video_{i}.mp4"
    raw_media_path = f"raw_media_{i}.mp4"
    word_clips = []
    
    try:
        if video_url:
            req = requests.get(video_url, timeout=45)
            with open(raw_media_path, "wb") as f: f.write(req.content)
            vclip = VideoFileClip(raw_media_path).fx(vfx.speedx, 1.2)
            vclip = vclip.fx(vfx.loop, duration=scene_duration) if vclip.duration < scene_duration else vclip.subclip(0, scene_duration)
            last_successful_media = {"type": "video", "path": raw_media_path}
        else:
            raw_media_path = f"raw_media_{i}.jpg"
            img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(f'Cinematic concept art, {image_prompt}, 8k, Unreal Engine 5')}?width=1920&height=1080&nologo=true"
            with open(raw_media_path, "wb") as f: f.write(requests.get(img_url, timeout=45).content)
            vclip = ImageClip(raw_media_path).set_duration(scene_duration)
            last_successful_media = {"type": "image", "path": raw_media_path}

        vclip = vclip.resize(height=TARGET_H) if (vclip.w / vclip.h) > (TARGET_W / TARGET_H) else vclip.resize(width=TARGET_W)
        vclip = vclip.crop(x_center=vclip.w/2, y_center=vclip.h/2, width=TARGET_W, height=TARGET_H)
        
        motion_type = random.choice(['zoom_in', 'zoom_out'])
        zoom_factor = 1.05 
        z_clip = vclip.resize(lambda t: 1.0 + (zoom_factor - 1.0) * (t / scene_duration)).set_position(('center', 'center')) if motion_type == 'zoom_in' else vclip.resize(lambda t: zoom_factor - (zoom_factor - 1.0) * (t / scene_duration)).set_position(('center', 'center'))

        def advanced_punch_anim(t):
            if t < 0.06: return 1.6 - 10.0 * t  
            elif t < 0.15: return 1.0 + 1.2 * (t - 0.06) 
            return 1.0

        def get_kinetic_pos(base_y, is_shaking, word_idx):
            def pos(t):
                idle_y = 7 * math.sin(t * 8 + word_idx)
                idle_x = 4 * math.cos(t * 6 + word_idx)
                if is_shaking and t > 0.06:
                    return (TARGET_W/2 + 5 * math.sin(t * 75) + idle_x, base_y + 5 * math.cos(t * 85) + idle_y)
                return (TARGET_W/2 + idle_x, base_y + idle_y)
            return pos

        words = text_line.split()
        danger_timestamps = []

        if words:
            # 🔥 FIX 2: Smart Subtitle Synchronization (Calculates time per character & pause) 🔥
            word_weights = []
            for w in words:
                wt = len(w)
                if w.endswith(','): wt += 4 # Commas trigger a short pause
                elif w[-1] in '.?!।': wt += 8 # Full stops trigger a longer pause
                word_weights.append(wt)
            
            total_weight = sum(word_weights) if sum(word_weights) > 0 else 1
            current_time_pos = 0.0

            for w_i, word in enumerate(words):
                word_lower = word.lower()
                is_danger = any(kw in word_lower for kw in ['secret', 'trick', 'hidden', 'scam', 'khatarnaak', 'danger', 'alert', 'mat'])
                is_highlight = not is_danger and len(word) > 5
                
                # Accurately mapping text duration to TTS speech length
                duration_per_word = (word_weights[w_i] / total_weight) * scene_duration
                
                if is_danger or is_highlight:
                    danger_timestamps.append((current_time_pos, current_time_pos + duration_per_word))

                current_color = '#FF003C' if is_danger else ('#000000' if is_highlight else '#FFFFFF')
                bg_color = 'transparent' if is_danger else (random.choice(['#FFD400', '#39FF14']) if is_highlight else 'transparent')
                base_size = 155 if is_danger else (140 if is_highlight else 90)

                try:
                    text_y_pos = TARGET_H * 0.75 
                    position_filter = get_kinetic_pos(text_y_pos, is_danger, w_i)

                    if bg_color == 'transparent':
                        shadow_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(get_kinetic_pos(text_y_pos + 15, is_danger, w_i)).set_duration(duration_per_word).set_start(current_time_pos)
                        bg_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, stroke_color='black', stroke_width=16, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        inner_border_txt = TextClip(word, fontsize=base_size, color='black', font=HINDI_FONT_FILE, stroke_color='white', stroke_width=4, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        main_txt = TextClip(word, fontsize=base_size, color=current_color, font=HINDI_FONT_FILE, method='caption', size=(1500, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        word_clips.extend([shadow_txt, bg_txt, inner_border_txt, main_txt])
                    else:
                        main_txt = TextClip(word, fontsize=base_size, color=current_color, bg_color=bg_color, font=HINDI_FONT_FILE, method='caption', size=(None, None)).resize(advanced_punch_anim).set_position(position_filter).set_duration(duration_per_word).set_start(current_time_pos)
                        word_clips.append(main_txt)
                except: pass
                
                # Move timeline forward accurately
                current_time_pos += duration_per_word

        def dynamic_opacity(t):
            for start, end in danger_timestamps:
                if start <= t <= end:
                    return 0.65 
            return 0.35 
            
        dark_overlay = ColorClip(size=(TARGET_W, TARGET_H), color=(0,0,0)).set_duration(scene_duration).set_opacity(0.45) # Keep fixed to avoid function crash

        final_scene = CompositeVideoClip([z_clip, dark_overlay] + word_clips, size=(TARGET_W, TARGET_H)).set_duration(scene_duration)
        final_scene.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", threads=4, ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)

    except Exception as e:
        print(f"Error on scene {i}: {e}")
        cclip = ColorClip(size=(TARGET_W, TARGET_H), color=(30, 30, 30)).set_duration(scene_duration)
        cclip.write_videofile(norm_video_path, fps=24, codec="libx264", audio=False, preset="ultrafast", threads=4, ffmpeg_params=['-pix_fmt', 'yuv420p', '-vf', 'setsar=1'], logger=None)
        cclip.close()

    try:
        vclip.close()
        z_clip.close()
        dark_overlay.close()
        final_scene.close()
        for w in word_clips: w.close()
    except: pass
    
    video_files.append(norm_video_path)
    gc.collect()

# --- 3. High-Speed FFmpeg Concat ---
with open("vid_list.txt", "w") as f:
    for vid in video_files: f.write(f"file '{vid}'\n")

with open("aud_list.txt", "w") as f:
    for aud in audio_files: f.write(f"file '{aud}'\n")

subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'vid_list.txt', '-c', 'copy', 'merged_video.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'aud_list.txt', '-c', 'copy', 'merged_audio.wav'], check=True)

# --- 4. Final Master Mix ---
has_logo = os.path.exists("logo.png")
has_bgm = os.path.exists("bgm.mp3")

ffmpeg_cmd = ['ffmpeg', '-y', '-i', 'merged_video.mp4', '-i', 'merged_audio.wav']
filter_complex = ""
audio_map = ""
video_map = ""
inputs = 2

if has_bgm:
    ffmpeg_cmd.extend(['-stream_loop', '-1', '-i', 'bgm.mp3'])
    filter_complex += "[1:a]asplit=2[voice_main][voice_control]; [2:a]volume=0.25[bgm_low]; [bgm_low][voice_control]sidechaincompress=threshold=0.08:ratio=8:attack=200:release=1000[ducked_bgm]; [voice_main][ducked_bgm]amix=inputs=2:duration=first,loudnorm=I=-14:LRA=11:TP=-1.5[a_out]; "
    audio_map = "[a_out]"
    inputs += 1
else:
    filter_complex += "[1:a]loudnorm=I=-14:LRA=11:TP=-1.5[a_out]; "
    audio_map = "[a_out]"

channel_name = "Android Tricks"
filter_complex += f"[0:v]eq=contrast=1.05:saturation=1.15,vignette,noise=alls=1:allf=t+u,drawtext=text='{channel_name}':fontcolor=white@0.6:fontsize=50:x=W-tw-50:y=H-th-50[v_graded]; "
current_v_map = "[v_graded]"

if has_logo:
    ffmpeg_cmd.extend(['-i', 'logo.png'])
    filter_complex += f"[{inputs-1}:v]format=rgba,colorchannelmixer=aa=0.85,scale=200:-1[logo]; {current_v_map}[logo]overlay=W-w-40:40[v_out]"
    video_map = "[v_out]"
else:
    video_map = current_v_map

if filter_complex.endswith("; "): filter_complex = filter_complex[:-2]
if filter_complex: ffmpeg_cmd.extend(['-filter_complex', filter_complex])

ffmpeg_cmd.extend([
    '-map', video_map, '-map', audio_map,
    '-c:v', 'libx264', '-preset', 'fast', '-profile:v', 'high', '-bf', '2', '-g', '48', '-crf', '26', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '128k', '-shortest', 'final_video.mp4'
])
subprocess.run(ffmpeg_cmd, check=True)

# --- 5. Upload System ---
video_link = "Upload Failed"
for upload_url in [
    "https://0x0.st", 
    "https://uguu.se/upload.php", 
    "https://tmpfiles.org/api/v1/upload", 
    "https://catbox.moe/user/api.php"
]:
    if not video_link.startswith("http"):
        try:
            if "uguu.se" in upload_url: res = requests.post(upload_url, files={'files[]': open('final_video.mp4', 'rb')}, timeout=600); video_link = res.json()['files'][0]['url'] if res.status_code == 200 else video_link
            elif "tmpfiles" in upload_url: res = requests.post(upload_url, files={'file': open('final_video.mp4', 'rb')}, timeout=600); video_link = res.json()['data']['url'].replace('tmpfiles.org/', 'tmpfiles.org/dl/') if res.status_code == 200 else video_link
            elif "catbox" in upload_url: res = requests.post(upload_url, data={'reqtype': 'fileupload'}, files={'fileToUpload': open('final_video.mp4', 'rb')}, timeout=600); video_link = res.text.strip() if res.text.startswith("http") else video_link
            else: res = requests.post(upload_url, files={'file': open('final_video.mp4', 'rb')}, timeout=600); video_link = res.text.strip() if res.text.startswith("http") else video_link
        except: pass

# --- 6. Notification ---
payload = {"chat_id": chat_id, "message": "👑 Bhai! Android Tricks Long Video Ready! 🔥", "youtube_url": video_link}
safe_headers = {'User-Agent': 'Mozilla/5.0 Chrome/123.0.0.0 Safari/537.36', 'Accept': 'application/json'}

if resume_url:
    try: requests.post(resume_url, json={"body": payload}, headers=safe_headers, timeout=30)
    except: pass

final_msg = f"READY_TO_UPLOAD|{video_link}|{video_title}|{thumbnail_prompt}|{video_desc}"
requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": final_msg})
