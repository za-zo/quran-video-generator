/**
 * TypeScript types mirroring the MongoDB collections owned by the Python
 * pipeline (see src/database/repository.py).
 *
 * Field names here MUST stay in sync with the Python side so the webapp
 * and the pipeline read/write the same documents.
 */

import type { ObjectId } from "mongodb";

export interface AudioDoc {
  _id: ObjectId | string;
  name: string;
  source_url: string;
  duration_seconds: number;
  usage_count: number;
  last_used_at: Date | null;
  created_at: Date;
}

export interface CategoryDoc {
  _id: ObjectId | string;
  name: string;
  usage_count: number;
  last_used_at: Date | null;
  created_at?: Date;
}

export interface VideoDoc {
  _id: ObjectId | string;
  category_id: ObjectId | string;
  name: string;
  source_url: string;
  duration_seconds: number;
  usage_count: number;
  last_used_at: Date | null;
  created_at: Date;
}

export interface ExecutionSlice {
  index: number;
  start_seconds: number;
  end_seconds: number;
  duration_seconds: number;
}

export interface ExecutionOutput {
  cloudinary_url: string;
  cloudinary_public_id: string;
  duration_seconds: number;
  width: number;
  height: number;
}

export type ExecutionStatus = "pending" | "success" | "failed";

export interface ExecutionDoc {
  _id: ObjectId | string;
  audio_id: ObjectId | string;
  status: ExecutionStatus;
  error_message: string | null;
  slice: ExecutionSlice;
  selected_category_id: ObjectId | string | null;
  selected_video_ids: (ObjectId | string)[];
  output: ExecutionOutput | null;
  github_run_id: string;
  created_at: Date;
  completed_at: Date | null;
}

// Convenience type used by the dashboard stats endpoint.
export interface DashboardStats {
  audios: number;
  categories: number;
  videos: number;
  executions_by_status: Record<ExecutionStatus, number>;
  executions_total: number;
  most_used_audio: { id: string; name: string; usage_count: number } | null;
  least_used_audio: { id: string; name: string; usage_count: number } | null;
  most_used_category: { id: string; name: string; usage_count: number } | null;
  least_used_category: { id: string; name: string; usage_count: number } | null;
  latest_execution: {
    id: string;
    status: ExecutionStatus;
    created_at: Date;
    audio_name: string;
  } | null;
}

// Stringify every ObjectId-shaped field so the client never sees a raw
// ObjectId (which would crash JSON.stringify in the browser).
export function stringifyIds<T>(doc: T): T {
  if (!doc || typeof doc !== "object") return doc;
  const out: any = Array.isArray(doc) ? [] : {};
  for (const [k, v] of Object.entries(doc as any)) {
    if (v && typeof v === "object" && "_bsontype" in v) {
      out[k] = v.toString();
    } else if (Array.isArray(v)) {
      out[k] = v.map((item) =>
        item && typeof item === "object" && "_bsontype" in item
          ? item.toString()
          : stringifyIds(item),
      );
    } else if (v && typeof v === "object" && !(v instanceof Date)) {
      out[k] = stringifyIds(v);
    } else {
      out[k] = v;
    }
  }
  return out;
}
