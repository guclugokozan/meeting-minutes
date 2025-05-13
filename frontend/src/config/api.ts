// Use the ngrok URL for the backend API during development/testing
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://8e00-136-24-118-41.ngrok-free.app';

// Keep Ollama local for now, unless it's also tunneled or deployed publicly.
// or consider using a cloud-based model provider for deployed environments.
const OLLAMA_API_BASE_URL = process.env.NEXT_PUBLIC_OLLAMA_API_BASE_URL || 'http://localhost:11434';

export const getApiUrl = (path: string) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
export const getOllamaApiUrl = (path: string) => `${OLLAMA_API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;

// Example usage for specific endpoints (optional, but can be helpful)
export const SAVE_TRANSCRIPT_ENDPOINT = '/save-transcript';
export const PROCESS_TRANSCRIPT_ENDPOINT = '/process-transcript';
export const GET_SUMMARY_ENDPOINT = '/get-summary'; // Path will be appended with process_id
export const OLLAMA_TAGS_ENDPOINT = '/api/tags';