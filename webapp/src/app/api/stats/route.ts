/**

 * GET /api/stats — aggregated dashboard metrics.
 *
 * Returns counts + most/least used audio + most/least used category +
 * the latest execution (with the audio name joined in). All in one
 * round-trip so the dashboard can render server-side without N+1.
 */

export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds, type DashboardStats } from "@/lib/types";

export async function GET() {
  const db = await getDb();

  const [audios, categories, videos, execCounts, latestPipeline] =
    await Promise.all([
      db.collection("audios").countDocuments(),
      db.collection("categories").countDocuments(),
      db.collection("videos").countDocuments(),
      db
        .collection("executions")
        .aggregate([
          { $group: { _id: "$status", count: { $sum: 1 } } },
        ])
        .toArray(),
      db
        .collection("executions")
        .aggregate([
          { $sort: { created_at: -1 } },
          { $limit: 1 },
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
            $project: {
              _id: 1,
              status: 1,
              created_at: 1,
              audio_name: { $ifNull: ["$_audio.name", "[deleted audio]"] },
            },
          },
        ])
        .toArray(),
    ]);

  const execByStatus: Record<string, number> = {
    pending: 0,
    success: 0,
    failed: 0,
  };
  for (const c of execCounts) {
    execByStatus[c._id] = c.count;
  }

  // Most/least used audios — fetch all, then sort in JS (small N).
  const allAudios = await db
    .collection("audios")
    .find({})
    .sort({ usage_count: -1 })
    .toArray();
  const allCategories = await db
    .collection("categories")
    .find({})
    .sort({ usage_count: -1 })
    .toArray();

  const mostUsedAudio =
    allAudios.length > 0 && allAudios[0].usage_count > 0
      ? {
          id: String(allAudios[0]._id),
          name: allAudios[0].name,
          usage_count: allAudios[0].usage_count,
        }
      : null;
  const leastUsedAudio =
    allAudios.length > 0
      ? {
          id: String(allAudios[allAudios.length - 1]._id),
          name: allAudios[allAudios.length - 1].name,
          usage_count: allAudios[allAudios.length - 1].usage_count,
        }
      : null;

  const mostUsedCategory =
    allCategories.length > 0 && allCategories[0].usage_count > 0
      ? {
          id: String(allCategories[0]._id),
          name: allCategories[0].name,
          usage_count: allCategories[0].usage_count,
        }
      : null;
  const leastUsedCategory =
    allCategories.length > 0
      ? {
          id: String(allCategories[allCategories.length - 1]._id),
          name: allCategories[allCategories.length - 1].name,
          usage_count: allCategories[allCategories.length - 1].usage_count,
        }
      : null;

  const latest = latestPipeline[0] ?? null;
  const stats: DashboardStats = {
    audios,
    categories,
    videos,
    executions_by_status: {
      pending: execByStatus.pending || 0,
      success: execByStatus.success || 0,
      failed: execByStatus.failed || 0,
    },
    executions_total:
      (execByStatus.pending || 0) +
      (execByStatus.success || 0) +
      (execByStatus.failed || 0),
    most_used_audio: mostUsedAudio,
    least_used_audio: leastUsedAudio,
    most_used_category: mostUsedCategory,
    least_used_category: leastUsedCategory,
    latest_execution: latest
      ? {
          id: String(latest._id),
          status: latest.status,
          created_at: latest.created_at,
          audio_name: latest.audio_name,
        }
      : null,
  };

  return NextResponse.json({ stats: stringifyIds(stats) });
}
