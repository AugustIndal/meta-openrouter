import json, pathlib, subprocess, sys, datetime
root=pathlib.Path(__file__).resolve().parent
frames=json.loads((root/'assets/live-capture/manifest.json').read_text())
rounds=json.loads((root/'assets/live-rounds.json').read_text())
events=json.loads((root/'assets/live-events.json').read_text())
def stamp(value): return datetime.datetime.fromisoformat(value).timestamp()
markers=[]
for round in rounds:
    start=stamp(round['timings']['checking_clue'])-2
    guess=stamp(round['timings']['guessing'])
    reveals=[stamp(event['at']) for event in events if 'Answer revealed' in event['message'] and stamp(event['at'])>guess]
    end=(min(reveals) if reveals else guess+10)+1
    markers.append({'start':start,'end':end})
(root/'assets/markers.json').write_text(json.dumps(markers,indent=2))
for i,marker in enumerate(markers):
    begin=float(marker['start']); end=float(marker['end'])
    items=[f for f in frames if begin<=f['timestamp']<=end]
    if not items: raise RuntimeError('No frames in round '+str(i+1))
    scale=6/max(.1,end-begin)
    listing=[]
    for a,b in zip(items,items[1:]):
        listing.append("file '"+str(root/'assets/live-capture'/a['file'])+"'")
        listing.append('duration '+str(max(.001,b['timestamp']-a['timestamp'])*scale))
    listing.append("file '"+str(root/'assets/live-capture'/items[-1]['file'])+"'")
    p=root/'assets'/f'clip-{i}.txt';p.write_text('\n'.join(listing))
    dest=root/'assets'/f'round-{i}.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(p),'-vf','scale=850:630:force_original_aspect_ratio=decrease,pad=850:630:(ow-iw)/2:(oh-ih)/2:color=0xf7f5ef,fps=30','-t','6','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',str(dest)],check=True)
    print(dest,flush=True)
