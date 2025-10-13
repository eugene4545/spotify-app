// frontend/src/components/DownloadSettings.tsx - Enhanced version

import { useState } from "react";
import apiClient from "../apiClient";
import type { Playlist } from "../types";

type TrackItem = {
  name: string;
  artists: { name: string }[];
};

const DownloadSettings = ({ playlist }: { playlist: Playlist }) => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState({ current: 0, total: 0 });
  const [isDownloading, setIsDownloading] = useState(false);
  const [failedTracks, setFailedTracks] = useState<string[]>([]);

  // Enhanced download with multiple retry strategies
  const handleDownloadTrack = async (track: TrackItem, retryCount = 0): Promise<boolean> => {
    const MAX_RETRIES = 3;
    
    try {
      console.log(`Downloading: ${track.artists[0].name} - ${track.name} (Attempt ${retryCount + 1})`);
      
      // Strategy 1: Try primary endpoint
      const response = await fetch(
        `${apiClient.defaults.baseURL}/stream-track`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            track_name: track.name,
            artist: track.artists[0].name
          }),
          signal: AbortSignal.timeout(45000) // 45 second timeout
        }
      );
      
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      
      const blob = await response.blob();
      
      if (blob.size === 0) {
        throw new Error("Empty file received");
      }
      
      // Create download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${track.artists[0].name} - ${track.name}.mp3`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      console.log(`✅ Download completed: ${track.name}`);
      return true;
      
    } catch (error) {
      console.error(`Download failed (Attempt ${retryCount + 1}):`, error);
      
      // Retry logic
      if (retryCount < MAX_RETRIES) {
        console.log(`Retrying in ${(retryCount + 1) * 2} seconds...`);
        await new Promise(resolve => setTimeout(resolve, (retryCount + 1) * 2000));
        return handleDownloadTrack(track, retryCount + 1);
      }
      
      // All retries failed
      console.error(`❌ All attempts failed for: ${track.name}`);
      return false;
    }
  };

  // Alternative: Get download info for client-side handling
  // const handleClientSideDownload = async (track: TrackItem): Promise<boolean> => {
  //   try {
  //     const response = await apiClient.post("/get-download-info", {
  //       track_name: track.name,
  //       artist: track.artists[0].name
  //     });
      
  //     if (response.data.success && response.data.url) {
  //       // Open in new tab (browser will handle download)
  //       window.open(response.data.url, '_blank');
  //       return true;
  //     }
      
  //     return false;
  //   } catch (error) {
  //     console.error("Client-side download failed:", error);
  //     return false;
  //   }
  // };

  const handleStartDownload = async () => {
    setIsDownloading(true);
    setIsLoading(true);
    setError(null);
    setFailedTracks([]);
    
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
        
        const failed: string[] = [];
        
        // Download each track with error tracking
        for (const [index, track] of tracks.entries()) {
          const success = await handleDownloadTrack(track);
          
          if (!success) {
            failed.push(`${track.artists[0].name} - ${track.name}`);
          }
          
          setDownloadProgress({ current: index + 1, total: tracks.length });
          
          // Small delay between downloads to avoid rate limiting
          if (index < tracks.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 1500));
          }
        }
        
        if (failed.length > 0) {
          setFailedTracks(failed);
          setError(`${failed.length} track(s) could not be downloaded. See list below.`);
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
        <div className="mb-4 p-3 bg-red-600/20 border border-red-500 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {failedTracks.length > 0 && (
        <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-600 rounded-lg">
          <p className="text-yellow-400 font-semibold mb-2">Failed Downloads:</p>
          <ul className="text-sm text-yellow-300 list-disc list-inside max-h-32 overflow-y-auto">
            {failedTracks.map((track, idx) => (
              <li key={idx}>{track}</li>
            ))}
          </ul>
          <p className="text-xs text-yellow-500 mt-2">
            These tracks may not be available on free music platforms.
          </p>
        </div>
      )}

      <div className="space-y-4">
        <div className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-4">
          <p className="text-blue-400 text-sm">
            <strong>💡 Tip:</strong> Downloads use free music sources (SoundCloud, etc.). 
            Some tracks may not be available. The app will try multiple sources automatically.
          </p>
        </div>

        {isDownloading && (
          <div className="p-4 bg-gradient-to-r from-blue-900/20 to-purple-900/20 rounded-lg border border-blue-500/30">
            <div className="flex justify-between text-sm mb-2">
              <span className="font-semibold">Downloading tracks...</span>
              <span className="text-blue-400">{downloadProgress.current}/{downloadProgress.total}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-500"
                style={{ width: `${(downloadProgress.current / downloadProgress.total) * 100}%` }}
              ></div>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Please keep this window open during download
            </p>
          </div>
        )}

        <button
          onClick={handleStartDownload}
          disabled={isLoading || isDownloading}
          className="w-full bg-gradient-to-r from-spotify-green to-green-600 hover:from-green-600 hover:to-green-700 text-white py-3 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
        >
          {isDownloading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Downloading... ({downloadProgress.current}/{downloadProgress.total})
            </span>
          ) : isLoading ? (
            "Loading tracks..."
          ) : (
            "Start Download"
          )}
        </button>

        {!isDownloading && downloadProgress.total > 0 && (
          <div className="text-center text-sm text-gray-400">
            Last attempt: {downloadProgress.current}/{downloadProgress.total} tracks processed
          </div>
        )}
      </div>
    </div>
  );
};

export default DownloadSettings;