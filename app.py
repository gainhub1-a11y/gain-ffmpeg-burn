# app.py — GAIN FFmpeg burn-in (.ASS karaoke) — versione robusta
import os, tempfile, subprocess, urllib.request, urllib.parse, shutil
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from urllib.error import HTTPError

app = FastAPI()
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
ASS_WORKER = os.environ.get("ASS_WORKER", "https://gain-subtitles-worker.gainhub1.workers.dev/")

# ---------- health ----------
@app.get("/ping")
def ping():
    return {"ok": True}

# ---------- util ----------
UA_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/118 Safari/537.36",
    "Accept": "*/*"
}

def http_download(url: str, path: str):
    req = urllib.request.Request(url, headers=UA_HDRS)
    try:
        with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
            shutil.copyfileobj(r, f)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode(errors="ignore")[:500]
        except Exception:
            pass
        raise HTTPException(status_code=400,
                            detail=f"Download failed: HTTP {e.code}. {body or e.reason}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

def escape_for_ffmpeg_path(p: str) -> str:
    s = p.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    return s

# ---------- main ----------
@app.get("/burn-ass")
def burn_ass(
    video_url: str = Query(..., description="URL MP4/MOV di input (pubblico)"),
    ass_url: str | None = Query(None, description="URL .ASS già pronto"),
    vtt_url: str | None = Query(None, description="URL .VTT di HeyGen: il server genera lui l'ASS"),
    crf: int = Query(18, ge=0, le=40),
    preset: str = Query("veryfast"),
    force_style: str | None = Query(None, description="override stile ASS: es. FontName=Arial,Outline=2,MarginV=40")
):
    if not ass_url and not vtt_url:
        raise HTTPException(status_code=422, detail="Fornisci 'ass_url' oppure 'vtt_url'.")

    # Se passa il VTT, costruiamo noi l'URL del Worker (parametri di default stile ‘instagram-friendly’)
    if not ass_url and vtt_url:
        worker_params = {
            "vtt": vtt_url,
            "font": "Arial",
            "size": "18",
            "bold": "1",
            "primary": "#FFFFFF",
            "back_alpha": "70",
            "align": "2",
            "margin_v": "180",
            "karaoke": "word",
        }
        ass_url = f"{ASS_WORKER}?{urllib.parse.urlencode(worker_params, quote_via=urllib.parse.quote)}"

    with tempfile.TemporaryDirectory() as tmpdir:
        in_mp4  = os.path.join(tmpdir, "in.mp4")
        in_ass  = os.path.join(tmpdir, "subs.ass")
        out_mp4 = os.path.join(tmpdir, "out.mp4")
        fontsdir = "/usr/share/fonts/truetype"  # Noto/DejaVu nel container

        # 1) download
        http_download(video_url, in_mp4)
        http_download(ass_url, in_ass)

        # 2) filtro subtitles (libass)
        safe_path = escape_for_ffmpeg_path(in_ass)
        vf = f"subtitles='{safe_path}':fontsdir='{fontsdir}':shaping=complex"
        if force_style and force_style.strip():
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
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        "params_burn_ass": [
            "video_url", "ass_url (oppure vtt_url)", "crf=18", "preset=veryfast", "force_style=<optional>"
        ]
    })
