# backend/main.py
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List  # Add this import
from spotify_api import SpotifyDownloaderAPI
import uvicorn

app = FastAPI()
api = SpotifyDownloaderAPI()

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
    return api.set_download_path(path)

# Spotify Callback Handler
@app.get("/callback")
async def spotify_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    # Pass the code to the API to complete authentication
    api.auth_code = code
    api.auth_event.set()
    
    return {"status": "success", "message": "Authentication successful"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)