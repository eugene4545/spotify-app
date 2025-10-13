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
    """Enhanced streaming that actually works"""
    try:
        search_query = f"{req.track_name} {req.artist}"
        filename = f"{req.artist} - {req.track_name}.mp3"
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '.')).rstrip()

        logging.info(f"Attempting to download: {search_query}")

        # Create a temporary file to store the download
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_path = temp_file.name
        temp_file.close()

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_path.replace('.mp3', '.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'extract_flat': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            },
            'geo_bypass': True,
            'geo_bypass_country': 'US',
        }

        # Try different search strategies
        search_strategies = [
            # Most reliable first
            f"ytsearch1:{req.artist} {req.track_name} audio",
            f"ytsearch1:{req.artist} {req.track_name} official audio",
            f"ytsearch1:{req.artist} {req.track_name} lyrics",
            f"ytsearch1:{req.track_name} {req.artist}",
            f"ytsearch1:{search_query}",
        ]

        download_successful = False
        last_error = None

        for strategy in search_strategies:
            try:
                logging.info(f"Trying: {strategy}")
                
                with YoutubeDL(ydl_opts) as ydl:
                    # Try to extract and download
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: ydl.download([strategy])
                        ),
                        timeout=60.0  # 60 second timeout per attempt
                    )
                
                # Check if file was created
                possible_files = [
                    temp_path,
                    temp_path.replace('.mp3', '.mp3'),
                    temp_path.replace('.mp3', '.m4a'),
                    temp_path.replace('.mp3', '.webm'),
                ]
                
                for possible_file in possible_files:
                    if os.path.exists(possible_file):
                        # Read the file
                        with open(possible_file, 'rb') as f:
                            audio_data = f.read()
                        
                        # Clean up
                        try:
                            os.unlink(possible_file)
                        except:
                            pass
                        
                        if len(audio_data) > 0:
                            logging.info(f"✅ Successfully downloaded with strategy: {strategy}")
                            download_successful = True
                            
                            return StreamingResponse(
                                io.BytesIO(audio_data),
                                media_type="audio/mpeg",
                                headers={
                                    "Content-Disposition": f'attachment; filename="{filename}"',
                                }
                            )
                
            except asyncio.TimeoutError:
                last_error = f"Timeout with strategy: {strategy}"
                logging.warning(last_error)
                continue
            except Exception as e:
                last_error = str(e)
                logging.warning(f"Failed with {strategy}: {e}")
                continue
        
        # If we get here, all strategies failed
        raise HTTPException(
            status_code=404,
            detail=f"Could not download track after trying all methods. Last error: {last_error}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in stream_track: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    finally:
        # Cleanup any leftover temp files
        try:
            if 'temp_path' in locals():
                for ext in ['.mp3', '.m4a', '.webm', '.part']:
                    try:
                        if os.path.exists(temp_path.replace('.mp3', ext)):
                            os.unlink(temp_path.replace('.mp3', ext))
                    except:
                        pass
        except:
            pass


# Alternative simpler endpoint for testing
@app.post("/api/stream-track-simple")
async def stream_track_simple(req: StreamRequest):
    """Simplified version that might work better on Render"""
    try:
        search_query = f"{req.artist} {req.track_name} official audio"
        filename = f"{req.artist} - {req.track_name}.mp3"
        
        logging.info(f"Simple download attempt: {search_query}")
        
        # Use a simpler yt-dlp configuration
        ydl_opts = {
            'format': 'worstaudio/worst',  # Use worst quality for faster downloads
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'socket_timeout': 20,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            },
        }
        
        def download_audio():
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{search_query}", download=False)
                if info and 'entries' in info and len(info['entries']) > 0:
                    video = info['entries'][0]
                    url = video.get('url')
                    
                    if url:
                        # Download the audio directly
                        import requests
                        response = requests.get(url, timeout=30, stream=True)
                        return response.content
            return None
        
        audio_data = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, download_audio),
            timeout=45.0
        )
        
        if audio_data and len(audio_data) > 0:
            return StreamingResponse(
                io.BytesIO(audio_data),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
        else:
            raise HTTPException(status_code=404, detail="No audio data retrieved")
            
    except Exception as e:
        logging.error(f"Simple stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Emergency fallback - return YouTube URL for client-side download
@app.post("/api/get-youtube-url")
async def get_youtube_url(req: StreamRequest):
    """Returns YouTube URL for client-side download"""
    try:
        search_query = f"{req.artist} {req.track_name} audio"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Just get metadata, don't download
        }
        
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
                return {
                    "success": True,
                    "url": f"https://www.youtube.com/watch?v={video['id']}",
                    "title": video.get('title'),
                    "id": video.get('id')
                }
        
        return {"success": False, "error": "No results found"}
        
    except Exception as e:
        logging.error(f"Error getting YouTube URL: {e}")
        return {"success": False, "error": str(e)}


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