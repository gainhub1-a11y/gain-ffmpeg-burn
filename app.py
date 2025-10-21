# app.py — GAIN FFmpeg burn-in (.ASS karaoke)
import os
import tempfile
import subprocess
import time
import urllib.request
from urllib.error import HTTPError, URLError
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

# ---------- util ----------
def download_to(path: str, url: str, timeout: int = 300, tries: int = 3):
    """
    Scarica url -> path usando header 'browser-like', streaming e retry.
    Ritorna HTTP 400 con il dettaglio reale se il server remoto fallisce.
    """
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                    "Accept": "*/*",
                    "Connection": "close",
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return
        except HTTPError as e:
            try:
                body = e.read(4096).decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            last_err = f"HTTP {e.code}: {e.reason} {body[:300]}"
        except URLError as e:
            last_err = f"URL error: {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

        if attempt < tries:
            time.sleep(1.5 * attempt)

    raise HTTPException(status_code=400, detail=f"Download failed: {last_err}")

def escape_for_ffmpeg_path(p: str) -> str:
    """
    Escapa il percorso file per il filtro FFmpeg `subtitles=`.
    Regole minime: \  '  :  (i due punti rompono il filtergraph)
    """
    s = p.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace(":", "\\:")
    return s

# ---------- health ----------
@app.get("/ping")
def ping():
    return {"ok": True}

# ---------- main ----------
@app.get("/burn-ass")
def burn_ass(
    video_url: str = Query(..., description="URL MP4/MOV di input"),
    ass_url: str = Query(..., description="URL .ASS (karaoke)"),
    crf: int = Query(18, ge=0, le=40),
    preset: str = Query("veryfast"),
    force_style: str | None = Query(None, description="override stile ASS: es. FontName=Arial,Outline=2,MarginV=40")
):
    """
    Scarica video + .ass, brucia i sottotitoli con libass, restituisce MP4 ottimizzato per social.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_mp4 = os.path.join(tmpdir, "in.mp4")
        in_ass = os.path.join(tmpdir, "subs.ass")
        out_mp4 = os.path.join(tmpdir, "out.mp4")
        fontsdir = "/usr/share/fonts/truetype"  # Noto è installato nel Dockerfile

        # 1) download
        download_to(in_mp4, video_url)
        download_to(in_ass, ass_url)

        # 2) filtro FFmpeg
        safe_path = escape_for_ffmpeg_path(in_ass)
        vf = f"subtitles='{safe_path}':fontsdir='{fontsdir}':shaping=complex"
        if force_style and force_style.strip():
            fs = force_style.replace("\\", "\\\\").replace("'", "\\'")
            vf += f":force_style='{fs}'"

        # 3) esegue ffmpeg
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

        return FileResponse(out_mp4, media_type="video/mp4", filename="gain-burned.mp4")

# ---------- root ----------
@app.get("/")
def root():
    return JSONResponse({
        "service": "GAIN ffmpeg burn-ass",
        "endpoints": ["/ping", "/burn-ass"],
        "params_burn_ass": ["video_url", "ass_url", "crf=18", "preset=veryfast", "force_style=<optional>"]
    })
