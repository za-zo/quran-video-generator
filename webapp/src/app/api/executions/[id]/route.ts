export const dynamic = "force-dynamic";

import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "mongodb";
import { getDb } from "@/lib/mongo";
import { stringifyIds } from "@/lib/types";

type Ctx = { params: { id: string } };

export async function GET(_req: NextRequest, { params }: Ctx) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(params.id);
  } catch {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }

  const db = await getDb();

  // First try execution_slices (individual clips)
  let doc = await db.collection("execution_slices").findOne({ _id: oid });

  // If not found, try executions (runs) — return run info with its slices
  if (!doc) {
    const run = await db.collection("executions").findOne({ _id: oid });
    if (!run) {
      return NextResponse.json({ error: "not found" }, { status: 404 });
    }
    // Return the run document (no audio/video lookups needed for runs)
    return NextResponse.json({ execution: stringifyIds(run), type: "run" });
  }

  // Enrich the slice with audio, category, videos
  const pipeline = [
    { $match: { _id: oid } },
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
      $lookup: {
        from: "videos",
        localField: "selected_video_ids",
        foreignField: "_id",
        as: "_videos",
      },
    },
    {
      $project: {
        _id: 1,
        execution_id: 1,
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
        audio: {
          _id: { $ifNull: ["$_audio._id", null] },
          name: { $ifNull: ["$_audio.name", null] },
          source_url: { $ifNull: ["$_audio.source_url", null] },
          duration_seconds: { $ifNull: ["$_audio.duration_seconds", 0] },
        },
        category: {
          _id: { $ifNull: ["$_category._id", null] },
          name: { $ifNull: ["$_category.name", null] },
        },
        videos: {
          $map: {
            input: "$_videos",
            as: "v",
            in: {
              _id: "$$v._id",
              name: "$$v.name",
              source_url: "$$v.source_url",
              duration_seconds: "$$v.duration_seconds",
            },
          },
        },
      },
    },
  ];

  const docs = await db.collection("execution_slices").aggregate(pipeline).toArray();
  if (docs.length === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ execution: stringifyIds(docs[0]), type: "slice" });
}
