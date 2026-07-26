/**
 * GET  /api/audios/[id]/silence  — fetch cached silence analysis
 * DELETE /api/audios/[id]/silence — clear cached analysis (forces
 *   re-analysis on the next pipeline run)
 *
 * The silence positions are populated by the Python pipeline (via
 * `python main.py analyze-audio` or automatically during `generate`).
 * This route is read-only on the GET side; the DELETE side lets the
 * operator force a re-analysis without touching the audio document's
 * other fields.
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

type Ctx = { params: { id: string } };

export async function GET(_req: NextRequest, { params }: Ctx) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(params.id);
  } catch {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const db = await getDb();
  const doc = await db.collection("audios").findOne(
    { _id: oid },
    {
      projection: {
        silence_positions: 1,
        silence_analyzed: 1,
        silence_analyzed_at: 1,
        name: 1,
        duration_seconds: 1,
      },
    },
  );
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ silence: stringifyIds(doc) });
}

export async function DELETE(_req: NextRequest, { params }: Ctx) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(params.id);
  } catch {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const db = await getDb();
  const res = await db.collection("audios").updateOne(
    { _id: oid },
    {
      $set: {
        silence_positions: [],
        silence_analyzed: false,
        silence_analyzed_at: null,
      },
    },
  );
  if (res.matchedCount === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ cleared: true });
}
