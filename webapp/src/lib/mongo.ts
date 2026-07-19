/**
 * Cached MongoDB client for the Next.js webapp.
 *
 * Connects to the same MongoDB Atlas cluster as the Python pipeline.
 * The connection string is read from MONGODB_URI server-side only —
 * it is NEVER exposed to the client bundle.
 *
 * IMPORTANT — lazy initialization
 * ------------------------------
 * The MongoClient is NOT constructed at module load time. This is
 * deliberate: `next build` imports every page module to determine
 * whether it is static or dynamic, and if this module threw at
 * import time (because MONGODB_URI isn't set during the build), the
 * entire build would fail — even though every page that needs Mongo
 * is marked `dynamic = "force-dynamic"` and only runs at request time.
 *
 * Instead, the env var is read lazily inside `getDb()` / `getClient()`,
 * so the build succeeds without credentials. The error surfaces only
 * when a request actually hits a route that needs Mongo, which is the
 * correct failure mode.
 */

import { MongoClient, type Db } from "mongodb";

let _client: MongoClient | null = null;
let _db: Db | null = null;

function readUri(): string {
  const uri = process.env.MONGODB_URI;
  if (!uri) {
    throw new Error(
      "MONGODB_URI is not set. Configure it in the Netlify site settings (or .env.local in dev).",
    );
  }
  return uri;
}

function readDbName(): string {
  return process.env.MONGODB_DB_NAME || "quran_video_generator";
}

function getClientInstance(): MongoClient {
  if (_client) return _client;
  const uri = readUri();
  _client = new MongoClient(uri, {
    serverSelectionTimeoutMS: 5000,
    retryWrites: true,
  });
  return _client;
}

export async function getDb(): Promise<Db> {
  if (_db) return _db;
  const client = getClientInstance();
  await client.connect();
  _db = client.db(readDbName());
  return _db;
}

// Export the raw client too, in case a route needs to start a session.
export function getClient(): MongoClient {
  return getClientInstance();
}

export function getDbName(): string {
  return readDbName();
}
