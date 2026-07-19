export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

export async function GET(req: NextRequest) {
  const db = await getDb();
  const status = req.nextUrl.searchParams.get("status");
  const limit = Math.min(200, Number(req.nextUrl.searchParams.get("limit") ?? 50));

  const match: Record<string, unknown> = {};
  if (status && ["running", "success", "failed", "partial", "canceled"].includes(status)) {
    match.status = status;
  }

  // Returns runs from the executions collection
  const pipeline = [
    ...(Object.keys(match).length ? [{ $match: match }] : []),
    { $sort: { created_at: -1 } },
    { $limit: limit },
  ];

  const docs = await db.collection("executions").aggregate(pipeline).toArray();
  return NextResponse.json({ executions: docs.map((d) => stringifyIds(d)) });
}
