import { useState, useEffect } from "react";
import axios from "axios";
import type { Playlist } from "../types";

const PlaylistBrowser = ({
  onSelectPlaylist,
}: {
  onSelectPlaylist: (playlist: Playlist) => void;
}) => {
  const [playlists, setPlaylists] = useState<Playlist[]>([]); // Replace any[]
  const [filteredPlaylists, setFilteredPlaylists] = useState<Playlist[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPlaylists = async () => {
      try {
        setIsLoading(true);
        const response = await axios.get<{
  success: boolean;
  playlists?: Playlist[];
  error?: string;
}>("/playlists");

        if (response.data.success && response.data.playlists) {
          setPlaylists(response.data.playlists);
          setFilteredPlaylists(response.data.playlists);
        } else {
          setError(response.data.error || "Error loading playlists");
        }
       } catch (caughtError) {
        let errorMessage = "Error loading playlists: ";
        
        if (axios.isAxiosError(caughtError)) {
          // Handle Axios-specific errors
          errorMessage += caughtError.response?.data?.error || caughtError.message;
        } else if (caughtError instanceof Error) {
          // Handle standard JavaScript errors
          errorMessage += caughtError.message;
        } else {
          // Handle unknown error types
          errorMessage += "Unknown error occurred";
        }
        
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPlaylists();
  }, []);


  useEffect(() => {
    if (!searchTerm) {
      setFilteredPlaylists(playlists);
    } else {
      const term = searchTerm.toLowerCase();
      setFilteredPlaylists(
        playlists.filter(
          (playlist) =>
            playlist.name.toLowerCase().includes(term) ||
            (playlist.owner && playlist.owner.toLowerCase().includes(term))
        )
      );
    }
  }, [searchTerm, playlists]);

  if (isLoading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center py-10">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-spotify-green"></div>
        <p className="mt-4">Loading your playlists...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center py-10 text-red-500">
        {error}
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Your Playlists</h2>

      <div className="search-container">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <svg
              className="w-5 h-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              ></path>
            </svg>
          </div>
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search your playlists..."
            className="search-input w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 pl-10 text-white placeholder-gray-400 focus:outline-none focus:border-spotify-green"
          />
        </div>
      </div>

      {filteredPlaylists.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-gray-400">No playlists found</p>
        </div>
      ) : (
        <div className="playlist-grid mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {filteredPlaylists.map((playlist) => (
            <div
              key={playlist.id}
              className="playlist-card bg-gray-700 rounded-lg overflow-hidden cursor-pointer transition-transform hover:scale-105"
              onClick={() => onSelectPlaylist(playlist)}
            >
              <img
                src={
                  playlist.image ||
                  "https://via.placeholder.com/300?text=No+Image"
                }
                alt={playlist.name}
                className="w-full h-48 object-cover"
              />
              <div className="p-3">
                <h3 className="font-bold truncate">{playlist.name}</h3>
                <p className="text-sm text-gray-400 truncate">
                  {playlist.owner} • {playlist.track_count} tracks
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PlaylistBrowser;
