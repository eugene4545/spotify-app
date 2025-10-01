import { useState, useEffect } from "react";
import axios from "axios";
import SetupSection from "./components/SetupSection";
import AuthSection from "./components/AuthSection";
import PlaylistBrowser from "./components/PlaylistBrowser";
import PlaylistDetails from "./components/PlaylistDetails";
import TrackSelector from "./components/TrackSelector";
import DownloadSettings from "./components/DownloadSettings";
import ProgressSection from "./components/ProgressSection";
import apiClient from "./apiClient";

// Configure Axios
const API_BASE_URL = import.meta.env.PROD 
  ? "https://spotify-app-backend-yqzt.onrender.com/api"
  : "/api";

axios.defaults.baseURL = API_BASE_URL;


function App() {
  const [appState, setAppState] = useState<"setup" | "auth" | "main">("setup");
  const [credentialsSet, setCredentialsSet] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState<any>(null);
  const [showTracks, setShowTracks] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<any>(null);

  // Check initial state
  useEffect(() => {
    const checkInitialState = async () => {
      try {
        const { data } = await apiClient.get("/are-credentials-set");
        setCredentialsSet(data.credentials_set);

        if (data.credentials_set) {
          const authRes = await apiClient.get("/is-authenticated");
          setAuthenticated(authRes.data.authenticated);
          setAppState(authRes.data.authenticated ? "main" : "auth");
        } else {
          setAppState("setup");
        }
      } catch (error) {
        console.error("Error checking initial state:", error);
      }
    };

    checkInitialState();
  }, []);

  useEffect(() => {
    if (appState !== "main") return;

    const fetchProgress = async () => {
      try {
        const response = await apiClient.get("/progress");
        setDownloadProgress(response.data);
      } catch (error) {
        console.error("Error fetching progress:", error);
      }
    };

    const interval = setInterval(fetchProgress, 1000);
    return () => clearInterval(interval);
  }, [appState]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <header className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-spotify-green to-green-400 bg-clip-text text-transparent">
          Spotify Playlist Downloader
        </h1>
        <p className="text-gray-400">
          Download your favorite Spotify playlists for offline listening
        </p>
      </header>

      {appState === "setup" && (
        <SetupSection onCredentialsSaved={() => setAppState("auth")} />
      )}

      {appState === "auth" && (
        <AuthSection
          onAuthenticated={() => {
            setAuthenticated(true);
            setAppState("main");
          }}
        />
      )}

      {appState === "main" && (
        <div className="space-y-6">
          <PlaylistBrowser onSelectPlaylist={setSelectedPlaylist} />

          {selectedPlaylist && (
            <PlaylistDetails
              playlist={selectedPlaylist}
              onShowTracks={() => setShowTracks(true)}
            />
          )}

          {appState !== "main" && (
            <p className="text-xs text-gray-400">
              Credentials: {credentialsSet ? "✔️" : "❌"} | Authenticated:{" "}
              {authenticated ? "✔️" : "❌"}
            </p>
          )}

          {downloadProgress && downloadProgress.status !== "idle" && (
            <ProgressSection
              progress={downloadProgress}
              onStopDownload={async () => {
                await apiClient.get("/api/stop-download");
              }}
            />
          )}

          {selectedPlaylist && !showTracks && (
            <DownloadSettings playlist={selectedPlaylist} />
          )}

          {showTracks && selectedPlaylist && (
            <TrackSelector
              playlist={selectedPlaylist}
              onClose={() => setShowTracks(false)}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default App;
