/**
 * Environment configuration for the frontend.
 *
 * In Docker (nginx proxy): VITE_API_URL and VITE_WS_URL are empty strings
 *   → API calls use relative paths like /api/... (nginx proxies to backend)
 *   → WebSocket connects to /ws (nginx proxies to ws server)
 *
 * In local dev: They default to http://localhost:8000 and ws://localhost:8080
 */
const apiUrl = import.meta.env.VITE_API_URL;
const wsUrl = import.meta.env.VITE_WS_URL;

export const config = {
  // Empty string = relative URL (works with nginx proxy)
  // undefined/missing = fall back to localhost for local dev
  API_URL: apiUrl !== undefined && apiUrl !== '' ? apiUrl : 'http://localhost:8000',
  WS_URL: wsUrl !== undefined && wsUrl !== '' ? wsUrl : 'ws://localhost:8080',
};
