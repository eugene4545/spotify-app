import type { ProgressData, ProgressStatus } from "../types";

const ProgressSection = ({
  progress,
  onStopDownload,
  onOpenFolder,
}: {
  progress: ProgressData;
  onStopDownload: () => void;
  onOpenFolder: () => void;
}) => {
  const percentage = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;

  const getStatusText = (status: ProgressStatus) => {
    switch (status) {
      case "starting":
        return "Preparing download...";
      case "downloading":
        return "Downloading tracks...";
      case "completed":
        return `Completed! ${progress.successful || progress.current} tracks downloaded.`;
      case "cancelled":
        return "Download cancelled";
      case "error":
        return `Download error: ${progress.error || "Unknown error"}`;
      case "idle":
      default:
        return "Ready to download";
    }
  };

  const statusText = getStatusText(progress.status);

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold mb-4">Download Progress</h2>
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span>{statusText}</span>
            <span>
              {progress.current}/{progress.total}
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-spotify-green h-2 rounded-full transition-all duration-300"
              style={{ width: `${percentage}%` }}
            ></div>
          </div>
        </div>

        {progress.current_track && (
          <div className="text-sm text-gray-400">
            Downloading: {progress.current_track}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={onStopDownload}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            Stop Download
          </button>
          <button
            onClick={onOpenFolder}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            Open Download Folder
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProgressSection;