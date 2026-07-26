from PIL import Image
import subprocess, os, math

cands = {
    "0011": ("DJI_20250419185729_0011_D.MP4", [2.8,4.0,6.0]),
    "0020": ("DJI_20250419190338_0020_D.MP4", [0.8]),
    "0030": ("DJI_20250419191109_0030_D.MP4", [2.6,5.2,10.8]),
    "0040": ("DJI_20250419191908_0040_D.MP4", [4.4,7.4,10.6,11.8,17.4,27.2,28.6,38.2,39.2,43.4]),
    "0128": ("DJI_20250419203648_0128_D.MP4", [18.2,20.8,23.0,24.2]),
}
os.makedirs("work/review", exist_ok=True)
W, H = 480, 360
font = r"C\:/Windows/Fonts/arialbd.ttf"
for fid, (fname, times) in cands.items():
    imgs = []
    for t in times:
        tmp = f"work/review/{fid}_{t}.jpg"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-ss",str(t),"-i",f"0_raw_videos/{fname}","-map","0:v:0","-frames:v","1",
            "-vf",f"scale={W}:{H},drawtext=fontfile='{font}':text='{fid} t={t}s':x=5:y=5:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.7",
            "-q:v","3",tmp], check=True)
        imgs.append(tmp)
    n = len(imgs); cols = min(n,5); rows = math.ceil(n/cols)
    sheet = Image.new('RGB',(W*cols,H*rows),(40,40,40))
    for i,p in enumerate(imgs):
        sheet.paste(Image.open(p),((i%cols)*W,(i//cols)*H))
    out = f"work/review/{fid}_candidates.jpg"
    sheet.save(out, quality=85)
    print(f"{fid}: {n} cands {cols}x{rows} -> {out}")
