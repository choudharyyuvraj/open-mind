import { NextResponse } from "next/server"
import { ObjectId } from "mongodb"
import { dashboardCollections, ensureDashboardForUser } from "@/lib/dashboard-db"
import { getSessionUser } from "@/lib/require-session"
import type { MemoryIngestDetail } from "@/lib/types/dashboard"

export const runtime = "nodejs"

function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string") {
      const trimmed = value.trim()
      if (trimmed) return trimmed
    }
  }
  return null
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const session = await getSessionUser()
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  await ensureDashboardForUser(session.user._id)

  const { id } = await context.params
  let oid: ObjectId
  try {
    oid = new ObjectId(id)
  } catch {
    return NextResponse.json({ error: "Invalid id." }, { status: 400 })
  }

  const { activity } = await dashboardCollections()
  const row = await activity.findOne({
    _id: oid,
    userId: session.user._id,
    kind: "ingest",
  })

  if (!row) {
    return NextResponse.json({ error: "Not found." }, { status: 404 })
  }

  const meta = row.metadata ?? {}
  const stored =
    typeof meta.storedContent === "string" && meta.storedContent.length > 0
      ? meta.storedContent
      : null

  const body: MemoryIngestDetail = {
    id: String(row._id),
    createdAt: row.createdAt.toISOString(),
    summary: row.summary,
    sessionId: typeof meta.sessionId === "string" ? meta.sessionId : null,
    role: typeof meta.role === "string" ? meta.role : null,
    gatewayOk: typeof meta.ok === "boolean" ? meta.ok : null,
    gatewayStatus: typeof meta.gatewayStatus === "number" ? meta.gatewayStatus : null,
    latencyMs: typeof meta.latencyMs === "number" ? meta.latencyMs : null,
    storedContent: stored,
    contentLength: typeof meta.contentLength === "number" ? meta.contentLength : null,
    contentTruncated: meta.contentTruncated === true,
    assetId: typeof meta.assetId === "string" ? meta.assetId : null,
    filename: typeof meta.filename === "string" ? meta.filename : null,
    generationId: firstNonEmptyString(
      meta.generationId,
      meta.generation_id,
      meta.cursorGenerationId,
      meta.cursor_generation_id,
      meta.mcp_generation_id,
    ),
    conversationId: firstNonEmptyString(
      meta.conversationId,
      meta.conversation_id,
      meta.cursorConversationId,
      meta.cursor_conversation_id,
      meta.mcp_conversation_id,
    ),
    cursorGenerationId: firstNonEmptyString(
      meta.generationId,
      meta.generation_id,
      meta.cursorGenerationId,
      meta.cursor_generation_id,
      meta.mcp_generation_id,
    ),
    cursorConversationId: firstNonEmptyString(
      meta.conversationId,
      meta.conversation_id,
      meta.cursorConversationId,
      meta.cursor_conversation_id,
      meta.mcp_conversation_id,
    ),
    clientType: firstNonEmptyString(meta.clientType, meta.client_type),
    source: firstNonEmptyString(meta.source),
  }

  return NextResponse.json(body)
}
