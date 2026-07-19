/**

 * GET /api/executions?status=...&limit=...
 *
 * Returns executions joined with their audio name + category name +
 * selected video names so the list page can render without N+1 queries
 * from the client. Uses a MongoDB aggregation pipeline.
 */

export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

export async function GET(req: NextRequest) {
  const db = await getDb();
  const status = req.nextUrl.searchParams.get("status");
  const limit = Math.min(200, Number(req.nextUrl.searchParams.get("limit") ?? 50));

  const match: Record<string, unknown> = {};
  if (status && ["pending", "success", "failed"].includes(status)) {
    match.status = status;
  }

  const pipeline = [
    ...(Object.keys(match).length ? [{ $match: match }] : []),
    { $sort: { created_at: -1 } },
    { $limit: limit },
    {
      $lookup: {
        from: "audios",
        localField: "audio_id",
        foreignField: "_id",
        as: "_audio",
      },
    },
    { $unwind: { path: "$_audio", preserveNullAndEmptyArrays: true } },
    {
      $lookup: {
        from: "categories",
        localField: "selected_category_id",
        foreignField: "_id",
        as: "_category",
      },
    },
    { $unwind: { path: "$_category", preserveNullAndEmptyArrays: true } },
    {
      $project: {
        _id: 1,
        audio_id: 1,
        status: 1,
        error_message: 1,
        slice: 1,
        selected_category_id: 1,
        selected_video_ids: 1,
        output: 1,
        github_run_id: 1,
        created_at: 1,
        completed_at: 1,
        audio_name: { $ifNull: ["$_audio.name", "[deleted audio]"] },
        audio_duration: { $ifNull: ["$_audio.duration_seconds", 0] },
        category_name: { $ifNull: ["$_category.name", null] },
      },
    },
  ];

  const docs = await db.collection("executions").aggregate(pipeline).toArray();
  return NextResponse.json({ executions: docs.map((d) => stringifyIds(d)) });
}
