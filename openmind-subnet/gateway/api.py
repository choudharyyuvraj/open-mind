"""
FastAPI REST gateway for OpenMind local mode.

This gateway processes requests in-process without Bittensor miner/validator
transport.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from gateway.mcp_server import mcp
from gateway.models import (
    ChatRequest,
    ChatResponse,
    CheckpointResumeRequest,
    CheckpointSaveRequest,
    CompactRequest,
    HealthResponse,
    MemoryResult,
    QueryRequest,
    SharedSpaceQueryRequest,
    StoreRequest,
    VersionRequest,
)
from openmind.extraction import extract_temporal
from openmind.local_processor import process_request
from openmind.protocol import OpenMindRequest


_mcp_http_app = mcp.streamable_http_app()
_mcp_streamable_endpoint = _mcp_http_app.routes[0].endpoint


@asynccontextmanager
async def _gateway_lifespan(app: FastAPI):
    logging.getLogger("uvicorn.error").info(
        "OpenMind gateway running in local mode (no Bittensor dependency)."
    )
    # FastMCP streamable HTTP transport requires its session manager task-group
    # to be started during app lifespan; otherwise /mcp returns 500.
    async with _mcp_streamable_endpoint.session_manager.run():
        yield


app = FastAPI(
    title="OpenMind Gateway",
    version="0.1.0",
    lifespan=_gateway_lifespan,
)

# Expose MCP transport for connector-based clients.
# We proxy /mcp to the FastMCP ASGI app in-process (no outbound self-HTTP),
# which avoids DNS issues and keeps /v1 REST routes unaffected.


@app.api_route("/mcp", methods=["GET", "POST", "OPTIONS"])
@app.api_route("/mcp/", methods=["GET", "POST", "OPTIONS"])
async def mcp_entrypoint(request: Request) -> Response:
    import httpx

    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"content-length"}
    }
    # Some MCP clients omit the required streamable Accept value.
    # Normalize case-insensitively and ensure upstream always sees text/event-stream.
    accept = ""
    for k in list(headers.keys()):
        if k.lower() == "accept":
            accept = headers.pop(k)
            break
    if "text/event-stream" not in accept.lower():
        accept = f"{accept}, text/event-stream" if accept else "application/json, text/event-stream"
    headers["Accept"] = accept

    transport = httpx.ASGITransport(app=_mcp_http_app)
    incoming_host = request.headers.get("host", "localhost")
    incoming_scheme = request.url.scheme or "http"
    async with httpx.AsyncClient(
        transport=transport,
        base_url=f"{incoming_scheme}://{incoming_host}",
    ) as client:
        upstream = await client.request(
            method=request.method,
            url="/mcp",
            headers=headers,
            params=request.query_params,
            content=body if body else None,
        )

    passthrough_headers: Dict[str, str] = {}
    for h in ("content-type", "cache-control", "www-authenticate"):
        if h in upstream.headers:
            passthrough_headers[h] = upstream.headers[h]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=passthrough_headers,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).parent / "static"
_chat_env_loaded = False


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(_STATIC_DIR / "index.html")


def configure(_unused: Any = None) -> None:
    """Compatibility no-op for legacy validator bootstrap paths."""
    return


def _load_gateway_env_once() -> None:
    """Load gateway/.env once if OPENAI_API_KEY isn't present in process env."""
    global _chat_env_loaded
    if _chat_env_loaded:
        return
    _chat_env_loaded = True
    if os.environ.get("OPENAI_API_KEY"):
        return

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("export "):
                s = s[len("export "):]
            if "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return


async def _query_local(synapse: OpenMindRequest) -> List[Any]:
    """Process a request via the local in-process runtime."""
    response = process_request(synapse)
    return [response]


