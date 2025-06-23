import { useState, useEffect } from "react";
import axios from "axios";

const DownloadSettings = ({
  onStartDownload,
}: {
  onStartDownload: () => void;
}) => {
  const [downloadPath, setDownloadPath] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDownloadPath = async () => {
      try {
        setError(null);
        const response = await axios.get<{ path: string }>("/download-path");
        setDownloadPath(response.data.path);
      } catch (caughtError) {
        let errorMessage = "Error fetching download path: ";
        
        if (axios.isAxiosError(caughtError)) {
          errorMessage += caughtError.response?.data?.error || caughtError.message;
        } else if (caughtError instanceof Error) {
          errorMessage += caughtError.message;
        } else {
          errorMessage += "Unknown error occurred";
        }
        
        setError(errorMessage);
        console.error(errorMessage);
      }
    };

    fetchDownloadPath();
  }, []);

  const handleBrowse = async () => {
    try {
      setError(null);
      const response = await axios.post<{ path: string }>("/browse-folder");
      
      if (response.data.path) {
        setDownloadPath(response.data.path);
        
        // Set the new download path on the server
        await axios.post("/set-download-path", { path: response.data.path });
      }
    } catch (caughtError) {
      let errorMessage = "Error browsing folder: ";
      
      if (axios.isAxiosError(caughtError)) {
        errorMessage += caughtError.response?.data?.error || caughtError.message;
      } else if (caughtError instanceof Error) {
        errorMessage += caughtError.message;
      } else {
        errorMessage += "Unknown error occurred";
      }
      
      setError(errorMessage);
      console.error(errorMessage);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Download Settings</h2>
      
      {error && (
        <div className="mb-4 p-3 bg-red-600 rounded-lg">
          {error}
        </div>
      )}
      
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Download Location
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={downloadPath}
              readOnly
              className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white"
            />
            <button
              onClick={handleBrowse}
              className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              Browse
            </button>
          </div>
        </div>
        <div className="bg-yellow-900/20 border border-yellow-600/30 rounded-lg p-4">
          <p className="text-yellow-400 text-sm">
            <strong>Note:</strong> This tool searches YouTube for audio tracks
            matching your Spotify playlist. Due to YouTube's restrictions, some
            downloads may fail. Make sure you have FFmpeg installed.
          </p>
        </div>
        <button
          onClick={onStartDownload}
          className="w-full bg-spotify-green hover:bg-green-600 text-white py-3 rounded-lg font-semibold transition-colors"
        >
          Start Download
        </button>
      </div>
    </div>
  );
};

export default DownloadSettings;