/**

 * GET  /api/videos?category_id=...   — list videos (optionally filtered)
 * POST /api/videos                   — create a new video
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";
import { isValidUrl } from "@/lib/format";

export async function GET(req: NextRequest) {
  const db = await getDb();
  const categoryId = req.nextUrl.searchParams.get("category_id");

  const filter: Record<string, unknown> = {};
  if (categoryId) {
    try {
      filter.category_id = new ObjectId(categoryId);
    } catch {
      return NextResponse.json({ error: "invalid category_id" }, { status: 400 });
    }
  }

  const docs = await db
    .collection("videos")
    .find(filter)
    .sort({ _id: 1 })
    .toArray();
  return NextResponse.json({ videos: docs.map((d) => stringifyIds(d)) });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const categoryId = (body.category_id ?? "").toString().trim();
  const name = (body.name ?? "").toString().trim();
  const sourceUrl = (body.source_url ?? "").toString().trim();
  const durationSeconds = Number(body.duration_seconds ?? 0) || 0;

  if (!categoryId) return NextResponse.json({ error: "category_id is required" }, { status: 400 });
  if (!name) return NextResponse.json({ error: "name is required" }, { status: 400 });
  if (!sourceUrl || !isValidUrl(sourceUrl)) {
    return NextResponse.json({ error: "source_url must be a valid http(s) URL" }, { status: 400 });
  }

  let catOid: ObjectId;
  try {
    catOid = new ObjectId(categoryId);
  } catch {
    return NextResponse.json({ error: "invalid category_id" }, { status: 400 });
  }

  const db = await getDb();
  const cat = await db.collection("categories").findOne({ _id: catOid });
  if (!cat) return NextResponse.json({ error: "category not found" }, { status: 404 });

  const existing = await db.collection("videos").findOne({ category_id: catOid, name });
  if (existing) {
    return NextResponse.json({ error: `a video named '${name}' already exists in this category` }, { status: 409 });
  }

  const doc = {
    category_id: catOid,
    name,
    source_url: sourceUrl,
    duration_seconds: durationSeconds,
    usage_count: 0,
    last_used_at: null,
    created_at: new Date(),
  };
  const res = await db.collection("videos").insertOne(doc);
  const inserted = await db.collection("videos").findOne({ _id: res.insertedId });
  return NextResponse.json({ video: stringifyIds(inserted) }, { status: 201 });
}
