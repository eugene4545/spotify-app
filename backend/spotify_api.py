import os
import re
import json
import threading
import time
import urllib.parse
import urllib.request
import string
from pathlib import Path
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv, set_key
import spotipy
from spotipy import SpotifyOAuth
from spotipy.oauth2 import SpotifyOauthError
from yt_dlp import YoutubeDL
import logging

class DownloadInterrupted(Exception):
    pass

class SpotifyDownloaderAPI:
    def __init__(self):
        # Initialize attributes first
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://127.0.0.1:8000/callback"
        self.credentials_set = False
        
        # Load environment variables
        self.env_path = '.env'
        self._check_credentials()
        
        # Now set up Spotify auth if credentials are available
        if self.credentials_set:
            self._setup_spotify_auth()
        
        # Initialize other attributes
        self.sp_oauth = None
        self.sp = None
        self.is_downloading = False
        self.download_progress = {"current": 0, "total": 0, "status": "idle"}
        self.download_path = str(Path.home() / "Downloads" / "Spotify_Downloads")
        self.auth_code = None
        self.auth_event = threading.Event()

    def _check_credentials(self):
        """Check if credentials are set in .env file"""
        if not os.path.exists(self.env_path):
            self.credentials_set = False
            return
            
        # Load environment variables
        load_dotenv(self.env_path)
        
        # Get credentials
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.redirect_uri = os.getenv("REDIRECT_URL", "http://localhost:8000/callback")
        
        # Check if credentials are valid
        if self.client_id and self.client_secret and \
           "your_spotify_client_id_here" not in self.client_id and \
           "your_spotify_client_secret_here" not in self.client_secret:
            self.credentials_set = True
        else:
            self.credentials_set = False

    def save_credentials(self, client_id: str, client_secret: str):
        """Save credentials to .env file"""
        try:
            # Create or update .env file
            set_key(self.env_path, "CLIENT_ID", client_id)
            set_key(self.env_path, "CLIENT_SECRET", client_secret)
            set_key(self.env_path, "REDIRECT_URL", "http://localhost:8000/callback")
            
            # Reload environment variables
            load_dotenv(self.env_path)
            self.client_id = client_id
            self.client_secret = client_secret
            self.redirect_uri = "http://localhost:8000/callback"
            self.credentials_set = True
            
            # Initialize Spotify auth
            self._setup_spotify_auth()
            
            return {"success": True, "message": "Credentials saved successfully!"}
        except Exception as e:
            logging.error(f"Error saving credentials: {e}")
            return {"error": str(e)}
            
    def are_credentials_set(self):
        """Check if credentials are configured"""
        return {"credentials_set": self.credentials_set}
        
    def start_auth_flow(self):
        """Start authentication flow with automatic code capture"""
        if not self.sp_oauth:
            return {"error": "Spotify OAuth not initialized"}
        
        # Generate auth URL
        auth_url = self.sp_oauth.get_authorize_url()
        
        # Start HTTP server in background
        self.auth_code = None
        self.auth_event.clear()
        self.server_thread = threading.Thread(target=self.run_auth_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Open auth URL in browser
        self.open_url(auth_url)
        
        # Wait for auth code or timeout
        self.auth_event.wait(timeout=120)
        
        if self.auth_code:
            try:
                token_info = self.sp_oauth.get_access_token(self.auth_code)
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                return {"success": True, "message": "Authentication successful"}
            except Exception as e:
                logging.error(f"Authentication error: {e}")
                return {"error": str(e)}
        else:
            return {"error": "Authentication timed out"}

    def run_auth_server(self):
        """Run HTTP server to capture auth callback"""
        # Create reference to outer self for inner class
        outer_self = self
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/callback'):
                    query = urllib.parse.urlparse(self.path).query
                    params = urllib.parse.parse_qs(query)
                    code = params.get('code', [None])[0]
                    
                    if code:
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'<h1>Authentication Successful</h1><p>You can close this window</p>')
                        # Set auth code on outer class instance
                        outer_self.auth_code = code
                        outer_self.auth_event.set()
                    else:
                        self.send_error(400, "Missing authorization code")
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                # Disable logging
                return
        
        # Create and start server on port 8000
        server = HTTPServer(('localhost', 8000), CallbackHandler)
        server.timeout = 120
        server.handle_request()


    def _setup_spotify_auth(self):
        """Setup Spotify authentication"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Spotify credentials not found in .env file")
                
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
                cache_path=".spotify_cache"
            )
            
            # Try to get cached token
            token_info = self.sp_oauth.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                
        except Exception as e:
            logging.error(f"Spotify OAuth setup error: {e}")
            
    def is_authenticated(self):
        """Check if user is authenticated"""
        return {"authenticated": self.sp is not None}
        
    def extract_playlist_id(self, playlist_url: str) -> Optional[str]:
        """Extract playlist ID from Spotify URL"""
        patterns = [
            r'playlist/([a-zA-Z0-9]+)',
            r'playlist:([a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, playlist_url)
            if match:
                return match.group(1)
        return None
        
    def get_playlist_info(self, playlist_url: str):
        """Get playlist information"""
        try:
            if not self.sp:
                return {"error": "Not authenticated with Spotify"}
                
            playlist_id = self.extract_playlist_id(playlist_url)
            if not playlist_id:
                return {"error": "Invalid Spotify playlist URL"}
                
            playlist = self.sp.playlist(playlist_id)
            track_count = playlist['tracks']['total']
            
            return {
                "success": True,
                "name": playlist['name'],
                "description": playlist['description'],
                "track_count": track_count,
                "owner": playlist['owner']['display_name'],
                "image": playlist['images'][0]['url'] if playlist['images'] else None
            }
            
        except Exception as e:
            logging.error(f"Error getting playlist info: {e}")
            return {"error": str(e)}
            
    def set_download_path(self, path: str):
        """Set download directory"""
        try:
            self.download_path = path
            os.makedirs(path, exist_ok=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"error": f"Invalid path: {str(e)}"}
            
    def get_download_path(self):
        """Get current download path"""
        return {"path": self.download_path}
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage"""
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        return ''.join(c for c in filename if c in valid_chars)
        
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Fetch all tracks from a playlist"""
        tracks = []
        offset = 0
        limit = 100
        
        while True:
            response = self.sp.playlist_tracks(playlist_id, limit=limit, offset=offset)
            tracks.extend(response['items'])
            
            if len(response['items']) < limit:
                break
            offset += limit
            
        return tracks
        
    def get_user_playlists(self):
        """Get current user's playlists"""
        try:
            if not self.sp:
                return {"error": "Not authenticated with Spotify"}
                
            playlists = []
            offset = 0
            limit = 50
            
            while True:
                response = self.sp.current_user_playlists(limit=limit, offset=offset)
                playlists.extend(response['items'])
                
                if len(response['items']) < limit:
                    break
                offset += limit
                
            # Format playlists for UI display
            formatted_playlists = []
            for playlist in playlists:
                formatted_playlists.append({
                    "id": playlist['id'],
                    "name": playlist['name'],
                    "owner": playlist['owner']['display_name'],
                    "track_count": playlist['tracks']['total'],
                    "image": playlist['images'][0]['url'] if playlist['images'] else None,
                    "url": playlist['external_urls']['spotify']
                })
                
            return {"success": True, "playlists": [
                {
                    "id": playlist['id'],
                    "name": playlist['name'],
                    "owner": playlist['owner']['display_name'],
                    "track_count": playlist['tracks']['total'],
                    "image": playlist['images'][0]['url'] if playlist['images'] else None,
                    "url": playlist['external_urls']['spotify']
                }
                for playlist in playlists
            ]}
        except Exception as e:
            logging.error(f"Error getting user playlists: {e}")
            return {"error": str(e)}
        
    def get_playlist_tracks_info(self, playlist_url: str):
        """Get detailed track information for a playlist"""
        try:
            if not self.sp:
                return {"error": "Not authenticated with Spotify"}
                
            playlist_id = self.extract_playlist_id(playlist_url)
            if not playlist_id:
                return {"error": "Invalid Spotify playlist URL"}
                
            raw_tracks = self.get_playlist_tracks(playlist_id)
            
            # Format track information
            tracks = []
            for item in raw_tracks:
                track = item['track']
                if track and track['type'] == 'track':
                    tracks.append({
                        "id": track['id'],
                        "name": track['name'],
                        "artists": [artist['name'] for artist in track['artists']],
                        "duration_ms": track['duration_ms'],
                        "preview_url": track['preview_url'],
                        "external_url": track['external_urls']['spotify']
                    })
            
            return {"success": True, "tracks": tracks}
            
        except Exception as e:
            logging.error(f"Error getting playlist tracks: {e}")
            return {"error": str(e)}

    def download_selected_tracks(self, playlist_url: str, track_ids: List[str]):
        """Download selected tracks from a playlist"""
        def download_worker():
            try:
                self.is_downloading = True
                self.download_progress = {"current": 0, "total": len(track_ids), "status": "starting"}
                
                # Get playlist info
                playlist_id = self.extract_playlist_id(playlist_url)
                if not playlist_id:
                    self.download_progress["status"] = "error"
                    self.download_progress["error"] = "Invalid playlist URL"
                    return
                    
                playlist = self.sp.playlist(playlist_id)
                playlist_name = self.sanitize_filename(playlist['name'])
                
                # Create download folder
                download_folder = os.path.join(self.download_path, playlist_name)
                os.makedirs(download_folder, exist_ok=True)
                
                # Get all tracks
                raw_tracks = self.get_playlist_tracks(playlist_id)
                
                # Filter selected tracks
                selected_tracks = [
                    t for t in raw_tracks 
                    if t['track'] and t['track']['id'] in track_ids
                ]
                
                self.download_progress["total"] = len(selected_tracks)
                self.download_progress["status"] = "downloading"
                
                successful_downloads = 0
                
                for i, track_info in enumerate(selected_tracks):
                    if not self.is_downloading:
                        self.download_progress["status"] = "cancelled"
                        return
                        
                    self.download_progress["current"] = i + 1
                    self.download_progress["current_track"] = f"{track_info['track']['artists'][0]['name']} - {track_info['track']['name']}"
                    
                    if self.download_track(track_info, download_folder):
                        successful_downloads += 1
                        
                self.download_progress["status"] = "completed"
                self.download_progress["successful"] = successful_downloads
                self.is_downloading = False
                
            except Exception as e:
                logging.error(f"Download error: {e}")
                self.download_progress["status"] = "error"
                self.download_progress["error"] = str(e)
                self.is_downloading = False
                
        if not self.is_downloading:
            threading.Thread(target=download_worker, daemon=True).start()
            return {"success": True, "message": "Download started"}
        else:
            return {"error": "Download already in progress"}

    
    def download_track(self, track_info: Dict, download_folder: str) -> bool:
        try:
            track = track_info['track']
            if not track or track['type'] != 'track':
                return False
                
            artist_name = track['artists'][0]['name']
            track_name = track['name']
            
            sanitized_name = self.sanitize_filename(f"{artist_name} - {track_name}")
            final_file = os.path.join(download_folder, f"{sanitized_name}.mp3")
            
            # Skip if already exists
            if os.path.exists(final_file):
                logging.info(f"Skipping existing file: {sanitized_name}")
                return True
                
            # Search YouTube
            search_query = urllib.parse.quote(f"{track_name} {artist_name} official")
            try:
                html = urllib.request.urlopen(f"https://www.youtube.com/results?search_query={search_query}")
                video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
            except Exception as e:
                logging.warning(f"Error searching YouTube for {sanitized_name}: {e}")
                return False
            
            if not video_ids:
                logging.warning(f"No YouTube videos found for: {sanitized_name}")
                return False
                
            # ADDED: Check if download should stop before starting
            if not self.is_downloading:
                return False
                
            # Try downloading from YouTube with improved options
            for video_id in video_ids[:3]:  # Try first 3 results
                try:
                    # ADDED: Check if download should stop before each attempt
                    if not self.is_downloading:
                        return False
                        
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    ydl_opts = {
                        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                        'outtmpl': os.path.join(download_folder, f'{sanitized_name}.%(ext)s'),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'noplaylist': True,
                        'quiet': True,
                        'no_warnings': True,
                        'ignoreerrors': True,
                        'extract_flat': False,
                        'writethumbnail': False,
                        'writeinfojson': False,
                        'cookiefile': None,  # Remove cookies for now
                        'timeout': 30,  # ADDED: Timeout to prevent hanging
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web'],
                                'skip': ['hls', 'dash'],
                            }
                        },
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        },
                        # ADDED: Progress hook for instant cancellation
                        'progress_hooks': [self._create_progress_hook()]
                    }
                    
                    with YoutubeDL(ydl_opts) as ydl:
                        # ADDED: Check if download should stop before starting download
                        if not self.is_downloading:
                            return False
                        ydl.download([video_url])
                        logging.info(f"Downloaded: {sanitized_name}")
                        return True
                        
                except DownloadInterrupted:
                    logging.info(f"Download interrupted for: {sanitized_name}")
                    return False
                except Exception as e:
                    logging.warning(f"Error downloading video {video_id}: {e}")
                    continue
                    
            return False
            
        except Exception as e:
            logging.error(f"Error downloading track: {e}")
            return False

    def _create_progress_hook(self):
        """Create a progress hook that checks for download cancellation"""
        def progress_hook(d):
            if not self.is_downloading:
                raise DownloadInterrupted()
        return progress_hook
            
    def start_download(self, playlist_url: str):
        """Start downloading playlist in background thread"""
        def download_worker():
            try:
                self.is_downloading = True
                self.download_progress = {"current": 0, "total": 0, "status": "starting"}
                
                # Get playlist info
                playlist_id = self.extract_playlist_id(playlist_url)
                if not playlist_id:
                    self.download_progress["status"] = "error"
                    self.download_progress["error"] = "Invalid playlist URL"
                    return
                    
                playlist = self.sp.playlist(playlist_id)
                playlist_name = self.sanitize_filename(playlist['name'])
                
                # Create download folder
                download_folder = os.path.join(self.download_path, playlist_name)
                os.makedirs(download_folder, exist_ok=True)
                
                # Get all tracks
                tracks = self.get_playlist_tracks(playlist_id)
                total_tracks = len(tracks)
                
                self.download_progress["total"] = total_tracks
                self.download_progress["status"] = "downloading"
                
                successful_downloads = 0
                
                for i, track_info in enumerate(tracks):
                    if not self.is_downloading:
                        self.download_progress["status"] = "cancelled"
                        return
                        
                    self.download_progress["current"] = i + 1
                    self.download_progress["current_track"] = f"{track_info['track']['artists'][0]['name']} - {track_info['track']['name']}"
                    
                    if self.download_track(track_info, download_folder):
                        successful_downloads += 1
                        
                self.download_progress["status"] = "completed"
                self.download_progress["successful"] = successful_downloads
                self.is_downloading = False
                
            except Exception as e:
                logging.error(f"Download error: {e}")
                self.download_progress["status"] = "error"
                self.download_progress["error"] = str(e)
                self.is_downloading = False
                
        if not self.is_downloading:
            threading.Thread(target=download_worker, daemon=True).start()
            return {"success": True, "message": "Download started"}
        else:
            return {"error": "Download already in progress"}
            
    def stop_download(self):
        """Stop current download"""
        self.is_downloading = False
        return {"success": True, "message": "Download stopped"}
        
    def get_download_progress(self):
        """Get current download progress"""
        return self.download_progress
        