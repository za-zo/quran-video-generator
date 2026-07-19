/**

 * GET, PUT, DELETE /api/categories/[id]
 *
 * DELETE: requires the category to have no videos. If it has videos,
 * returns 409 with the count so the UI can prompt the user to
 * reassign or delete them first.
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

type Ctx = { params: { id: string } };

export async function GET(_req: NextRequest, { params }: Ctx) {
  const db = await getDb();
  const doc = await db.collection("categories").findOne({ _id: new ObjectId(params.id) });
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ category: stringifyIds(doc) });
}

export async function PUT(req: NextRequest, { params }: Ctx) {
  const body = await req.json().catch(() => ({}));
  const name = (body.name ?? "").toString().trim();
  if (!name) {
    return NextResponse.json({ error: "name cannot be empty" }, { status: 400 });
  }
  const db = await getDb();
  const res = await db
    .collection("categories")
    .findOneAndUpdate(
      { _id: new ObjectId(params.id) },
      { $set: { name } },
      { returnDocument: "after" },
    );
  if (!res) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ category: stringifyIds(res) });
}

export async function DELETE(_req: NextRequest, { params }: Ctx) {
  const db = await getDb();
  const videoCount = await db
    .collection("videos")
    .countDocuments({ category_id: new ObjectId(params.id) });
  if (videoCount > 0) {
    return NextResponse.json(
      {
        error: `cannot delete: category has ${videoCount} video(s). Reassign or delete them first.`,
        video_count: videoCount,
      },
      { status: 409 },
    );
  }
  const res = await db.collection("categories").deleteOne({ _id: new ObjectId(params.id) });
  if (res.deletedCount === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: true });
}
