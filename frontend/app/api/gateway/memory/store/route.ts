import { NextResponse } from "next/server"
import { recordActivity } from "@/lib/record-activity"
import { syncStoredChunksFromGatewayStore } from "@/lib/dashboard-db"
import { forwardSubnetJson } from "@/lib/gateway-proxy"
import { getGatewayAuth, gatewayUnauthorized } from "@/lib/gateway-auth"
import { subnetSessionIdForUser } from "@/lib/subnet-session"
import { MAX_ACTIVITY_STORED_CONTENT } from "@/lib/memory-ingest-limits"

export const runtime = "nodejs"

function firstNonEmptyString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string") {
      const trimmed = value.trim()
      if (trimmed) return trimmed
    }
  }
  return ""
}

export async function POST(request: Request) {
  const auth = await getGatewayAuth(request)
  if (auth instanceof NextResponse) return auth
  if (!auth) {
    return gatewayUnauthorized(request)
  }

  let body: Record<string, unknown> = {}
  try {
    body = (await request.json()) as Record<string, unknown>
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }

  const userId = String(auth.userId)
  const content = typeof body.content === "string" ? body.content : ""
  if (!content.trim()) {
    return NextResponse.json({ error: "content is required." }, { status: 400 })
  }

  const rawAuth =
    typeof body.auth_metadata === "object" &&
    body.auth_metadata !== null &&
    !Array.isArray(body.auth_metadata)
      ? { ...(body.auth_metadata as Record<string, unknown>) }
      : {}

  const generationId = firstNonEmptyString(
    body.generation_id,
    body.cursor_generation_id,
    rawAuth.generation_id,
    rawAuth.cursor_generation_id,
    rawAuth.mcp_generation_id,
  )
  const conversationId = firstNonEmptyString(
    body.conversation_id,
    body.cursor_conversation_id,
    rawAuth.conversation_id,
    rawAuth.cursor_conversation_id,
    rawAuth.mcp_conversation_id,
  )
  const clientType = firstNonEmptyString(body.client_type, rawAuth.client_type)
  const source = firstNonEmptyString(body.source, rawAuth.source)

  if (generationId) {
    rawAuth.generation_id = generationId
    rawAuth.cursor_generation_id = generationId
  }
  if (conversationId) {
    rawAuth.conversation_id = conversationId
    rawAuth.cursor_conversation_id = conversationId
  }
  if (clientType) {
    rawAuth.client_type = clientType
  }
  if (source) {
    rawAuth.source = source
  }

  const payload = {
    session_id: typeof body.session_id === "string" ? body.session_id : subnetSessionIdForUser(userId),
    content,
    role: typeof body.role === "string" ? body.role : "user",
    event_at: typeof body.event_at === "string" ? body.event_at : undefined,
    multimodal_type: typeof body.multimodal_type === "string" ? body.multimodal_type : undefined,
    embedding: Array.isArray(body.embedding) ? body.embedding : undefined,
    filters: typeof body.filters === "object" && body.filters !== null ? body.filters : {},
    shared_space_id: typeof body.shared_space_id === "string" ? body.shared_space_id : undefined,
    author: typeof body.author === "string" ? body.author : undefined,
    auth_metadata: rawAuth,
  }

  const t0 = Date.now()
  const out = await forwardSubnetJson("/v1/memory/store", {
    method: "POST",
    jsonBody: payload,
  })
  const latencyMs = Date.now() - t0

  const preview = content.slice(0, 120)
  const truncated = content.length > MAX_ACTIVITY_STORED_CONTENT
  await recordActivity({
    userId: auth.userId,
    kind: "ingest",
    summary: preview + (content.length > 120 ? "…" : ""),
    metadata: {
      ok: out.ok,
      latencyMs,
      gatewayStatus: out.status,
      sessionId: payload.session_id,
      role: payload.role,
      storedContent: content.slice(0, MAX_ACTIVITY_STORED_CONTENT),
      contentLength: content.length,
      contentTruncated: truncated,
      ...(generationId ? { generationId, cursorGenerationId: generationId } : {}),
      ...(conversationId
        ? { conversationId, cursorConversationId: conversationId }
        : {}),
      ...(clientType ? { clientType } : {}),
      ...(source ? { source } : {}),
    },
  })

  if (out.ok) {
    await syncStoredChunksFromGatewayStore(auth.userId, out.data, payload.session_id)
  }

  return NextResponse.json(out.data, { status: out.ok ? 200 : out.status })
}
