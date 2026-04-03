import { NextResponse } from "next/server"
import { dashboardCollections, ensureDashboardForUser } from "@/lib/dashboard-db"
import { forwardSubnetJson, getSubnetGatewayBaseUrl } from "@/lib/gateway-proxy"
import { getSessionUser } from "@/lib/require-session"

export const runtime = "nodejs"

export async function GET() {
  const session = await getSessionUser()
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  await ensureDashboardForUser(session.user._id)
  const { stats, activity } = await dashboardCollections()
  const st = await stats.findOne({ userId: session.user._id })

  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
  const [ingestWeek, queryWeek] = await Promise.all([
    activity.countDocuments({ userId: session.user._id, kind: "ingest", createdAt: { $gte: weekAgo } }),
    activity.countDocuments({ userId: session.user._id, kind: "query", createdAt: { $gte: weekAgo } }),
  ])

  const chunks = st?.storedChunks ?? 0

  let gatewayOk: boolean | null = null
  let durabilityMeta = "Local memory durability summary."
  if (getSubnetGatewayBaseUrl()) {
    const gh = await forwardSubnetJson("/v1/health", { method: "GET" })
    gatewayOk = gh.ok
    durabilityMeta = gatewayOk
      ? "Gateway health check OK"
      : "Gateway configured but unreachable"
  }

  const activitySignal = Math.min(100, ingestWeek * 4 + queryWeek * 2)
  const chunkSignal = Math.min(100, chunks)
  const baseSignal = gatewayOk === false ? 0 : gatewayOk === true ? 35 : 20
  const coveragePercent = Math.max(
    0,
    Math.min(100, Math.round(baseSignal + activitySignal * 0.4 + chunkSignal * 0.25)),
  )

  return NextResponse.json({
    summary: {
      label: "Default durability",
      description: "Local-memory durability estimate from gateway health, activity, and persisted chunk volume.",
      coveragePercent,
      meta: `${durabilityMeta} · ${ingestWeek} ingest events (7d) · ${queryWeek} queries (7d) · ${chunks} stored chunks`,
    },
    repairQueue: [
      {
        id: "rq-1",
        label: "Shard verification sweep",
        status: gatewayOk === false ? "degraded" : "nominal",
        detail:
          gatewayOk === false
            ? "Gateway unreachable — check SUBNET_GATEWAY_URL"
            : gatewayOk === true
              ? "Validator health OK"
              : "Gateway not configured",
      },
    ],
    storedChunks: chunks,
    gatewayConfigured: Boolean(getSubnetGatewayBaseUrl()),
    gatewayReachable: gatewayOk,
  })
}
