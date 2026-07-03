import { createClient, SupabaseClient } from '@supabase/supabase-js';

/**
 * A single shared Supabase client for the whole server.
 *
 * We use the *service_role* key here because this code runs only on the
 * server. That key bypasses Row Level Security, so it must never reach the
 * browser. All DB access in DocDrift funnels through this one client.
 *
 * The client is created lazily and guarded: in Phase 0 you may not have
 * pasted your Supabase credentials yet, and the server should still boot so
 * you can hit /api/hello. `isConfigured()` lets routes report DB status
 * honestly instead of crashing.
 */
let client: SupabaseClient | null = null;

export function isConfigured(): boolean {
  return Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
}

export function getSupabase(): SupabaseClient {
  if (!isConfigured()) {
    throw new Error(
      'Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in server/.env',
    );
  }
  if (!client) {
    client = createClient(
      process.env.SUPABASE_URL as string,
      process.env.SUPABASE_SERVICE_ROLE_KEY as string,
      { auth: { persistSession: false } },
    );
  }
  return client;
}

/**
 * Lightweight connectivity probe used by the /api/health endpoint.
 * We query the `repos` table (created by supabase/schema.sql). A missing
 * table still proves we reached Postgres — we surface that as a hint.
 */
export async function checkDbConnection(): Promise<{ ok: boolean; detail: string }> {
  if (!isConfigured()) {
    return { ok: false, detail: 'Supabase credentials not set in server/.env' };
  }
  try {
    const { error } = await getSupabase().from('repos').select('id').limit(1);
    if (error) {
      // 42P01 = undefined_table -> connected, but schema.sql not run yet.
      if (error.code === '42P01') {
        return { ok: true, detail: 'Connected to Postgres, but run supabase/schema.sql to create tables.' };
      }
      return { ok: false, detail: error.message };
    }
    return { ok: true, detail: 'Connected to Supabase and repos table is reachable.' };
  } catch (err) {
    return { ok: false, detail: (err as Error).message };
  }
}
