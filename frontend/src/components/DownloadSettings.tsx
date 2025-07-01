import { useState, useEffect } from "react";
import axios from "axios";

// Define an interface for the extended input element
interface DirectoryInputElement extends HTMLInputElement {
  webkitdirectory: boolean;
  mozdirectory: boolean;
  directory: boolean;
}

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
          errorMessage +=
            caughtError.response?.data?.error || caughtError.message;
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
      // Create a hidden file input element with proper typing
      const input = document.createElement("input") as DirectoryInputElement;
      input.type = "file";
      
      // Set directory attributes with proper typing
      input.webkitdirectory = true;
      input.mozdirectory = true;
      input.directory = true;

      // Handle folder selection
      input.onchange = async () => {
        const files = input.files;
        
        // Proper null/undefined check with length validation
        if (files && files.length > 0) {
          // The folder path is the path of the first file
          const folderPath = files[0].webkitRelativePath.split("/")[0];

          try {
            // Send the selected path to the backend
            const response = await axios.post("/api/set-download-path", {
              path: folderPath,
            });

            if (response.data.success) {
              setDownloadPath(response.data.path);
            } else {
              setError(response.data.error || "Failed to set download path");
            }
          } catch (error) {
            setError("Failed to set download path");
            console.error("Error setting download path:", error);
          }
        }
      };

      // Trigger the folder picker
      input.click();
    } catch (error) {
      setError("Your browser does not support folder selection");
      console.error("Folder selection error:", error);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Download Settings</h2>

      {error && <div className="mb-4 p-3 bg-red-600 rounded-lg">{error}</div>}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">
            Download Location
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={downloadPath}
              onChange={(e) => setDownloadPath(e.target.value)}
              placeholder="Select download folder..."
              className="flex-grow px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-spotify-green"
            />

            <button 
              onClick={handleBrowse}
              className="px-4 py-2 bg-spotify-green hover:bg-green-600 text-white rounded-lg font-medium transition-colors"
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