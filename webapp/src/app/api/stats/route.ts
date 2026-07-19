export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

export async function GET() {
  const db = await getDb();

  const [audios, categories, videos, runCounts, sliceCounts, latestRun] =
    await Promise.all([
      db.collection("audios").countDocuments(),
      db.collection("categories").countDocuments(),
      db.collection("videos").countDocuments(),
      db
        .collection("executions")
        .aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])
        .toArray(),
      db
        .collection("execution_slices")
        .aggregate([{ $group: { _id: "$status", count: { $sum: 1 } } }])
        .toArray(),
      db.collection("executions").findOne({}, { sort: { created_at: -1 } }),
    ]);

  const runsByStatus: Record<string, number> = {
    running: 0,
    success: 0,
    failed: 0,
    partial: 0,
    canceled: 0,
  };
  for (const c of runCounts) runsByStatus[c._id] = c.count;

  const slicesByStatus: Record<string, number> = {
    pending: 0,
    success: 0,
    failed: 0,
    canceled: 0,
  };
  for (const c of sliceCounts) slicesByStatus[c._id] = c.count;

  const runsTotal = Object.values(runsByStatus).reduce((a, b) => a + b, 0);
  const slicesTotal = Object.values(slicesByStatus).reduce((a, b) => a + b, 0);

  // Most/least used
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
      ? { id: String(allAudios[0]._id), name: allAudios[0].name, usage_count: allAudios[0].usage_count }
      : null;
  const leastUsedAudio =
    allAudios.length > 0
      ? { id: String(allAudios[allAudios.length - 1]._id), name: allAudios[allAudios.length - 1].name, usage_count: allAudios[allAudios.length - 1].usage_count }
      : null;
  const mostUsedCategory =
    allCategories.length > 0 && allCategories[0].usage_count > 0
      ? { id: String(allCategories[0]._id), name: allCategories[0].name, usage_count: allCategories[0].usage_count }
      : null;
  const leastUsedCategory =
    allCategories.length > 0
      ? { id: String(allCategories[allCategories.length - 1]._id), name: allCategories[allCategories.length - 1].name, usage_count: allCategories[allCategories.length - 1].usage_count }
      : null;

  // Latest run with audio name (lookup from slices)
  let latestExecution = null;
  if (latestRun) {
    const latestSlice = await db.collection("execution_slices").findOne(
      { execution_id: String(latestRun._id) },
      { sort: { created_at: -1 } },
    );
    let audioName = "[no slices]";
    if (latestSlice?.audio_id) {
      try {
        const { ObjectId } = await import("mongodb");
        const audio = await db.collection("audios").findOne({ _id: new ObjectId(latestSlice.audio_id) });
        if (audio) audioName = audio.name;
      } catch {}
    }
    latestExecution = {
      id: String(latestRun._id),
      status: latestRun.status,
      created_at: latestRun.created_at,
      audio_name: audioName,
    };
  }

  const stats = {
    audios,
    categories,
    videos,
    executions_by_status: {
      ...runsByStatus,
      // also include slice counts for backwards compat
      pending: slicesByStatus.pending || 0,
    },
    executions_total: slicesTotal,
    runs_total: runsTotal,
    slices_total: slicesTotal,
    most_used_audio: mostUsedAudio,
    least_used_audio: leastUsedAudio,
    most_used_category: mostUsedCategory,
    least_used_category: leastUsedCategory,
    latest_execution: latestExecution,
  };

  return NextResponse.json({ stats: stringifyIds(stats) });
}
