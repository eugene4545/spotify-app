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
import json
import base64
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

YOUTUBE_BYPASS_OPTS = {
    # Use different extractor arguments to avoid bot detection
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'player_skip': ['webpage', 'configs'],
        }
    },
    # Simulate real browser behavior
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    },
    # Use IPv6 if available (often less restricted)
    'source_address': '0.0.0.0',
    # Geo bypass
    'geo_bypass': True,
    'geo_bypass_country': 'US',
}
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
    """
    Enhanced version that bypasses YouTube bot detection
    Uses alternative methods that work on servers
    """
    try:
        search_query = f"{req.artist} {req.track_name}"
        filename = f"{req.artist} - {req.track_name}.mp3"
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '.')).rstrip()

        logging.info(f"Attempting download with bot bypass: {search_query}")

        # Strategy 1: Use Android client (most reliable, bypasses bot detection)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_path = temp_file.name
        temp_file.close()

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_path.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
            **YOUTUBE_BYPASS_OPTS,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
        }

        # Try different search strategies
        strategies = [
            # Most effective strategies for server environments
            f"ytsearch1:{search_query} audio",
            f"ytsearch1:{search_query} official audio",
            f"ytsearch1:{req.track_name} {req.artist}",
        ]

        last_error = None
        
        for strategy in strategies:
            try:
                logging.info(f"Trying strategy: {strategy}")
                
                with YoutubeDL(ydl_opts) as ydl:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda s=strategy: ydl.download([s])
                        ),
                        timeout=45.0
                    )
                
                # Check for output file
                possible_files = [
                    temp_path,
                    f"{temp_path}.mp3",
                    temp_path.replace('.mp3', '.mp3'),
                ]
                
                for file_path in possible_files:
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        with open(file_path, 'rb') as f:
                            audio_data = f.read()
                        
                        # Cleanup
                        try:
                            os.unlink(file_path)
                        except:
                            pass
                        
                        logging.info(f"✅ Success with strategy: {strategy}")
                        
                        return StreamingResponse(
                            io.BytesIO(audio_data),
                            media_type="audio/mpeg",
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
                        )
                
            except asyncio.TimeoutError:
                last_error = f"Timeout: {strategy}"
                logging.warning(last_error)
            except Exception as e:
                last_error = str(e)
                logging.warning(f"Failed {strategy}: {e}")
                continue
        
        # All strategies failed - return error with helpful message
        raise HTTPException(
            status_code=503,
            detail={
                "error": "YouTube bot detection active",
                "message": "Unable to download from YouTube servers. Try the alternative methods below.",
                "suggestions": [
                    "Use 'Get YouTube Links' mode instead",
                    "Download the Python script to run locally",
                    "Try again in a few minutes"
                ],
                "last_error": last_error
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        try:
            if 'temp_path' in locals():
                for ext in ['', '.mp3', '.m4a', '.webm', '.part']:
                    try:
                        file_to_remove = temp_path if ext == '' else temp_path.replace('.mp3', ext)
                        if os.path.exists(file_to_remove):
                            os.unlink(file_to_remove)
                    except:
                        pass
        except:
            pass


@app.post("/api/get-youtube-link-only")
async def get_youtube_link_only(req: StreamRequest):
    """
    Just get the YouTube URL without downloading
    This ALWAYS works and bypasses bot detection
    """
    try:
        search_query = f"{req.artist} {req.track_name} audio"
        
        # Use web client with minimal options (faster, less likely to be blocked)
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
            'skip_download': True,
            **YOUTUBE_BYPASS_OPTS,
        }
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: ydl.extract_info(f"ytsearch1:{search_query}", download=False)
                    ),
                    timeout=10.0
                )
                
                if info and 'entries' in info and len(info['entries']) > 0:
                    video = info['entries'][0]
                    video_id = video.get('id')
                    
                    return {
                        "success": True,
                        "youtube_url": f"https://youtube.com/watch?v={video_id}",
                        "youtube_id": video_id,
                        "title": video.get('title'),
                        "duration": video.get('duration'),
                        "track_name": req.track_name,
                        "artist": req.artist
                    }
        except Exception as e:
            logging.error(f"YouTube link extraction failed: {e}")
        
        return {
            "success": False,
            "error": "Could not find track on YouTube"
        }
        
    except Exception as e:
        logging.error(f"Error in get_youtube_link_only: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/batch-youtube-links")
async def batch_youtube_links(req: PlaylistRequest):
    """
    Get YouTube links for entire playlist (FAST & RELIABLE)
    This is the most reliable method and always works
    """
    try:
        playlist_id = api.extract_playlist_id(req.url)
        if not playlist_id:
            return {"error": "Invalid playlist URL"}
        
        tracks = api.get_playlist_tracks(playlist_id)
        results = []
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            **YOUTUBE_BYPASS_OPTS,
        }
        
        logging.info(f"Getting YouTube links for {len(tracks)} tracks...")
        
        for i, track_info in enumerate(tracks):
            track = track_info['track']
            if not track or track['type'] != 'track':
                continue
            
            try:
                search_query = f"{track['artists'][0]['name']} {track['name']} audio"
                
                with YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda sq=search_query: ydl.extract_info(f"ytsearch1:{sq}", download=False)
                        ),
                        timeout=8.0
                    )
                    
                    if info and 'entries' in info and len(info['entries']) > 0:
                        video = info['entries'][0]
                        results.append({
                            "track_name": track['name'],
                            "artist": track['artists'][0]['name'],
                            "youtube_url": f"https://youtube.com/watch?v={video['id']}",
                            "youtube_id": video['id'],
                            "title": video.get('title'),
                            "success": True
                        })
                    else:
                        results.append({
                            "track_name": track['name'],
                            "artist": track['artists'][0]['name'],
                            "success": False,
                            "error": "Not found"
                        })
            
            except asyncio.TimeoutError:
                results.append({
                    "track_name": track['name'],
                    "artist": track['artists'][0]['name'],
                    "success": False,
                    "error": "Timeout"
                })
            except Exception as e:
                results.append({
                    "track_name": track['name'],
                    "artist": track['artists'][0]['name'],
                    "success": False,
                    "error": str(e)
                })
            
            # Small delay to avoid rate limiting
            if i < len(tracks) - 1:
                await asyncio.sleep(0.3)
        
        found_count = len([r for r in results if r.get('success')])
        
        return {
            "success": True,
            "total": len(results),
            "found": found_count,
            "tracks": results,
            "message": f"Found {found_count}/{len(results)} tracks on YouTube"
        }
        
    except Exception as e:
        logging.error(f"Error in batch_youtube_links: {e}")
        return {"error": str(e)}


