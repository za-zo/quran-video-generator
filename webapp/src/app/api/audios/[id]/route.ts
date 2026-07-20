/**

 * GET    /api/audios/[id]  — fetch one audio
 * PUT    /api/audios/[id]  — update name / source_url / duration_seconds
 * DELETE /api/audios/[id]  — delete the audio
 *
 * Deleting an audio that has executions referencing it is handled
 * gracefully: we soft-warn (return 200 with a `warning` field listing
 * the count of executions that referenced it) rather than hard-failing.
 * The audio document itself is deleted; the executions remain with
 * their `audio_id` pointing to a now-missing record (the webapp renders
 * "[deleted audio]" in that case).
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { isValidUrl } from "@/lib/format";

type Ctx = { params: { id: string } };

export async function GET(_req: NextRequest, { params }: Ctx) {
  const db = await getDb();
  const doc = await db.collection("audios").findOne({ _id: new ObjectId(params.id) });
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ audio: stringifyIds(doc) });
}

export async function PUT(req: NextRequest, { params }: Ctx) {
  const body = await req.json().catch(() => ({}));
  const update: Record<string, unknown> = {};

  if (body.name !== undefined) {
    const name = String(body.name).trim();
    if (!name) return NextResponse.json({ error: "name cannot be empty" }, { status: 400 });
    update.name = name;
  }
  if (body.source_url !== undefined) {
    const url = String(body.source_url).trim();
    if (!isValidUrl(url)) {
      return NextResponse.json({ error: "source_url must be a valid http(s) URL" }, { status: 400 });
    }
    update.source_url = url;
  }
  if (body.duration_seconds !== undefined) {
    const dur = Number(body.duration_seconds);
    if (isNaN(dur) || dur < 0) {
      return NextResponse.json({ error: "duration_seconds must be a non-negative number" }, { status: 400 });
    }
    update.duration_seconds = dur;
  }

  if (Object.keys(update).length === 0) {
    return NextResponse.json({ error: "no fields to update" }, { status: 400 });
  }

  const db = await getDb();

  // Pre-flight duplicate-name check. `audios.name` has a unique index,
  // so without this check a duplicate would surface as a 500 from
  // findOneAndUpdate — we want a clean 409 instead.
  if (update.name !== undefined) {
    const dup = await db
      .collection("audios")
      .findOne({ name: update.name, _id: { $ne: new ObjectId(params.id) } });
    if (dup) {
      return NextResponse.json(
        { error: `an audio named '${update.name}' already exists` },
        { status: 409 },
      );
    }
  }

  const res = await db
    .collection("audios")
    .findOneAndUpdate(
      { _id: new ObjectId(params.id) },
      { $set: update },
      { returnDocument: "after" },
    );
  if (!res) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ audio: stringifyIds(res) });
}

export async function DELETE(_req: NextRequest, { params }: Ctx) {
  const db = await getDb();
  // Count executions referencing this audio so we can soft-warn.
  const refCount = await db
    .collection("executions")
    .countDocuments({ audio_id: new ObjectId(params.id) });

  const res = await db.collection("audios").deleteOne({ _id: new ObjectId(params.id) });
  if (res.deletedCount === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({
    deleted: true,
    warning: refCount > 0 ? `${refCount} execution(s) still reference this audio` : null,
  });
}