async def _call_openai_chat(model: str, prompt: str) -> str:
    """Call OpenAI-compatible chat endpoint using server-side env credentials."""
    import httpx

    _load_gateway_env_once()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY not configured in server environment or gateway/.env",
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": "You are a concise assistant integrated with OpenMind memory."},
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {resp.text[:400]}")
        data = resp.json()
        return (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()


def _expand_time_references(query: Optional[str]) -> tuple:
    """Resolve relative time expressions in a query. Returns (expanded_query, resolved_date)."""
    if not query:
        return query, None
    resolved = extract_temporal(query)
    if resolved:
        return f"{query} [resolved: {resolved}]", resolved
    return query, None


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _best_response(responses: List[Any]) -> MemoryResult:
    """Pick the response with the most results (simple heuristic)."""
    best: Optional[Any] = None
    best_count = -1
    for r in responses:
        results = getattr(r, "results", None) or []
        if len(results) > best_count:
            best = r
            best_count = len(results)
    if best is None:
        return MemoryResult()
    return MemoryResult(
        results=getattr(best, "results", []),
        version_diff=getattr(best, "version_diff", None),
        provenance_path=getattr(best, "provenance_path", None),
        checkpoint=getattr(best, "checkpoint", None),
    )


@app.post("/v1/memory/store", response_model=MemoryResult)
async def memory_store(body: StoreRequest):
    synapse = OpenMindRequest(
        session_id=body.session_id,
        query=body.content,
        embedding=body.embedding,
        event_at=body.event_at,
        filters={**body.filters, "_action": "store", "_role": body.role},
        multimodal_type=body.multimodal_type,
        shared_space_id=body.shared_space_id,
        author=body.author,
        auth_metadata=body.auth_metadata,
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/memory/query", response_model=MemoryResult)
async def memory_query(body: QueryRequest):
    expanded_query, resolved_time = _expand_time_references(body.query)

    action = "_action"
    filters = dict(body.filters)
    if body.smart:
        filters[action] = "query_smart"
    if resolved_time:
        filters["_resolved_time"] = resolved_time

    synapse = OpenMindRequest(
        session_id=body.session_id,
        query=expanded_query,
        embedding=body.embedding,
        top_k=body.top_k,
        as_of_timestamp=resolved_time,
        filters=filters,
        multimodal_type=body.multimodal_type,
    )
    responses = await _query_local(synapse)
    result = _best_response(responses)

    if result.results and isinstance(result.results[0], dict):
        smart_data = result.results[0]
        if "facts" in smart_data:
            result.anchor = smart_data.get("anchor")
            result.facts = smart_data.get("facts")
            result.sources = smart_data.get("sources")

            all_text = ""
            if result.anchor:
                all_text += result.anchor.get("content", "") + " "
            for f in (result.facts or []):
                all_text += f.get("content", "") + " "
            for s in (result.sources or []):
                all_text += s.get("content", "") + " "
            result.token_estimate = _estimate_tokens(all_text)

    return result


@app.post("/v1/memory/compact", response_model=MemoryResult)
async def memory_compact(body: CompactRequest):
    synapse = OpenMindRequest(
        session_id=body.session_id,
        filters={"_action": "compact"},
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/memory/version", response_model=MemoryResult)
async def memory_version(body: VersionRequest):
    synapse = OpenMindRequest(
        session_id=body.session_id,
        as_of_timestamp=body.as_of_timestamp,
        version_id=body.version_id,
        diff_since=body.diff_since,
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/checkpoint/save", response_model=MemoryResult)
async def checkpoint_save(body: CheckpointSaveRequest):
    synapse = OpenMindRequest(
        session_id=f"checkpoint-{body.workflow_id}",
        workflow_id=body.workflow_id,
        query=f"checkpoint-step-{body.step}",
        filters={"_action": "checkpoint_save", "step": body.step, "state": body.state},
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/checkpoint/resume", response_model=MemoryResult)
async def checkpoint_resume(body: CheckpointResumeRequest):
    synapse = OpenMindRequest(
        session_id=f"checkpoint-{body.workflow_id}",
        workflow_id=body.workflow_id,
        resume_from_checkpoint=True,
        filters={"_action": "checkpoint_resume"},
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/space/query", response_model=MemoryResult)
async def space_query(body: SharedSpaceQueryRequest):
    synapse = OpenMindRequest(
        session_id=body.session_id,
        query=body.query,
        embedding=body.embedding,
        top_k=body.top_k,
        shared_space_id=body.shared_space_id,
        author=body.author,
        auth_metadata=body.auth_metadata,
    )
    responses = await _query_local(synapse)
    return _best_response(responses)


@app.post("/v1/chat/respond", response_model=ChatResponse)
async def chat_respond(body: ChatRequest):
    expanded_query, resolved_time = _expand_time_references(body.user_message)
    synapse = OpenMindRequest(
        session_id=body.session_id,
        query=expanded_query,
        top_k=body.top_k,
        as_of_timestamp=resolved_time,
        filters={"_action": "query_smart"},
    )
    responses = await _query_local(synapse)
    result = _best_response(responses)

    anchor = None
    facts: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    if result.results and isinstance(result.results[0], dict):
        smart_data = result.results[0]
        if "facts" in smart_data:
            anchor = smart_data.get("anchor")
            facts = smart_data.get("facts") or []
            sources = smart_data.get("sources") or []

    ctx_parts: List[str] = []
    if anchor and isinstance(anchor, dict):
        a = anchor.get("content", "")
        if a:
            ctx_parts.append("Session anchor:\n" + a)
    if facts:
        lines = [f"- {f.get('content','')}" for f in facts[:20] if f.get("content")]
        if lines:
            ctx_parts.append("Facts:\n" + "\n".join(lines))
    if sources:
        lines = [f"- {(s.get('content','') or '')[:400]}" for s in sources[:8]]
        if lines:
            ctx_parts.append("Source snippets:\n" + "\n".join(lines))

    context_text = "\n\n".join([p for p in ctx_parts if p]).strip()
    prompt = (
        "Use only the provided memory context and user message.\n"
        "If memory is insufficient, say what is missing.\n\n"
        f"Memory context:\n{context_text or '(none)'}\n\n"
        f"User:\n{body.user_message}"
    )

    response_text = await _call_openai_chat(body.model, prompt)
    return ChatResponse(
        response=response_text,
        model=body.model,
        token_estimate=_estimate_tokens(context_text),
    )


@app.get("/v1/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        subtensor=False,
        metagraph_n=0,
        dendrite=False,
        validator_step=0,
    )
