# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from io import BytesIO
import shutil
import uuid
import time
import json
from fastapi.responses import StreamingResponse
import httpx
from yt_dlp import YoutubeDL
import re
import urllib.parse
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
from concurrent.futures import ThreadPoolExecutor
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
           "http://127.0.0.1:5173",
           "https://spotify-app-1lrn.onrender.com",
           "https://spotify-app-backend-yqzt.onrender.com"
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
    """Try multiple audio sources"""
    try:
        search_query = f"{req.track_name} {req.artist}"
        filename = api.sanitize_filename(f"{req.artist} - {req.track_name}.mp3")
        
        # Try YouTube first
        try:
            result = await download_from_youtube(search_query, filename)
            if result:
                return result
        except Exception as e:
            logging.warning(f"YouTube download failed: {e}")
        
        # Fallback to SoundCloud
        try:
            result = await download_from_soundcloud(search_query, filename)
            if result:
                return result
        except Exception as e:
            logging.warning(f"SoundCloud download failed: {e}")
        
        # Final fallback - return error with suggestions
        raise HTTPException(
            status_code=500, 
            detail="Unable to download track. This may be due to YouTube restrictions. Try again later or use a different track."
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

async def download_from_soundcloud(search_query: str, filename: str):
    """Fallback to SoundCloud"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '-',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            # SoundCloud search
            info = ydl.extract_info(f"scsearch:{search_query}", download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                return None
            
            # Download first result
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            ydl_opts['outtmpl'] = f'{temp_dir}/audio.%(ext)s'
            
            with YoutubeDL(ydl_opts) as ydl_download:
                download_result = ydl_download.extract_info(
                    info['entries'][0]['webpage_url'], 
                    download=True
                )
                
                # Find and return the file
                for file in os.listdir(temp_dir):
                    if file.endswith('.mp3'):
                        with open(os.path.join(temp_dir, file), 'rb') as f:
                            content = f.read()
                        
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        
                        from io import BytesIO
                        return StreamingResponse(
                            BytesIO(content),
                            media_type="audio/mpeg",
                            headers={
                                "Content-Disposition": f'attachment; filename="{filename}"',
                                "Content-Type": "audio/mpeg",
                            }
                        )
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
            
    except Exception as e:
        logging.error(f"SoundCloud error: {e}")
        return None

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