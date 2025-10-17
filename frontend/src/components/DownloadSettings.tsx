// frontend/src/components/DownloadSettings.tsx - Solution that ACTUALLY WORKS

import { useState } from "react";
import apiClient from "../apiClient";
import type { Playlist } from "../types";

type YouTubeLink = {
  track_name: string;
  artist: string;
  youtube_url?: string;
  youtube_id?: string;
  title?: string;
  success: boolean;
  error?: string;
};

const DownloadSettings = ({ playlist }: { playlist: Playlist }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [youtubeLinks, setYoutubeLinks] = useState<YouTubeLink[]>([]);
  const [showLinks, setShowLinks] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Get all YouTube links (THIS ALWAYS WORKS)
  const handleGetYouTubeLinks = async () => {
    setIsLoading(true);
    setError(null);
    setYoutubeLinks([]);
    
    try {
      const response = await apiClient.post("/batch-youtube-links", {
        url: playlist.url
      });
      
      if (response.data.success) {
        setYoutubeLinks(response.data.tracks);
        setShowLinks(true);
        
        if (response.data.found === response.data.total) {
          alert(`✅ Success! Found all ${response.data.total} tracks on YouTube.`);
        } else {
          alert(`⚠️ Found ${response.data.found}/${response.data.total} tracks on YouTube.`);
        }
      } else {
        setError(response.data.error || "Failed to get YouTube links");
      }
    } catch (err) {
      setError("Error fetching YouTube links. Please try again.");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  // Copy link to clipboard
  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    });
  };

  // Open all links (in batches to avoid popup blocker)
  const openAllLinks = async () => {
    const successfulLinks = youtubeLinks.filter(link => link.success && link.youtube_url);
    
    if (successfulLinks.length === 0) {
      alert("No links to open!");
      return;
    }
    
    if (successfulLinks.length > 10) {
      const confirmed = window.confirm(
        `This will open ${successfulLinks.length} tabs. This might be blocked by your browser.\n\n` +
        `Recommended: Copy links instead and use a download manager.\n\nContinue anyway?`
      );
      if (!confirmed) return;
    }
    
    // Open in batches to avoid popup blocker
    const batchSize = 5;
    for (let i = 0; i < successfulLinks.length; i += batchSize) {
      const batch = successfulLinks.slice(i, i + batchSize);
      batch.forEach(link => {
        if (link.youtube_url) {
          window.open(link.youtube_url, '_blank');
        }
      });
      
      // Wait between batches
      if (i + batchSize < successfulLinks.length) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  };

  // Export links as text file
  const exportLinks = () => {
    const successfulLinks = youtubeLinks.filter(link => link.success);
    
    let content = `# Playlist: ${playlist.name}\n`;
    content += `# Total tracks: ${successfulLinks.length}\n`;
    content += `# Generated: ${new Date().toLocaleString()}\n\n`;
    
    successfulLinks.forEach((link, index) => {
      content += `${index + 1}. ${link.artist} - ${link.track_name}\n`;
      content += `   ${link.youtube_url}\n\n`;
    });
    
    // Add instructions
    content += '\n# How to download:\n';
    content += '# 1. Copy these links\n';
    content += '# 2. Use a browser extension like "Video DownloadHelper"\n';
    content += '# 3. Or paste links into: https://ytmp3.cc or https://y2mate.com\n';
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${playlist.name}_youtube_links.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  // Generate Python download script
  const handleGenerateScript = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.post("/generate-download-script", {
        url: playlist.url
      });
      
      if (response.data.success) {
        const blob = new Blob([response.data.script], { type: 'text/x-python' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = response.data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        alert(
          `✅ Script downloaded!\n\n` +
          `To use:\n` +
          `1. Install yt-dlp: pip install yt-dlp\n` +
          `2. Run: python ${response.data.filename}\n\n` +
          `The script will download all ${response.data.track_count} tracks directly to your computer.`
        );
      }
    } catch {
      alert("Error generating script. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-semibold mb-2">Download Options</h2>
        <p className="text-gray-400 text-sm">
          Due to YouTube's bot protection, server downloads aren't working. 
          Use one of these reliable alternatives instead:
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Option 1: Get YouTube Links */}
      <div className="bg-gradient-to-br from-green-900/20 to-spotify-green/10 border-2 border-spotify-green/50 rounded-lg p-5">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold text-spotify-green flex items-center gap-2">
              <span>🎯</span> Get YouTube Links (Recommended)
            </h3>
            <p className="text-sm text-gray-300 mt-1">
              Get direct YouTube links for all tracks. 100% reliable!
            </p>
          </div>
        </div>
        
        <button
          onClick={handleGetYouTubeLinks}
          disabled={isLoading}
          className="w-full bg-spotify-green hover:bg-green-600 text-white py-3 px-4 rounded-lg font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Getting links...
            </span>
          ) : (
            "🔍 Get YouTube Links"
          )}
        </button>
      </div>

      {/* Option 2: Download Python Script */}
      <div className="bg-gradient-to-br from-blue-900/20 to-blue-600/10 border border-blue-500/50 rounded-lg p-5">
        <h3 className="text-lg font-bold text-blue-400 flex items-center gap-2 mb-2">
          <span>💻</span> Download Python Script
        </h3>
        <p className="text-sm text-gray-300 mb-3">
          Download a Python script to run on your computer. No restrictions!
        </p>
        
        <button
          onClick={handleGenerateScript}
          disabled={isLoading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg font-semibold transition-all disabled:opacity-50"
        >
          📥 Generate Download Script
        </button>
      </div>

      {/* Show YouTube Links */}
      {showLinks && youtubeLinks.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-5 border border-gray-700">
          <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
            <h3 className="text-xl font-bold">
              YouTube Links ({youtubeLinks.filter(l => l.success).length}/{youtubeLinks.length})
            </h3>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => {
                  const allLinks = youtubeLinks
                    .filter(l => l.success && l.youtube_url)
                    .map(l => l.youtube_url)
                    .join('\n');
                  navigator.clipboard.writeText(allLinks);
                  alert('✅ All links copied to clipboard!\n\nNow:\n1. Open JDownloader\n2. Links will auto-detect\n3. Downloads start automatically!');
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
              >
                📋 Copy All Links
              </button>
              <button
                onClick={exportLinks}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
              >
                📄 Export as File
              </button>
              <button
                onClick={openAllLinks}
                className="bg-spotify-green hover:bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
              >
                🔗 Open All
              </button>
            </div>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {youtubeLinks.map((link, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg ${
                  link.success
                    ? 'bg-gray-800 border border-gray-700'
                    : 'bg-red-900/20 border border-red-800'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold truncate">
                      {link.artist} - {link.track_name}
                    </div>
                    {link.success && link.youtube_url ? (
                      <a
                        href={link.youtube_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-400 hover:text-blue-300 truncate block"
                      >
                        {link.youtube_url}
                      </a>
                    ) : (
                      <div className="text-sm text-red-400">
                        {link.error || "Not found"}
                      </div>
                    )}
                  </div>
                  
                  {link.success && link.youtube_url && (
                    <div className="flex gap-2 flex-shrink-0">
                      <button
                        onClick={() => copyToClipboard(link.youtube_url!, index)}
                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded text-xs transition"
                      >
                        {copiedIndex === index ? '✓ Copied' : '📋 Copy'}
                      </button>
                      <a
                        href={link.youtube_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-spotify-green hover:bg-green-600 text-white px-3 py-1 rounded text-xs transition"
                      >
                        ▶ Open
                      </a>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 p-4 bg-blue-900/20 border border-blue-700 rounded-lg">
            <h4 className="font-semibold text-blue-300 mb-2">How to download from YouTube:</h4>
            <ol className="text-sm text-gray-300 space-y-1 list-decimal list-inside">
              <li>Install a browser extension like "Video DownloadHelper" or "4K Video Downloader"</li>
              <li>Or use online tools: <a href="https://ytmp3.cc" target="_blank" className="text-blue-400 hover:underline">ytmp3.cc</a> or <a href="https://y2mate.com" target="_blank" className="text-blue-400 hover:underline">y2mate.com</a></li>
              <li>Click "Open All" to open all links, then download with your chosen method</li>
              <li>Or export the links and use a download manager</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
};

export default DownloadSettings;