# app.py  — GAIN FFmpeg burn-in (.ASS karaoke)
import os
import tempfile
import subprocess
import urllib.request
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

# ---------- util ----------
def download_to(path: str, url: str):
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

def escape_for_ffmpeg_path(p: str) -> str:
    """
    Escapa il percorso file per il filtro FFmpeg `subtitles=`.
    Regole minime: \  '  :  (i due punti rompono il filtergraph)
    """
    s = p.replace("\\", "\\\\")   # backslash
    s = s.replace("'", "\\'")     # apice singolo
    s = s.replace(":", "\\:")     # due punti (C:\, etc.)
    return s

# ---------- health ----------
@app.get("/ping")
def ping():
    return {"ok": True}

# ---------- main ----------
@app.get("/burn-ass")
def burn_ass(
    video_url: str = Query(..., description="URL MP4/MOV di input"),
    ass_url: str   = Query(..., description="URL .ASS (karaoke)"),
    crf: int       = Query(18, ge=0, le=40),
    preset: str    = Query("veryfast"),
    force_style: str | None = Query(None, description="override stile ASS: es. FontName=Arial,Outline=2,MarginV=40")
):
    """
    Scarica video + .ass, brucia i sottotitoli con libass, restituisce MP4 ottimizzato per social.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_mp4  = os.path.join(tmpdir, "in.mp4")
        in_ass  = os.path.join(tmpdir, "subs.ass")
        out_mp4 = os.path.join(tmpdir, "out.mp4")
        fontsdir = "/usr/share/fonts/truetype"  # Noto è installato nel Dockerfile

        # 1) download
        download_to(in_mp4, video_url)
        download_to(in_ass, ass_url)

        # 2) costruzione filtro in modo SICURO (niente backslash dentro f-string)
        safe_path = escape_for_ffmpeg_path(in_ass)
        vf = f"subtitles='{safe_path}':fontsdir='{fontsdir}':shaping=complex"
        if force_style and force_style.strip():
            # anche i singoli apici nel force_style vanno escapati
            fs = force_style.replace("\\", "\\\\").replace("'", "\\'")
            vf += f":force_style='{fs}'"

        # 3) ffmpeg
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", in_mp4,
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            out_mp4,
        ]

        try:
            proc = subprocess.run(
                cmd, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            # restituisco un estratto utile dei log ffmpeg
            err = e.stderr.decode(errors="ignore")[-2000:]
            raise HTTPException(status_code=500, detail=f"FFmpeg error:\n{err}")

        # 4) ritorna il file
        return FileResponse(out_mp4, media_type="video/mp4", filename="gain-burned.mp4")

# ---------- root ----------
@app.get("/")
def root():
    return JSONResponse({
        "service": "GAIN ffmpeg burn-ass",
        "endpoints": ["/ping", "/burn-ass"],
        "params_burn_ass": ["video_url", "ass_url", "crf=18", "preset=veryfast", "force_style=<optional>"]
    })
