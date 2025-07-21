import os
from dotenv import load_dotenv
import re
import threading
import urllib.parse
import urllib.request
import string
from pathlib import Path
from typing import Dict, List, Optional
import spotipy
from spotipy import SpotifyOAuth
from yt_dlp import YoutubeDL
import logging
import tempfile


class DownloadInterrupted(Exception):
    pass

class SpotifyDownloaderAPI:
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://127.0.0.1:8000/callback"
        self.credentials_set = False
        
        
        self.env_path = '.env'
        self._check_credentials()
        
        # Initialize these as None first
        self.sp_oauth = None
        self.sp = None

        self.temp_download_path = os.path.join(str(Path.home()), "spotify_downloads_temp")
        logging.info(f"Created persistent temp download directory: {self.temp_download_path}")

        self.download_path = self.temp_download_path  # Use temp dir
        
          # Make sure temp_download_path exists
        os.makedirs(self.temp_download_path, exist_ok=True)
        logging.info(f"Temp download path: {self.temp_download_path}")

        # Set up Spotify auth if credentials are available
        if self.credentials_set:
            self._setup_spotify_auth()
        
        self.is_downloading = False
        self.download_progress = {"current": 0, "total": 0, "status": "idle"}
        self.download_log: List[str] = []

        self.download_path = str(Path.home() / "Downloads" / "Spotify_Downloads")

    def _check_credentials(self):
        """Check if credentials exist and are valid"""
        if not os.path.exists(self.env_path):
            self.credentials_set = False
            return
            
        load_dotenv(self.env_path)
        
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        
        # Check if credentials are set and not placeholder values
        if (self.client_id and self.client_secret and 
            self.client_id.strip() and self.client_secret.strip() and
            "your_spotify_client_id_here" not in self.client_id and 
            "your_spotify_client_secret_here" not in self.client_secret):
            self.credentials_set = True
            logging.info("Valid Spotify credentials found")
        else:
            self.credentials_set = False
            logging.warning("No valid Spotify credentials found")

    def save_credentials(self, client_id: str, client_secret: str):
        """Save Spotify credentials to .env file"""
        try:
            # Validate inputs
            if not client_id or not client_secret:
                return {"error": "Client ID and Client Secret are required"}
            
            if not client_id.strip() or not client_secret.strip():
                return {"error": "Client ID and Client Secret cannot be empty"}
            
            # Create .env file if it doesn't exist
            if not os.path.exists(self.env_path):
                with open(self.env_path, 'w') as f:
                    f.write("")
            
            # Update .env file
            from dotenv import set_key
            set_key(self.env_path, "CLIENT_ID", client_id.strip())
            set_key(self.env_path, "CLIENT_SECRET", client_secret.strip())
            
            # Reload environment variables
            load_dotenv(self.env_path, override=True)
            
            # Update instance variables
            self.client_id = client_id.strip()
            self.client_secret = client_secret.strip()
            self.credentials_set = True
            
            # Setup Spotify OAuth
            self._setup_spotify_auth()
            
            logging.info("Credentials saved and Spotify OAuth initialized")
            return {"success": True, "message": "Credentials saved successfully!"}
            
        except Exception as e:
            logging.error(f"Error saving credentials: {e}")
            return {"error": f"Failed to save credentials: {str(e)}"}
            
    def are_credentials_set(self):
        """Check if credentials are properly set"""
        return {"credentials_set": self.credentials_set}
        
    def start_auth_flow(self):
        """Start the Spotify authentication flow"""
        if not self.credentials_set:
            return {"error": "Spotify credentials not set. Please set them first."}
        
        if not self.sp_oauth:
            logging.warning("Spotify OAuth not initialized, attempting to initialize...")
            self._setup_spotify_auth()
            
        if not self.sp_oauth:
            return {"error": "Failed to initialize Spotify OAuth. Please check your credentials."}
        
        try:
            auth_url = self.sp_oauth.get_authorize_url()
            logging.info(f"Generated auth URL: {auth_url}")
            return {"success": True, "auth_url": auth_url}
        except Exception as e:
            logging.error(f"Error generating auth URL: {e}")
            return {"error": f"Failed to generate auth URL: {str(e)}"}

    def _setup_spotify_auth(self):
        """Setup Spotify OAuth client"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Client ID and Client Secret are required")
            
            if not self.credentials_set:
                raise ValueError("Credentials not properly set")
                
            # Create SpotifyOAuth instance
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
                cache_path=".spotify_cache",
                show_dialog=True  # Force showing the auth dialog
            )
            
            # Check if there's a cached token
            token_info = self.sp_oauth.get_cached_token()
            if token_info and not self.sp_oauth.is_token_expired(token_info):
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                logging.info("Using cached Spotify token")
            else:
                logging.info("No valid cached token found")
                
            logging.info("Spotify OAuth setup completed successfully")
            
        except Exception as e:
            logging.error(f"Spotify OAuth setup error: {e}")
            self.sp_oauth = None
            self.sp = None
            raise
            
    def is_authenticated(self):
        """Check if user is authenticated with Spotify"""
        is_auth = self.sp is not None
        logging.info(f"Authentication check: {is_auth}")
        return {"authenticated": is_auth}

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
            
    # def set_download_path(self, path: str):
    #     """Set download directory"""
    #     try:
    #         self.download_path = path
    #         os.makedirs(path, exist_ok=True)
    #         return {"success": True, "path": path}
    #     except Exception as e:
    #         return {"error": f"Invalid path: {str(e)}"}
            
    # def get_download_path(self):
    #     """Get current download path"""
    #     return {"path": self.download_path}
        
    def sanitize_filename(self, filename: str) -> str:
        cleaned = re.sub(r'[^\w\s\-.)(]', '', filename)
        return cleaned.strip()[:150]
        
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
                
            return {"success": True, "playlists": formatted_playlists}
            
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
                # download_folder = os.path.join(self.download_path, playlist_name)
                # os.makedirs(download_folder, exist_ok=True)
                
                download_folder = self.temp_download_path


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
                self.get_downloaded_files()
                
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
            final_file = os.path.join(self.temp_download_path, f"{sanitized_name}.mp3")

            logging.info(f"Saving track to: {final_file}")

            # Skip if already exists
            # if os.path.exists(final_file) and not final_file.endswith('.part'):
            #     logging.info(f"Skipping existing file: {sanitized_name}")
            # return True
                
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
                
            if not self.is_downloading:
                return False
                
            # Try downloading from YouTube with improved options
            for video_id in video_ids[:3]:  # Try first 3 results
                try:
                    if not self.is_downloading:
                        return False
                        
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    ydl_opts = {
                        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                        'outtmpl': f'{self.temp_download_path}/%(title)s.%(ext)s',
                        'noplaylist': True,
                        'quiet': True,
                        'no_warnings': True,
                        'ignoreerrors': True,
                        'extract_flat': False,
                        'continuedl': True,
                        'writethumbnail': False,
                        'writeinfojson': False,
                        'cookiefile': None,
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web'],
                                'skip': ['hls', 'dash'],
                            }
                        },
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        },
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'progress_hooks': [self._create_progress_hook()],
                        'timeout': 60
                    }
                    
                    with YoutubeDL(ydl_opts) as ydl:
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
        def progress_hook(d):
            status = d.get('status')
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total     = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                percent   = downloaded / total * 100 if total else 0
                msg = f"Downloading {d.get('filename')} — {percent:.1f}%"
                self.download_progress.update({
                    "current": d.get('downloaded_bytes', 0),
                    "total": total,
                    "status": "downloading",
                    "percent": percent
                })
                self.download_log.append(msg)

                # enforce your timeout if you want
                if d.get('elapsed') and d['elapsed'] > 120:
                    raise Exception("Download timed out")

            elif status in ('finished', 'error'):
                msg = f"{'Finished' if status=='finished' else 'Error'}: {d.get('filename')}"
                self.download_progress["status"] = status
                self.download_log.append(msg)

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

                # download_folder = os.path.join(self.download_path, playlist_name)
                # os.makedirs(download_folder, exist_ok=True)
                
                download_folder = self.temp_download_path

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
                        
                    track = track_info['track']
                    self.download_progress["current"] = i + 1
                    self.download_progress["current_track"] = f"{track['artists'][0]['name']} - {track['name']}"
                    
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
    
    def get_downloaded_files(self):
        try:
            if not os.path.exists(self.temp_download_path):
                return {"files": []}
            
            return {
                "files": [
                    f for f in os.listdir(self.temp_download_path)
                if os.path.isfile(os.path.join(self.temp_download_path, f)) 
                and not f.endswith('.part')  # Exclude incomplete files
                ]
            }
        except Exception as e:
            logging.error(f"Error listing downloaded files: {e}")
            return {"error": str(e)}
        
def cleanup_temp_files(self):
        try:
            import shutil
            if os.path.exists(self.temp_download_path):
                shutil.rmtree(self.temp_download_path)
                logging.info(f"Cleaned up temp directory: {self.temp_download_path}")
        except Exception as e:
            logging.error(f"Error cleaning temp files: {e}")

        def get_download_logs(self):
                return {"logs": self.download_log}
