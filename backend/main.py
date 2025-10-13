# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
import io
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

@app.post("/api/test-download-single")
async def test_download_single():
    """Test the download logic with a known working track"""
    try:
        test_req = StreamRequest(
            track_name="Blinding Lights",
            artist="The Weeknd"
        )
        return await stream_track(test_req)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/stream-track")
async def stream_track(req: StreamRequest):
    """Use SoundCloud as primary source, YouTube as fallback"""
    try:
        search_query = f"{req.track_name} {req.artist}"
        filename = f"{req.artist} - {req.track_name}.mp3"
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '.')).rstrip()

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '-',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'ignoreerrors': True,
            'no_check_certificate': True,
        }

        def try_download(source):
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(source, download=True)
            except Exception as e:
                logging.warning(f"Failed with {source}: {e}")
                return None

        loop = asyncio.get_event_loop()
        audio_data = None
        
        # Try sources in order of reliability
        sources = [
            f"scsearch1:{search_query}",  # SoundCloud - most reliable
            f"ytsearch1:{req.track_name} {req.artist} soundcloud",  # YouTube search for SoundCloud
            f"ytsearch1:{req.track_name} {req.artist} audio",  # YouTube as last resort
        ]
        
        for source in sources:
            try:
                logging.info(f"Trying source: {source}")
                audio_data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda s=source: try_download(s)),
                    timeout=15.0
                )
                if audio_data:
                    logging.info(f"Success with source: {source}")
                    break
            except asyncio.TimeoutError:
                logging.warning(f"Timeout with source: {source}")
                continue
            except Exception as e:
                logging.warning(f"Error with source {source}: {e}")
                continue

        if not audio_data:
            raise HTTPException(status_code=404, detail="No audio source found for this track")

        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
            
    except Exception as e:
        logging.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail="Download service unavailable")


@app.post("/api/stream-track-simple")
async def stream_track_simple(req: StreamRequest):
    """Simple streaming endpoint with timeout handling"""
    try:
        search_query = f"{req.track_name} {req.artist} audio"
        filename = f"{req.artist} - {req.track_name}.mp3"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '-',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
        }
        
        # Use asyncio to handle timeouts
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: ydl.extract_info(f"ytsearch1:{search_query}", download=True)
                    ),
                    timeout=30.0  # 30 second timeout
                )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="Download timeout")
        
        if not info:
            raise HTTPException(status_code=404, detail="No audio found")
            
        # Return the audio data
        return StreamingResponse(
            io.BytesIO(info),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Simple streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

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
    
#debug
@app.post("/api/debug-search")
async def debug_search(req: StreamRequest):
    """Debug endpoint to test search functionality"""
    try:
        search_query = f"{req.track_name} {req.artist}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': False,  # Show all logs
            'no_warnings': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'extract_flat': True,  # Get info without downloading
        }
        
        results = {}
        
        # Test different search strategies
        strategies = {
            "ytsearch1": f"ytsearch1:{search_query}",
            "ytsearch10": f"ytsearch10:{search_query}",
            "scsearch": f"scsearch1:{search_query}",
        }
        
        for strategy_name, strategy_query in strategies.items():
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(strategy_query, download=False)
                    results[strategy_name] = {
                        "success": True,
                        "result_count": len(info.get('entries', [])) if info else 0,
                        "first_result": info.get('entries', [{}])[0] if info and info.get('entries') else None
                    }
            except Exception as e:
                results[strategy_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "search_query": search_query,
            "results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/")
async def root():
    return {"status": "ok", "message": "Spotify Downloader API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

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