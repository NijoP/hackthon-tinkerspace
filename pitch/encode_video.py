"""Encode the 600-frame Blender pitch and composite clean thin tracked typography.
Run: python encode_video.py --mode preview   (or --mode final after approval).
Requires Pillow and FFmpeg. Writes silent H.264 MP4s and a local review page.
"""
import argparse, json, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser(); p.add_argument('--mode',choices=['preview','final'],default='preview')
args=p.parse_args()
BASE=Path(r'C:\Users\HP\Downloads\hackathon\pitch')
OUT=BASE/'video_output'
preview=args.mode=='preview'
FRAMES=OUT/('preview_frames' if preview else 'final_frames')
DEST=OUT/('previews' if preview else 'finals')
DEST.mkdir(parents=True,exist_ok=True)
ffmpeg=shutil.which('ffmpeg')
ffprobe=shutil.which('ffprobe')
if not ffmpeg:
    candidates=list(Path(r'C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages').glob('Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe'))
    if candidates: ffmpeg=str(candidates[0]); ffprobe=str(candidates[0].with_name('ffprobe.exe'))
if not ffmpeg: raise RuntimeError('FFmpeg is required.')
missing=[i for i in range(1,601) if not (FRAMES/f'frame_{i:04d}.png').exists()]
if missing: raise RuntimeError(f'Missing {len(missing)} rendered frames; first missing: {missing[0]}')
W,H=Image.open(FRAMES/'frame_0001.png').size
scale=W/960
SS=3
# Supersampled title plate preserves the thin sans-serif at preview resolution.
plate=Image.new('RGBA',(W*SS,H*SS),(0,0,0,0))
draw=ImageDraw.Draw(plate)
font_path=r'C:\Windows\Fonts\segoeuil.ttf'

def tracked(text,size,y,color,tracking):
    font=ImageFont.truetype(font_path,round(size*scale*SS))
    gap=tracking*scale*SS
    widths=[draw.textlength(c,font=font) for c in text]
    width=sum(widths)+gap*(len(text)-1)
    x=(W*SS-width)/2
    # Shared baseline is essential: individual glyph top-alignment makes
    # lowercase letters and punctuation jump vertically.
    top=font.getbbox(text,anchor='ls')[1]
    baseline=round(y*scale*SS-top)
    for c,w in zip(text,widths):
        draw.text((round(x),baseline),c,font=font,fill=color,anchor='ls')
        x+=w+gap
tracked('Super Monkey',42,414,(29,29,31,255),2.2)
tracked('Built in 24 hours.',17,474,(112,112,118,255),.55)
plate=plate.resize((W,H),Image.Resampling.LANCZOS)
plate_path=DEST/'hero_title.png'; plate.save(plate_path)

def run(argv):
    print('RUN:',subprocess.list2cmdline([str(x) for x in argv]),flush=True)
    subprocess.run([str(x) for x in argv],check=True)

def codec():
    return ['-an','-c:v','libx264','-preset','medium','-crf','18' if preview else '16',
            '-pix_fmt','yuv420p','-r','24','-movflags','+faststart','-color_primaries','bt709',
            '-color_trc','bt709','-colorspace','bt709']

shots=[('shot1',1,144),('shot2',145,192),('shot3',337,144),('shot4',481,120)]
for name,start,count in shots:
    cmd=[ffmpeg,'-y','-hide_banner','-loglevel','warning','-framerate','24',
         '-start_number',str(start),'-i',str(FRAMES/'frame_%04d.png')]
    if name=='shot4':
        cmd+=['-loop','1','-framerate','24','-i',str(plate_path),'-filter_complex',
              '[1:v]format=rgba,fade=t=in:st=2.5:d=0.85:alpha=1[title];'
              '[0:v][title]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]',
              '-map','[v]']
    else:
        cmd+=['-vf','format=yuv420p']
    cmd+=['-frames:v',str(count)]+codec()+[str(DEST/f'{name}.mp4')]
    run(cmd)
concat=DEST/'concat.txt'
concat.write_text('\n'.join("file '"+(DEST/f'{name}.mp4').as_posix()+"'" for name,_,_ in shots),encoding='utf-8')
# Apply the transition ONLY around the shot1->shot2 boundary. Frame count and
# durations remain exactly 600 frames / 25 seconds. Later joins are untouched.
master=DEST/('final_preview.mp4' if preview else 'final.mp4')
transition=("fade=t=out:st=5.75:d=0.25:color=white:enable='between(t,5.75,6)',"
            "fade=t=in:st=6:d=0.25:color=white:enable='between(t,6,6.25)'")
