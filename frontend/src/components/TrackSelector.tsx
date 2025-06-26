import { useState, useEffect } from "react";
import axios from "axios";
import type { Playlist, Track } from "../types";

const TrackSelector = ({
  playlist,
  onClose,
  onDownloadSelected,
}: {
  playlist: Playlist;
  onClose: () => void;
  onDownloadSelected: (trackIds: string[]) => void;
}) => {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [selectedTracks, setSelectedTracks] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTracks = async () => {
      try {
        setIsLoading(true);
        const response = await axios.post<{
          success: boolean;
          tracks?: Track[];
          error?: string;
        }>("/api/playlist-tracks", {
          url: playlist.url,
        });

       if (response.data.success && response.data.tracks) {
          setTracks(response.data.tracks);
          setSelectedTracks(response.data.tracks.map(t => t.id));
        } else {
          setError(response.data.error || "Error loading tracks");
        }
      } catch (caughtError) {
        let errorMessage = "Error loading tracks: ";
        
        if (axios.isAxiosError(caughtError)) {
          errorMessage += caughtError.response?.data?.error || caughtError.message;
        } else if (caughtError instanceof Error) {
          errorMessage += caughtError.message;
        } else {
          errorMessage += "Unknown error occurred";
        }
        
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTracks();
  }, [playlist.url]);

  const toggleSelectAll = (select: boolean) => {
    if (select) {
      setSelectedTracks(tracks.map((t) => t.id));
    } else {
      setSelectedTracks([]);
    }
  };

  const toggleTrack = (trackId: string) => {
    setSelectedTracks((prev) =>
      prev.includes(trackId)
        ? prev.filter((id) => id !== trackId)
        : [...prev, trackId]
    );
  };

  const formatDuration = (ms: number) => {
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(0);
    return `${minutes}:${seconds.padStart(2, "0")}`;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Select Tracks to Download</h2>

      <div className="select-all-container mb-4">
        <input
          type="checkbox"
          id="select-all-tracks"
          checked={selectedTracks.length === tracks.length}
          onChange={(e) => toggleSelectAll(e.target.checked)}
          className="mr-2"
        />
        <label htmlFor="select-all-tracks">Select All</label>
      </div>

      {isLoading ? (
        <div className="text-center py-10">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-spotify-green"></div>
          <p className="mt-4">Loading tracks...</p>
        </div>
      ) : error ? (
        <div className="text-center py-10 text-red-500">{error}</div>
      ) : (
        <div className="track-list">
          {tracks.map((track) => (
            <div
              key={track.id}
              className="track-item flex items-center p-2 hover:bg-gray-700 rounded"
            >
              <input
                type="checkbox"
                checked={selectedTracks.includes(track.id)}
                onChange={() => toggleTrack(track.id)}
                className="mr-3"
              />
              <div className="flex-1 min-w-0">
                <div className="track-name truncate">{track.name}</div>
                <div className="track-artist text-sm text-gray-400 truncate">
                  {track.artists.join(", ")}
                </div>
              </div>
              <div className="track-duration text-sm text-gray-400">
                {formatDuration(track.duration_ms)}
              </div>
              {track.preview_url && (
                <button
                  className="preview-button ml-2 border border-spotify-green text-spotify-green px-2 py-1 rounded-full text-sm"
                 onClick={() => {
          if (track.preview_url) {
            new Audio(track.preview_url).play();
          }
        }}
                >
                  Preview
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="selection-actions mt-4 flex justify-between">
        <button
          onClick={onClose}
          className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors"
        >
          Close
        </button>
        <button
          onClick={() => onDownloadSelected(selectedTracks)}
          disabled={selectedTracks.length === 0}
          className="bg-spotify-green hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          Download Selected ({selectedTracks.length})
        </button>
      </div>
    </div>
  );
};

export default TrackSelector;