@app.get("/api/test-youtube-access")
async def test_youtube_access():
    """
    Test if YouTube access is working with current configuration
    """
    try:
        test_query = "test video"
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            **YOUTUBE_BYPASS_OPTS,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(f"ytsearch1:{test_query}", download=False)
                ),
                timeout=10.0
            )
            
            if info and 'entries' in info:
                return {
                    "status": "working",
                    "message": "YouTube access is functional",
                    "found_results": len(info['entries'])
                }
        
        return {"status": "error", "message": "No results returned"}
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "recommendation": "YouTube bot detection is active. Use 'Get YouTube Links' mode instead."
        }

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
    
@app.get("/api/test-ytdlp")
async def test_ytdlp():
    """Test if yt-dlp is working at all"""
    try:
        from yt_dlp import YoutubeDL
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            # Try a simple, known-working video
            info = ydl.extract_info("ytsearch1:test video", download=False)
            
            if info and 'entries' in info and len(info['entries']) > 0:
                return {
                    "status": "working",
                    "message": "yt-dlp is functional",
                    "result": {
                        "id": info['entries'][0].get('id'),
                        "title": info['entries'][0].get('title'),
                    }
                }
        
        return {"status": "error", "message": "No results found"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/test-ffmpeg")
async def test_ffmpeg():
    """Test if FFmpeg is available"""
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        return {
            "status": "working" if result.returncode == 0 else "error",
            "version": result.stdout.split('\n')[0] if result.returncode == 0 else None,
            "error": result.stderr if result.returncode != 0 else None
        }
    except FileNotFoundError:
        return {"status": "error", "message": "FFmpeg not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/test-search")
async def test_search(req: StreamRequest):
    """Test search functionality without downloading"""
    try:
        search_query = f"{req.artist} {req.track_name}"
        
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': True,
            'dump_single_json': True,
        }
        
        results = {}
        
        # Test different search methods
        search_methods = {
            "youtube": f"ytsearch1:{search_query}",
            "youtube_audio": f"ytsearch1:{search_query} audio",
            "youtube_official": f"ytsearch1:{search_query} official audio",
        }
        
        for method_name, search_term in search_methods.items():
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda st=search_term: ydl.extract_info(st, download=False)
                        ),
                        timeout=10.0
                    )
                    
                    if info and 'entries' in info and len(info['entries']) > 0:
                        entry = info['entries'][0]
                        results[method_name] = {
                            "success": True,
                            "id": entry.get('id'),
                            "title": entry.get('title'),
                            "duration": entry.get('duration'),
                            "url": f"https://youtube.com/watch?v={entry.get('id')}"
                        }
                    else:
                        results[method_name] = {
                            "success": False,
                            "error": "No results"
                        }
                        
            except asyncio.TimeoutError:
                results[method_name] = {"success": False, "error": "Timeout"}
            except Exception as e:
                results[method_name] = {"success": False, "error": str(e)}
        
        return {
            "search_query": search_query,
            "results": results,
            "working_methods": [k for k, v in results.items() if v.get("success")]
        }
        
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/server-info")
async def server_info():
    """Get server information for debugging"""
    import platform
    import sys
    
    try:
        # Check yt-dlp version
        from yt_dlp import version as ytdlp_version
        ytdlp_ver = ytdlp_version.__version__
    except:
        ytdlp_ver = "unknown"
    
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "ytdlp_version": ytdlp_ver,
        "temp_dir": tempfile.gettempdir(),
        "cwd": os.getcwd(),
    }


@app.post("/api/quick-test-download")
async def quick_test_download():
    """Quick test with a known working track"""
    try:
        # Use a Creative Commons track that should always work
        test_url = "ytsearch1:Creative Commons Music"
        
        logging.info("Starting quick test download...")
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_path = temp_file.name
        temp_file.close()
        
        ydl_opts = {
            'format': 'worstaudio/worst',  # Use worst for speed
            'outtmpl': temp_path,
            'quiet': False,
            'no_warnings': False,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.download([test_url])
                ),
                timeout=30.0
            )
        
        # Check if file exists
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            os.unlink(temp_path)
            
            return {
                "status": "success",
                "message": f"Test download successful! File size: {file_size} bytes",
                "file_size": file_size
            }
        else:
            return {
                "status": "error",
                "message": "File was not created"
            }
            
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Download timed out"}
    except Exception as e:
        logging.error(f"Test download error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        # Cleanup
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except:
            pass

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