run([ffmpeg,'-y','-hide_banner','-loglevel','warning','-f','concat','-safe','0','-i',concat,
     '-vf',transition,'-frames:v','600']+codec()+[master])
convenient=BASE/('Super_Monkey_pitch_preview.mp4' if preview else 'final.mp4')
shutil.copy2(master,convenient)
poster=Image.open(FRAMES/'frame_0600.png').convert('RGBA')
poster=Image.alpha_composite(poster,plate)
poster.convert('RGB').save(OUT/'hero_poster.jpg',quality=95)
# Review contact sheet sampled from rendered frames; title shown on final panel.
frames=[1,72,144,145,218,264,336,400,480,540,570,600]
labels=['01 / Tactile details','01 / Ring and joint','01 / Lens reveal','02 / Float',
        '02 / Explode','02 / Suspended parts','02 / Reassembled','03 / Swirl',
        '03 / Rise','04 / Hero hold','04 / Identity','04 / Final lockup']
thumb_w,thumb_h=480,270
sheet=Image.new('RGB',(thumb_w*3,(thumb_h+34)*4),(245,245,247))
font=ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf',15)
sd=ImageDraw.Draw(sheet)
for i,(frame,label) in enumerate(zip(frames,labels)):
    im=Image.open(FRAMES/f'frame_{frame:04d}.png').convert('RGBA')
    if frame>=570: im=Image.alpha_composite(im,plate)
    im=im.convert('RGB').resize((thumb_w,thumb_h),Image.Resampling.LANCZOS)
    x=(i%3)*thumb_w; y=(i//3)*(thumb_h+34)
    sheet.paste(im,(x,y)); sd.text((x+12,y+thumb_h+8),label,font=font,fill=(50,50,54))
sheet.save(OUT/'storyboard.jpg',quality=93)
# Validate actual encoded streams, not just file existence.
report={}
if ffprobe:
    for path in [master]+[DEST/f'{name}.mp4' for name,_,_ in shots]:
        raw=subprocess.check_output([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)])
        data=json.loads(raw)
        video=next(s for s in data['streams'] if s['codec_type']=='video')
        report[path.name]={'width':video['width'],'height':video['height'],
                          'fps':video['r_frame_rate'],'frames':video.get('nb_read_frames'),
                          'seconds':data['format']['duration'],
                          'audio_streams':sum(s['codec_type']=='audio' for s in data['streams'])}
    (DEST/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
page='''<!doctype html><html><head><meta charset="utf-8"><title>Super Monkey — Pitch review</title>
<style>body{margin:0;background:#f5f5f7;color:#1d1d1f;font:16px 'Segoe UI',sans-serif}main{max-width:1100px;margin:48px auto;padding:0 24px}h1{font-size:42px;font-weight:300;letter-spacing:3px}p{line-height:1.6;color:#616166}video{width:100%;border-radius:12px;background:#ddd}a{color:#39622e}.shots{display:grid;grid-template-columns:1fr 1fr;gap:24px}h2{font-weight:400}img{width:100%;border-radius:12px}</style></head><body><main>
<h1>Super Monkey</h1><p>25-second silent product-launch film · 24 fps · PREVIEW_RESOLUTION<br>
Draft reconstruction from your four photographs. Preview approval is required before the final 1080p render.</p>
<video controls playsinline preload="metadata" poster="hero_poster.jpg" src="MASTER_PATH"></video>
<p><a href="MASTER_PATH" download>Download combined preview</a> ·
<a href="super_monkey_pitch.blend">Blender scene</a> · <a href="../phase1_output/super_monkey_model.glb">GLB model</a></p>
<h2>Individual shots</h2><div class="shots">SHOT_VIDEOS</div>
<h2>Storyboard</h2><img src="storyboard.jpg">
<p>Notes: proportions and hidden mating geometry remain provisional. The exploded animation uses clearance offsets and is not collision-certified. Lens internals, foil wrinkles and precise clip moulded contours are simplified draft details. No audio.</p>
</main></body></html>'''
sub=DEST.name
shot_html=''.join(f'<div><h3>{name} · {count/24:g} s</h3><video controls preload="none" src="{sub}/{name}.mp4"></video></div>' for name,_,count in shots)
page=page.replace('PREVIEW_RESOLUTION',f'{W}×{H}').replace('MASTER_PATH',f'{sub}/{master.name}').replace('SHOT_VIDEOS',shot_html)
(OUT/'watch.html').write_text(page,encoding='utf-8')
print('COMPLETE:',convenient,flush=True)
print(json.dumps(report,indent=2),flush=True)
