import { NextResponse } from "next/server"
import { ObjectId } from "mongodb"
import { dashboardCollections, ensureDashboardForUser } from "@/lib/dashboard-db"
import { getSessionUser } from "@/lib/require-session"
import { buildMemoryIndexList } from "@/lib/memory-index-grouping"
import type { MemoryIndexResponse } from "@/lib/types/dashboard"

export const runtime = "nodejs"

const DEFAULT_LIMIT = 40
const MAX_LIMIT = 100

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string") {
      const trimmed = value.trim()
      if (trimmed) return trimmed
    }
  }
  return null
}

export async function GET(request: Request) {
  const session = await getSessionUser()
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  await ensureDashboardForUser(session.user._id)

  const { searchParams } = new URL(request.url)
  const limit = Math.min(
    MAX_LIMIT,
    Math.max(1, Number(searchParams.get("limit")) || DEFAULT_LIMIT),
  )
  const cursor = searchParams.get("cursor")
  const q = (searchParams.get("q") ?? "").trim()
  const sessionOnly = (searchParams.get("session") ?? "").trim()

  const { activity } = await dashboardCollections()

  const filter: Record<string, unknown> = {
    userId: session.user._id,
    kind: "ingest",
  }

  if (cursor) {
    try {
      filter._id = { $lt: new ObjectId(cursor) }
    } catch {
      return NextResponse.json({ error: "Invalid cursor." }, { status: 400 })
    }
  }

  const extraAnd: object[] = []
  if (sessionOnly) {
    extraAnd.push({ "metadata.sessionId": sessionOnly })
  }
  if (q) {
    const safe = escapeRegex(q)
    extraAnd.push({
      $or: [
        { summary: { $regex: safe, $options: "i" } },
        { "metadata.sessionId": { $regex: safe, $options: "i" } },
        { "metadata.cursorGenerationId": { $regex: safe, $options: "i" } },
      ],
    })
  }
  if (extraAnd.length) {
    filter.$and = extraAnd
  }

  const rows = await activity.find(filter).sort({ _id: -1 }).limit(limit + 1).toArray()

  const slice = rows.slice(0, limit)
  const items = slice.map((row) => {
    const meta = row.metadata ?? {}
    const stored = typeof meta.storedContent === "string" ? meta.storedContent : ""
    const generationId = firstNonEmptyString(
      meta.generationId,
      meta.generation_id,
      meta.cursorGenerationId,
      meta.cursor_generation_id,
      meta.mcp_generation_id,
    )
    const conversationId = firstNonEmptyString(
      meta.conversationId,
      meta.conversation_id,
      meta.cursorConversationId,
      meta.cursor_conversation_id,
      meta.mcp_conversation_id,
    )
    return {
      id: String(row._id),
      createdAt: row.createdAt.toISOString(),
      sessionId: typeof meta.sessionId === "string" ? meta.sessionId : null,
      summary: row.summary,
      role: typeof meta.role === "string" ? meta.role : null,
      gatewayOk: typeof meta.ok === "boolean" ? meta.ok : null,
      gatewayStatus: typeof meta.gatewayStatus === "number" ? meta.gatewayStatus : null,
      hasStoredContent: stored.length > 0,
      generationId,
      conversationId,
      cursorGenerationId: generationId,
      cursorConversationId: conversationId,
      clientType: firstNonEmptyString(meta.clientType, meta.client_type),
      source: firstNonEmptyString(meta.source),
    }
  })

  const nextCursor = rows.length > limit ? String(slice[slice.length - 1]!._id) : null

  const body: MemoryIndexResponse = {
    items: buildMemoryIndexList(items),
    nextCursor,
  }
  return NextResponse.json(body)
}
