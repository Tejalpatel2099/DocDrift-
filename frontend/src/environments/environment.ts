export const environment = {
  production: true,
  // In the hosted/production build the Angular app and the API are served
  // from the same origin, and the proxy routes /api/* to the FastAPI backend.
  // So a relative base URL ('' + '/api/...') is exactly what we want.
  apiBaseUrl: '',
};
