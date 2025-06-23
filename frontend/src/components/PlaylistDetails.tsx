import type { Playlist } from '../types';

const PlaylistDetails = ({ 
  playlist, 
  onShowTracks 
}: { 
  playlist: Playlist; 
  onShowTracks: () => void; 
}) => {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Selected Playlist</h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <img
          src={playlist.image || 'https://via.placeholder.com/300?text=No+Image'}
          alt="Playlist Cover"
          className="w-24 h-24 rounded-lg mx-auto sm:mx-0"
        />
        <div className="flex-1 text-center sm:text-left">
          <h3 className="text-xl font-semibold mb-2">{playlist.name}</h3>
          <p className="text-gray-400 mb-2">{playlist.description}</p>
          <div className="flex flex-col sm:flex-row sm:gap-6 gap-2 text-sm text-gray-300">
            <span>By {playlist.owner}</span>
            <span>{playlist.track_count} tracks</span>
          </div>
        </div>
      </div>
      <div className="mt-4">
        <button
          onClick={onShowTracks}
          className="bg-spotify-green hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors"
        >
          Show Tracks
        </button>
      </div>
    </div>
  );
};

export default PlaylistDetails;