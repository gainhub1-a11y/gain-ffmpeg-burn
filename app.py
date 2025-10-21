# app.py — GAIN FFmpeg burn-in (.ASS karaoke) — versione completa
import os
import tempfile
import subprocess
import urllib.request
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

# ---------------- Util ----------------
def download_to(path: str, url: str):
    """Scarica url -> path (senza dipendenze esterne)."""
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

def escape_for_ffmpeg_path(p: str) -> str:
    """
    Escaping per il filtro FFmpeg `subtitles=`.
    Attenzione a backslash, apice singolo e due punti.
    """
    s = p.replace("\\", "\\\\")   # backslash
    s = s.replace("'", "\\'")     # apice singolo
    s = s.replace(":", "\\:")     # due punti (es. C:\)
    return s

# ---------------- Health / Info ----------------
@app.get("/ping")
def ping():
    return {"ok": True}

@app.get("/")
def root():
    return JSONResponse({
        "service": "GAIN ffmpeg burn-ass",
        "endpoints": ["/ping", "/burn-ass"],
        "params_burn_ass": ["video_url", "ass_url", "crf=18", "preset=veryfast", "force_style=<optional>"]
    })

# ---------------- Endpoint principale ----------------
@app.get("/burn-ass")
def burn_ass(
    video_url: str = Query(..., description="URL MP4/MOV del video (es. HeyGen)"),
    ass_url:   str = Query(..., description="URL del file .ASS generato dal Worker"),
    crf:       int = Query(18, ge=0, le=40, description="Qualità (più alto = più compresso)"),
    preset:    str = Query("veryfast", description="Preset x264"),
    force_style: str | None = Query(None, description="Override ASS: es. FontName=Arial,Outline=2,MarginV=40")
):
    """
    Scarica video + .ass, brucia i sottotitoli con libass e restituisce l'MP4 finale.
    Mantiene: shaping=complex, fontsdir, faststart, yuv420p.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_mp4  = os.path.join(tmpdir, "in.mp4")
        in_ass  = os.path.join(tmpdir, "subs.ass")
        out_mp4 = os.path.join(tmpdir, "out.mp4")
        fontsdir = "/usr/share/fonts/truetype"  # Noto/Arial fallback dal Dockerfile

        # 1) Download
        download_to(in_mp4, video_url)
        download_to(in_ass, ass_url)

        # 2) Costruzione filtro in modo sicuro
        safe_ass = escape_for_ffmpeg_path(in_ass)
        vf = f"subtitles='{safe_ass}':fontsdir='{fontsdir}':shaping=complex"
        if force_style and force_style.strip():
            fs = force_style.replace("\\", "\\\\").replace("'", "\\'")
            vf += f":force_style='{fs}'"

        # 3) Comando FFmpeg completo
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
            err = e.stderr.decode(errors="ignore")[-2000:]
            raise HTTPException(status_code=500, detail=f"FFmpeg error:\n{err}")

        # 4) Ritorno il file finale (non JSON): Make riceve direttamente l’MP4
        return FileResponse(out_mp4, media_type="video/mp4", filename="gain-burned.mp4")
