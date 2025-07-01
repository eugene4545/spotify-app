# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tkinter as tk
from tkinter import filedialog
from pydantic import BaseModel
from typing import Optional, List
from spotify_api import SpotifyDownloaderAPI
import spotipy
import uvicorn
import asyncio
import logging
import os  # Added missing import
import platform
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
api = SpotifyDownloaderAPI()

# Create authentication event
auth_event = asyncio.Event()

# CORS Configuration
origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# API Endpoints - Note: /api prefix is handled by frontend proxy
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

@app.get("/api/playlists")
def get_user_playlists():
    return api.get_user_playlists()

@app.post("/api/playlist-info")
def get_playlist_info(req: PlaylistRequest):
    return api.get_playlist_info(req.url)

@app.post("/api/playlist-tracks")
def get_playlist_tracks(req: PlaylistRequest):
    return api.get_playlist_tracks_info(req.url)

@app.post("/api/download")
def start_download(req: DownloadRequest):
    if req.track_ids:
        return api.download_selected_tracks(req.url, req.track_ids)
    else:
        return api.start_download(req.url)

@app.get("/api/progress")
def get_download_progress():
    return api.get_download_progress()

@app.get("/api/download-path")
def get_download_path():
    return api.get_download_path()

@app.post("/api/set-download-path")
def set_download_path(path: str):
    if not path:
        return {"error": "No path provided"}
    
    try:
        # Expand home directory if needed
        expanded_path = os.path.expanduser(path)
        
        # Create the directory if it doesn't exist
        os.makedirs(expanded_path, exist_ok=True)
        
        # Set and return the path
        api.set_download_path(expanded_path)
        return {"success": True, "path": expanded_path}
    except Exception as e:
        logging.error(f"Error setting download path: {e}")
        return {"error": f"Invalid path: {str(e)}"}

@app.get("/api/stop-download")
def stop_download():
    return api.stop_download()

@app.get("/api/open-download-folder")
def open_download_folder():
    import os
    import subprocess
    import platform
    
    try:
        download_path = api.get_download_path()["path"]
        
        # Open folder based on OS
        if platform.system() == "Windows":
            os.startfile(download_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", download_path])
        else:  # Linux
            subprocess.run(["xdg-open", download_path])
            
        return {"success": True, "message": "Folder opened"}
    except Exception as e:
        return {"error": str(e)}

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