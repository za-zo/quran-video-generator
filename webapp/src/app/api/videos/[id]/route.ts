/**

 * GET, PUT, DELETE /api/videos/[id]
 *
 * PUT supports reassignment via `category_id` (used by the "reassign
 * before delete" flow on the categories page).
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
  const doc = await db.collection("videos").findOne({ _id: new ObjectId(params.id) });
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ video: stringifyIds(doc) });
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
  if (body.category_id !== undefined) {
    try {
      update.category_id = new ObjectId(body.category_id);
    } catch {
      return NextResponse.json({ error: "invalid category_id" }, { status: 400 });
    }
  }

  if (Object.keys(update).length === 0) {
    return NextResponse.json({ error: "no fields to update" }, { status: 400 });
  }

  const db = await getDb();
  const res = await db
    .collection("videos")
    .findOneAndUpdate(
      { _id: new ObjectId(params.id) },
      { $set: update },
      { returnDocument: "after" },
    );
  if (!res) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ video: stringifyIds(res) });
}

export async function DELETE(_req: NextRequest, { params }: Ctx) {
  const db = await getDb();
  const res = await db.collection("videos").deleteOne({ _id: new ObjectId(params.id) });
  if (res.deletedCount === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: true });
}
