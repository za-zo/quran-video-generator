/**
 * GET, PUT /api/slices/[id]
 *
 * PUT supports updating the user-managed fields on an execution slice:
 *   - posted_in  (string | null)  — account name where the video was posted
 *   - bad_result (boolean)         — flag for unsatisfactory results
 *
 * These fields are NOT set by the pipeline; they're curated by the
 * operator via the /slices/[id]/edit page to track which videos have
 * been published and which were deemed bad.
 */

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
  const doc = await db.collection("execution_slices").findOne({ _id: oid });
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ slice: stringifyIds(doc) });
}

export async function PUT(req: NextRequest, { params }: Ctx) {
  let oid: ObjectId;
  try {
    oid = new ObjectId(params.id);
  } catch {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }

  const body = await req.json().catch(() => ({}));
  const update: Record<string, unknown> = {};

  // posted_in: string or null (to clear it, send null or empty string)
  if (body.posted_in !== undefined) {
    const raw = body.posted_in;
    if (raw === null || raw === "") {
      update.posted_in = null;
    } else {
      const val = String(raw).trim();
      if (val.length > 200) {
        return NextResponse.json(
          { error: "posted_in must be 200 characters or fewer" },
          { status: 400 },
        );
      }
      update.posted_in = val;
    }
  }

  // bad_result: boolean
  if (body.bad_result !== undefined) {
    update.bad_result = Boolean(body.bad_result);
  }

  if (Object.keys(update).length === 0) {
    return NextResponse.json({ error: "no fields to update" }, { status: 400 });
  }

  const db = await getDb();
  const res = await db
    .collection("execution_slices")
    .findOneAndUpdate(
      { _id: oid },
      { $set: update },
      { returnDocument: "after" },
    );
  if (!res) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json({ slice: stringifyIds(res) });
}
