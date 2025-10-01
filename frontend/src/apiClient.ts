// apiClient.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.PROD 
    ? "https://spotify-app-backend-yqzt.onrender.com/api"
    : "/api",
});

export default apiClient;