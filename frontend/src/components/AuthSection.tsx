import React from "react";
import axios from "axios";

const AuthSection = ({ onAuthenticated }: { onAuthenticated: () => void }) => {
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleAuth = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.get<{
        success: boolean;
        auth_url?: string;
        error?: string;
      }>("/start-auth"); // Removed /api prefix since it's already in baseURL

      if (response.data.success && response.data.auth_url) {
        window.open(response.data.auth_url, "_blank", "width=600,height=800");

        const pollInterval = setInterval(async () => {
          try {
            const authRes = await axios.get<{
              authenticated: boolean;
            }>("/is-authenticated"); // FIXED: Removed /api prefix

            if (authRes.data.authenticated) {
              clearInterval(pollInterval);
              onAuthenticated();
            }
          } catch (pollingError) {
            let errorMessage = "Polling error: ";
            if (axios.isAxiosError(pollingError)) {
              errorMessage +=
                pollingError.response?.data?.error || pollingError.message;
            } else if (pollingError instanceof Error) {
              errorMessage += pollingError.message;
            } else {
              errorMessage += "Unknown polling error";
            }
            console.error(errorMessage);
          }
        }, 2000);

        // Add a timeout to stop polling after 2 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          if (isLoading) {
            setIsLoading(false);
            setError("Authentication timed out. Please try again.");
          }
        }, 120000);
        
      } else {
        setError(response.data.error || "Authentication failed");
      }
    } catch (caughtError) {
      let errorMessage = "Authentication error: ";

      if (axios.isAxiosError(caughtError)) {
        errorMessage +=
          caughtError.response?.data?.error || caughtError.message;
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

  return (
    <div id="auth-section">
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">
          Spotify Authentication Required
        </h2>
        <p className="text-gray-300 mb-4">
          Please authenticate with Spotify to access your playlists.
        </p>

        <button
          onClick={handleAuth}
          disabled={isLoading}
          className="bg-spotify-green hover:bg-green-600 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {isLoading ? "Connecting..." : "Connect to Spotify"}
        </button>

        {error && <div className="mt-4 p-3 bg-red-600 rounded-lg">{error}</div>}
      </div>
    </div>
  );
};

export default AuthSection;