import os, tempfile, subprocess, urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()
FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")

def dl(url, path):
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

@app.get("/burn-ass")
def burn_ass(video_url: str, ass_url: str, crf: int = 18,
             preset: str = "veryfast", force_style: str | None = None):
    with tempfile.TemporaryDirectory() as tmp:
        in_mp4 = os.path.join(tmp, "in.mp4")
        in_ass = os.path.join(tmp, "subs.ass")
        out_mp4 = os.path.join(tmp, "out.mp4")
        fonts   = "/usr/share/fonts/truetype"  # font fallback Noto

        dl(video_url, in_mp4)
        dl(ass_url,   in_ass)

        vf = f"subtitles='{in_ass.replace(':','\\:').replace(\"'\",\"\\\\'\")}':fontsdir='{fonts}':shaping=complex"
        if force_style:
            vf += f":force_style='{force_style.replace(\"'\",\"\\\\'\")}'"

        cmd = [FFMPEG,"-y","-i",in_mp4,"-vf",vf,"-c:v","libx264",
               "-crf",str(crf),"-preset",preset,"-pix_fmt","yuv420p",
               "-c:a","copy","-movflags","+faststart",out_mp4]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=("FFmpeg error: " + e.stderr.decode(errors="ignore")[:4000]))

        return FileResponse(out_mp4, media_type="video/mp4", filename="gain-burned.mp4")
