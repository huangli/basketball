import subprocess, os

cands = {
    "0011": ("DJI_20250419185729_0011_D.MP4", [2.8,4.0,6.0]),
    "0020": ("DJI_20250419190338_0020_D.MP4", [0.8]),
    "0030": ("DJI_20250419191109_0030_D.MP4", [2.6,5.2,10.8]),
    "0040": ("DJI_20250419191908_0040_D.MP4", [4.4,7.4,10.6,11.8,17.4,27.2,28.6,38.2,39.2,43.4]),
    "0128": ("DJI_20250419203648_0128_D.MP4", [18.2,20.8,23.0,24.2]),
}
os.makedirs("work/review", exist_ok=True)
for fid, (fname, times) in cands.items():
    segs = []
    for i, t in enumerate(times):
        seg = f"work/review/{fid}_s{i}.mp4"
        s = max(0, t-2); e = t+2
        vf = f"scale=1280:960,drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{fid} t={t}s':x=15:y=15:fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.8"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-ss",str(s),"-to",str(e),"-i",f"0_raw_videos/{fname}",
            "-map","0:v:0","-map","0:a:0","-vf",vf,
            "-c:v","libx264","-crf","24","-preset","fast","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","128k",seg], check=True)
        segs.append(os.path.basename(seg))
    lst = f"work/review/{fid}_list.txt"
    with open(lst,'w') as f:
        for sn in segs: f.write(f"file '{sn}'\n")
    out = f"work/review/{fid}_review.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","concat","-safe","0","-i",lst,"-c","copy","-movflags","+faststart",out], check=True)
    for sn in segs: os.remove(f"work/review/{sn}")
    os.remove(lst)
    print(f"{fid}: {len(times)} segments -> {out}")
