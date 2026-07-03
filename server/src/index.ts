import 'dotenv/config';
import express, { Request, Response } from 'express';
import cors from 'cors';
import { checkDbConnection, isConfigured } from './lib/supabase';

const app = express();
const PORT = Number(process.env.PORT) || 8001;
const CLIENT_ORIGIN = process.env.CLIENT_ORIGIN || 'http://localhost:4200';

// Allow the Angular dev server to call us during local development.
app.use(cors({ origin: [CLIENT_ORIGIN], credentials: true }));
app.use(express.json({ limit: '2mb' }));

/**
 * Phase 0 smoke-test endpoint. The Angular app calls this on load to prove
 * the frontend -> backend wire is connected. Everything is namespaced under
 * /api so a reverse proxy can route /api/* to Express in production.
 */
app.get('/api/hello', (_req: Request, res: Response) => {
  res.json({
    service: 'docdrift-api',
    message: 'Hello from the DocDrift Express backend 👋',
    time: new Date().toISOString(),
  });
});

/**
 * Health check — reports process uptime and live Supabase connectivity.
 * Useful for the frontend status banner and for deployment health probes.
 */
app.get('/api/health', async (_req: Request, res: Response) => {
  const db = await checkDbConnection();
  res.json({
    status: 'ok',
    uptimeSeconds: Math.round(process.uptime()),
    supabaseConfigured: isConfigured(),
    database: db,
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[docdrift-api] listening on http://0.0.0.0:${PORT}`);
  console.log(`[docdrift-api] CORS allowed origin: ${CLIENT_ORIGIN}`);
  console.log(`[docdrift-api] Supabase configured: ${isConfigured()}`);
});
