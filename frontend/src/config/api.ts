// TODO: Replace with your deployed backend API URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'YOUR_DEPLOYED_BACKEND_API_URL_HERE';

// TODO: Replace with your deployed Ollama API URL if you are self-hosting Ollama for production,
// or consider using a cloud-based model provider for deployed environments.
const OLLAMA_API_BASE_URL = process.env.NEXT_PUBLIC_OLLAMA_API_BASE_URL || 'http://localhost:11434';

export const getApiUrl = (path: string) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
export const getOllamaApiUrl = (path: string) => `${OLLAMA_API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;

// Example usage for specific endpoints (optional, but can be helpful)
export const SAVE_TRANSCRIPT_ENDPOINT = '/save-transcript';
export const PROCESS_TRANSCRIPT_ENDPOINT = '/process-transcript';
export const GET_SUMMARY_ENDPOINT = '/get-summary'; // Path will be appended with process_id
export const OLLAMA_TAGS_ENDPOINT = '/api/tags';