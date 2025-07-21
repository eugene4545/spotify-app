# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
import time
import json
from fastapi.responses import StreamingResponse
import httpx
from yt_dlp import YoutubeDL
import re
import urllib.parse
import tkinter as tk
from tkinter import filedialog
from pydantic import BaseModel
from typing import Optional, List
from spotify_api import SpotifyDownloaderAPI
import spotipy
import uvicorn
import asyncio
import logging
from pathlib import Path
import os
from fastapi.responses import FileResponse
import tempfile
import atexit
import platform
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
api = SpotifyDownloaderAPI()

# Create authentication event
auth_event = asyncio.Event()

# CORS Configuration
origins = ["http://localhost:5173",
           "http://127.0.0.1:5173"
           ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"]
)

# Pydantic Models
class Credentials(BaseModel):
    client_id: str
    client_secret: str

class PlaylistRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    track_ids: Optional[List[str]] = None

class StreamRequest(BaseModel):
    track_name: str
    artist: str

# API Endpoints
@app.get("/api/are-credentials-set")
def are_credentials_set():
    return api.are_credentials_set()

@app.post("/api/save-credentials")
def save_credentials(creds: Credentials):
    return api.save_credentials(creds.client_id, creds.client_secret)

@app.get("/api/start-auth")
def start_auth_flow():
    return api.start_auth_flow()

@app.get("/api/is-authenticated")
def is_authenticated():
    return api.is_authenticated()

# @app.get("/api/download-logs")
# def download_logs():
#     return api.get_download_logs()

@app.get("/api/download-logs-stream")
def stream_logs():
    def event_generator():
        last = 0
        while True:
            logs = api.get_download_logs()['logs']
            # send any new lines
            for line in logs[last:]:
                yield f"data: {json.dumps(line)}\n\n"
            last = len(logs)
            time.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/playlists")
def get_user_playlists():
    return api.get_user_playlists()

@app.post("/api/playlist-info")
def get_playlist_info(req: PlaylistRequest):
    return api.get_playlist_info(req.url)

@app.post("/api/playlist-tracks")
def get_playlist_tracks(req: PlaylistRequest):
    return api.get_playlist_tracks_info(req.url)

@app.get("/api/progress")
def get_download_progress():
    return api.get_download_progress()

@app.post("/api/start-download")
def start_download(req: PlaylistRequest):
    return api.start_download(req.url)

@app.get("/api/stop-download")
def stop_download():
    return api.stop_download()

@app.get("/api/test-download")
async def test_download():
    # Create a test file
    test_path = os.path.join(api.temp_download_path, "test.mp3")
    with open(test_path, "wb") as f:
        f.write(b"TEST AUDIO FILE")
    
    return FileResponse(
        test_path,
        media_type="audio/mpeg",
        filename="test.mp3",
        headers={
            "Content-Disposition": "attachment; filename=\"test.mp3\"",
            "Content-Type": "audio/mpeg"
        }
    )

@app.post("/api/stream-track")
async def stream_track(req: StreamRequest):
    """Stream a track directly from YouTube to client"""
    try:
        # Search YouTube
        search_query = urllib.parse.quote(f"{req.track_name} {req.artist} official")
        video_url = None
        
        # Find best YouTube video
        try:
            html = httpx.get(f"https://www.youtube.com/results?search_query={search_query}").text
            video_ids = re.findall(r"watch\?v=(\S{11})", html)
            if video_ids:
                video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
        except Exception as e:
            logging.error(f"Error searching YouTube: {e}")
            raise HTTPException(status_code=500, detail="YouTube search failed")
        
        if not video_url:
            raise HTTPException(status_code=404, detail="No YouTube video found")
        
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, "%(title)s.%(ext)s")

        # Setup yt-dlp options for direct streaming
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': tmp_path,
            'noplaylist': True,
    #         'http_headers': {
    #         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    #         'Accept': '*/*',
    #         'Accept-Language': 'en-US,en;q=0.5',
    #         'Referer': 'https://www.youtube.com/',
    # },
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'socket_timeout': 60,
    'nocheckcertificate': True,
    'progress_hooks': [ api._create_progress_hook()],
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio_url = info['url']
        
        # Generate filename
        # filename = api.sanitize_filename(f"{req.artist} - {req.track_name}.mp3")
        filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"

        return FileResponse(
      path=filename,
      media_type="audio/mpeg",
      filename=os.path.basename(filename),
    )
        # Create generator function for streaming
        def generate():
            with httpx.stream("GET", audio_url, timeout=60.0) as response:
                for chunk in response.iter_bytes():
                    yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "audio/mpeg",
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes"
            }
        )
            
    except Exception as e:
        logging.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Spotify Callback Handler
@app.get("/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    try:
        token_info = api.sp_oauth.get_access_token(code)
        api.sp = spotipy.Spotify(auth=token_info['access_token'])
        auth_event.set()  # Signal authentication complete
        return {"status": "success", "message": "Authentication successful"}
    except Exception as e:
        logging.error(f"Authentication error: {e}")
        return {"status": "error", "message": str(e)}

# New authentication check endpoint
@app.get("/api/check-auth")
async def check_auth():
    try:
        await asyncio.wait_for(auth_event.wait(), timeout=120)
        return {"authenticated": True}
    except asyncio.TimeoutError:
        return {"authenticated": False}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)