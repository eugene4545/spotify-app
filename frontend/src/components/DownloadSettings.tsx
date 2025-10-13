// frontend/src/components/DownloadSettings.tsx - Improved with fallbacks

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
  const [currentTrack, setCurrentTrack] = useState<string>("");

  const handleDownloadTrack = async (track: TrackItem): Promise<boolean> => {
    const trackName = `${track.artists[0].name} - ${track.name}`;
    setCurrentTrack(trackName);
    
    // Try primary endpoint
    try {
      console.log(`Attempting download: ${trackName}`);
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      
      const response = await fetch(
        `${apiClient.defaults.baseURL}/stream-track`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            track_name: track.name,
            artist: track.artists[0].name
          }),
          signal: controller.signal
        }
      );
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const blob = await response.blob();
        
        if (blob.size > 0) {
          // Create download
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = `${trackName}.mp3`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          
          console.log(`✅ Download successful: ${trackName}`);
          return true;
        }
      }
      
      throw new Error(`Download failed: ${response.status}`);
      
    } catch (error) {
      console.warn(`Primary download failed for ${trackName}:`, error);
      
      // Try simple endpoint as fallback
      try {
        console.log(`Trying simple endpoint for: ${trackName}`);
        
        const response = await fetch(
          `${apiClient.defaults.baseURL}/stream-track-simple`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              track_name: track.name,
              artist: track.artists[0].name
            }),
            signal: AbortSignal.timeout(45000)
          }
        );
        
        if (response.ok) {
          const blob = await response.blob();
          
          if (blob.size > 0) {
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `${trackName}.mp3`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            
            console.log(`✅ Simple download successful: ${trackName}`);
            return true;
          }
        }
        
        throw new Error("Simple endpoint also failed");
        
      } catch (fallbackError) {
        console.error(`All download methods failed for ${trackName}`);
        return false;
      }
    }
  };

  const handleStartDownload = async () => {
    setIsDownloading(true);
    setIsLoading(true);
    setError(null);
    setFailedTracks([]);
    
    try {
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
        let successCount = 0;
        
        for (const [index, track] of tracks.entries()) {
          const success = await handleDownloadTrack(track);
          
          if (success) {
            successCount++;
          } else {
            failed.push(`${track.artists[0].name} - ${track.name}`);
          }
          
          setDownloadProgress({ current: index + 1, total: tracks.length });
          
          // Delay between downloads to avoid rate limiting
          if (index < tracks.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
          }
        }
        
        // Show results
        if (failed.length > 0) {
          setFailedTracks(failed);
          setError(`Downloaded ${successCount}/${tracks.length} tracks. ${failed.length} failed.`);
        } else {
          setError(null);
          alert(`✅ Successfully downloaded all ${successCount} tracks!`);
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
      setCurrentTrack("");
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Download Settings</h2>

      {error && (
        <div className={`mb-4 p-3 rounded-lg ${
          failedTracks.length > 0 ? 'bg-yellow-600/20 border border-yellow-500' : 'bg-red-600/20 border border-red-500'
        }`}>
          <p className={failedTracks.length > 0 ? 'text-yellow-400' : 'text-red-400'}>
            {error}
          </p>
        </div>
      )}

      {failedTracks.length > 0 && (
        <div className="mb-4 p-3 bg-gray-900/50 border border-gray-700 rounded-lg">
          <p className="text-gray-300 font-semibold mb-2">Failed Downloads:</p>
          <div className="max-h-40 overflow-y-auto">
            <ul className="text-sm text-gray-400 space-y-1">
              {failedTracks.map((track, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-red-500 mr-2">•</span>
                  <span>{track}</span>
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            💡 These tracks may not be available on YouTube. Try downloading them manually.
          </p>
        </div>
      )}

      <div className="space-y-4">
        <div className="bg-blue-900/20 border border-blue-600/30 rounded-lg p-4">
          <p className="text-blue-400 text-sm">
            <strong>How it works:</strong> Files download from YouTube and similar platforms. 
            Some tracks may be unavailable due to regional restrictions or copyright.
          </p>
        </div>

        {isDownloading && (
          <div className="p-4 bg-gradient-to-br from-spotify-green/10 to-green-900/20 rounded-lg border border-spotify-green/30">
            <div className="flex justify-between items-center mb-2">
              <span className="font-semibold text-spotify-green">Downloading...</span>
              <span className="text-sm text-gray-300">
                {downloadProgress.current}/{downloadProgress.total}
              </span>
            </div>
            
            <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden mb-3">
              <div
                className="bg-gradient-to-r from-spotify-green to-green-400 h-3 rounded-full transition-all duration-500 flex items-center justify-end"
                style={{ width: `${(downloadProgress.current / downloadProgress.total) * 100}%` }}
              >
                <span className="text-xs text-white font-bold pr-2">
                  {Math.round((downloadProgress.current / downloadProgress.total) * 100)}%
                </span>
              </div>
            </div>
            
            {currentTrack && (
              <div className="text-sm text-gray-400 truncate animate-pulse">
                <span className="text-spotify-green">♪</span> {currentTrack}
              </div>
            )}
            
            <p className="text-xs text-gray-500 mt-2">
              ⏳ Please keep this window open. Downloads may take 30-60 seconds per track.
            </p>
          </div>
        )}

        <button
          onClick={handleStartDownload}
          disabled={isLoading || isDownloading}
          className="w-full bg-gradient-to-r from-spotify-green to-green-600 hover:from-green-600 hover:to-green-700 text-white py-4 rounded-lg font-bold text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:scale-105 disabled:transform-none"
        >
          {isDownloading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Downloading {downloadProgress.current}/{downloadProgress.total}
            </span>
          ) : isLoading ? (
            "Loading tracks..."
          ) : (
            "🎵 Start Download"
          )}
        </button>

        {!isDownloading && downloadProgress.total > 0 && (
          <div className="text-center">
            <p className="text-sm text-gray-400">
              Last session: {downloadProgress.current}/{downloadProgress.total} tracks processed
            </p>
            {failedTracks.length > 0 && (
              <p className="text-xs text-yellow-500 mt-1">
                {downloadProgress.total - failedTracks.length} successful downloads
              </p>
            )}
          </div>
        )}
      </div>

      <div className="mt-6 p-4 bg-gray-900/50 border border-gray-700 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">⚠️ Troubleshooting</h3>
        <ul className="text-xs text-gray-400 space-y-1">
          <li>• If downloads fail, try again in a few minutes</li>
          <li>• Some tracks may not be available on YouTube</li>
          <li>• Check your browser's download settings</li>
          <li>• Make sure popup blocker isn't blocking downloads</li>
        </ul>
      </div>
    </div>
  );
};

export default DownloadSettings;