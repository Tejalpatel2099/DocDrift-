export const environment = {
  production: false,
  // Local development: `ng serve` runs on :4200, FastAPI runs on :8001,
  // so we need the absolute cross-origin URL (CORS is enabled server-side).
  apiBaseUrl: 'http://localhost:8001',
};
