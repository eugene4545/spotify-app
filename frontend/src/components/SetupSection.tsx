import { useState } from 'react';
import axios from 'axios';

const SetupSection = ({ onCredentialsSaved }: { onCredentialsSaved: () => void }) => {
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const handleSave = async () => {
    try {
      const response = await axios.post('/save-credentials', {
        client_id: clientId,
        client_secret: clientSecret
      });
      
      if (response.data.success) {
        setMessage({ text: response.data.message, type: 'success' });
        setTimeout(onCredentialsSaved, 1500);
      } else {
        setMessage({ text: response.data.error, type: 'error' });
      }
    } catch (error: any) {
      setMessage({ text: error.message || 'Error saving credentials', type: 'error' });
    }
  };

  return (
    <div id="setup-section">
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-2xl font-semibold mb-4 text-center">
          API Setup Required
        </h2>
        <p className="text-gray-300 mb-6 text-center">
          To use this application, you need to provide your Spotify API credentials.
        </p>
        
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-4">
            Enter Your Credentials
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Client ID</label>
              <input
                type="text"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="Enter your Client ID"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-spotify-green"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Client Secret</label>
              <input
                type="password"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                placeholder="Enter your Client Secret"
                className="w-full bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-spotify-green"
              />
            </div>
            <div className="flex justify-center">
              <button
                onClick={handleSave}
                className="bg-spotify-green hover:bg-green-600 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
              >
                Save Credentials
              </button>
            </div>
          </div>
        </div>
        
        {message && (
          <div className={`mt-4 p-3 rounded-lg ${message.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>
            {message.text}
          </div>
        )}
        
        <div className="text-center text-sm text-gray-400">
          <p>Your credentials are stored locally and only used to authenticate with Spotify's API.</p>
        </div>
      </div>
    </div>
  );
};

export default SetupSection;