/**

 * GET  /api/audios       — list all audios
 * POST /api/audios       — create a new audio
 *
 * Validates input server-side: name required, source_url must be a
 * well-formed http(s) URL. Duration is optional (the pipeline probes
 * it at runtime if missing).
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { isValidUrl } from "@/lib/format";

export async function GET() {
  const db = await getDb();
  const docs = await db
    .collection("audios")
    .find({})
    .sort({ _id: 1 })
    .toArray();
  return NextResponse.json({ audios: docs.map((d) => stringifyIds(d)) });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const name = (body.name ?? "").toString().trim();
  const sourceUrl = (body.source_url ?? "").toString().trim();
  const durationSeconds = Number(body.duration_seconds ?? 0) || 0;

  if (!name) {
    return NextResponse.json(
      { error: "name is required" },
      { status: 400 },
    );
  }
  if (!sourceUrl || !isValidUrl(sourceUrl)) {
    return NextResponse.json(
      { error: "source_url must be a valid http(s) URL" },
      { status: 400 },
    );
  }

  const db = await getDb();
  const existing = await db.collection("audios").findOne({ name });
  if (existing) {
    return NextResponse.json(
      { error: `an audio named '${name}' already exists` },
      { status: 409 },
    );
  }

  const doc = {
    name,
    source_url: sourceUrl,
    duration_seconds: durationSeconds,
    usage_count: 0,
    last_used_at: null,
    created_at: new Date(),
  };
  const res = await db.collection("audios").insertOne(doc);
  const inserted = await db.collection("audios").findOne({ _id: res.insertedId });
  return NextResponse.json({ audio: stringifyIds(inserted) }, { status: 201 });
}
