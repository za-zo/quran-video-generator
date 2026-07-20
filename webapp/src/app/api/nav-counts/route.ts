/**
 * GET /api/nav-counts — lightweight endpoint that returns just the
 * collection counts shown in the sidebar nav.
 *
 * This exists separately from /api/stats (which is heavy: it computes
 * most/least used, latest run, slices by status, etc.) because the nav
 * is rendered in the root layout and the counts need to refresh on
 * every navigation. A small dedicated endpoint keeps that refresh cheap.
 */

export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";

export async function GET() {
  try {
    const db = await getDb();
    const [audios, categories, videos, execs] = await Promise.all([
      db.collection("audios").countDocuments(),
      db.collection("categories").countDocuments(),
      db.collection("videos").countDocuments(),
      db.collection("executions").countDocuments(),
    ]);
    return NextResponse.json({ audios, categories, videos, execs });
  } catch {
    return NextResponse.json(
      { audios: 0, categories: 0, videos: 0, execs: 0 },
      { status: 200 },
    );
  }
}
