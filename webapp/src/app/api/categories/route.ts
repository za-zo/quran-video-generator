/**

 * GET  /api/categories  — list all categories (with video counts)
 * POST /api/categories  — create a new category
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

export async function GET() {
  const db = await getDb();
  const cats = await db
    .collection("categories")
    .find({})
    .sort({ _id: 1 })
    .toArray();

  // Aggregate video counts per category in one pass.
  const counts = await db
    .collection("videos")
    .aggregate([
      { $group: { _id: "$category_id", count: { $sum: 1 } } },
    ])
    .toArray();
  const countMap = new Map(counts.map((c) => [String(c._id), c.count]));

  const out = cats.map((c) => ({
    ...stringifyIds(c),
    video_count: countMap.get(String(c._id)) ?? 0,
  }));
  return NextResponse.json({ categories: out });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const name = (body.name ?? "").toString().trim();
  if (!name) {
    return NextResponse.json({ error: "name is required" }, { status: 400 });
  }

  const db = await getDb();
  const existing = await db.collection("categories").findOne({ name });
  if (existing) {
    return NextResponse.json(
      { error: `a category named '${name}' already exists` },
      { status: 409 },
    );
  }

  const doc = {
    name,
    usage_count: 0,
    last_used_at: null,
    created_at: new Date(),
  };
  const res = await db.collection("categories").insertOne(doc);
  const inserted = await db.collection("categories").findOne({ _id: res.insertedId });
  return NextResponse.json({ category: stringifyIds(inserted) }, { status: 201 });
}
