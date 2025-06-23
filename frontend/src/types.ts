// Playlist type used in multiple components
export interface Playlist {
  id: string;
  name: string;
  owner: string;
  track_count: number;
  image?: string;
  url: string;
  description?: string;
}

// Track type used in TrackSelector
export interface Track {
  id: string;
  name: string;
  artists: string[];
  duration_ms: number;
  preview_url?: string;
}

// Progress type used in ProgressSection
export interface ProgressData {
  current: number;
  total: number;
  status: 'idle' | 'starting' | 'downloading' | 'completed' | 'cancelled' | 'error';
  current_track?: string;
  successful?: number;
  error?: string;
}