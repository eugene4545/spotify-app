import { useState } from "react";
import apiClient from "../apiClient";
import type { Playlist } from "../types";

// Define track type structure
type TrackItem = {
  name: string;
  artists: { name: string }[];
};

const DownloadSettings = ({
  playlist,
}: {
  playlist: Playlist;
}) => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState({ current: 0, total: 0 });
  const [isDownloading, setIsDownloading] = useState(false);

const handleDownloadTrack = async (track: TrackItem) => {
  try {
    const response = await fetch(
      `https://spotify-app-backend-yqzt.onrender.com/api/stream-track`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          track_name: track.name,
          artist: track.artists[0].name
        })
      }
    );
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Download failed: ${response.status} - ${errorText}`);
    }
    
    const blob = await response.blob();
    
    if (blob.size === 0) {
      throw new Error("Empty file received - download may have timed out");
    }
    
    // Check if it's actually an MP3 file
    if (blob.type !== 'audio/mpeg' && blob.size < 1000) {
      const text = await blob.text();
      if (text.includes('error') || text.includes('Error')) {
        throw new Error(`Server error: ${text}`);
      }
    }
    
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${track.artists[0].name} - ${track.name}.mp3`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    return true;
  } catch (error) {
    console.error("Download failed:", error);
    // Try alternative endpoint
    return await handleDownloadTrackAlternative(track);
  }
};

const handleDownloadTrackAlternative = async (track: TrackItem) => {
  try {
    const response = await fetch(
      `https://spotify-app-backend-yqzt.onrender.com/api/stream-track-direct`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          track_name: track.name,
          artist: track.artists[0].name
        })
      }
    );
    
    if (!response.ok) throw new Error(`Alternative download failed: ${response.status}`);
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${track.artists[0].name} - ${track.name}.mp3`;
    link.click();
    window.URL.revokeObjectURL(url);
    
    return true;
  } catch (error) {
    console.error("Alternative download also failed:", error);
    return false;
  }
};
  const handleStartDownload = async () => {
    setIsDownloading(true);
    setIsLoading(true);
    setError(null);
    
    try {
      // Get playlist tracks
      const response = await apiClient.post<{
        success: boolean;
        tracks?: TrackItem[];
        error?: string;
      }>("/playlist-tracks", {
        url: playlist.url,
      });

      if (response.data.success && response.data.tracks) {
        const tracks = response.data.tracks;
        setDownloadProgress({ current: 0, total: tracks.length });
        
        // Download each track sequentially
        for (const [index, track] of tracks.entries()) {
          await handleDownloadTrack(track);
          setDownloadProgress(prev => ({ ...prev, current: index + 1 }));
          await new Promise(resolve => setTimeout(resolve, 500)); // Small delay
        }
      } else {
        setError(response.data.error || "Error loading tracks");
      }
    } catch (error) {
      setError("Failed to start download. Please try again.");
      console.error("Download error:", error);
    } finally {
      setIsLoading(false);
      setIsDownloading(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Download Settings</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-600 rounded-lg text-white">{error}</div>
      )}

      <div className="space-y-4">
        <div className="bg-yellow-900/20 border border-yellow-600/30 rounded-lg p-4">
          <p className="text-yellow-400 text-sm">
            <strong>Note:</strong> Files will download directly to your browser's 
            Downloads folder. No server storage is used.
          </p>
        </div>

        {isDownloading && (
          <div className="p-3 bg-blue-900/20 rounded-lg">
            <div className="flex justify-between text-sm mb-1">
              <span>Downloading tracks...</span>
              <span>{downloadProgress.current}/{downloadProgress.total}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full"
                style={{ width: `${(downloadProgress.current / downloadProgress.total) * 100}%` }}
              ></div>
            </div>
          </div>
        )}

        <button
          onClick={handleStartDownload}
          disabled={isLoading || isDownloading}
          className="w-full bg-spotify-green hover:bg-green-600 text-white py-3 rounded-lg font-semibold transition-colors disabled:opacity-50"
        >
          {isDownloading ? (
            `Downloading... (${downloadProgress.current}/${downloadProgress.total})`
          ) : isLoading ? (
            "Loading tracks..."
          ) : (
            "Start Download"
          )}
        </button>
      </div>
    </div>
  );
};

export default DownloadSettings;