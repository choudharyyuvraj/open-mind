# OpenMind Project Runbook

This runbook explains what the project contains, how components connect, and how to run everything locally with Cursor MCP.

## 1) Project Overview

The project has two main runtime components:

- Frontend (Next.js): dashboard UI, auth, API key management, BFF proxy routes
- Backend gateway (FastAPI): memory/query/checkpoint APIs and MCP transport endpoint

Key behavior:

- Cursor MCP calls should go through the frontend BFF (`http://127.0.0.1:3000`) so dashboard activity/search visibility is preserved.
- Backend runs on `http://127.0.0.1:8090`.

## 2) Architecture in Practice

- Cursor MCP client -> `gateway.mcp_server` (stdio)
- `gateway.mcp_server` -> frontend BFF (`/api/gateway/*`) using Bearer `om_live_*` API key
- Frontend BFF -> backend gateway (`SUBNET_GATEWAY_URL`)
- Dashboard reads activity/memory index from Mongo-backed APIs

## 3) Prerequisites

- Windows PowerShell
- Python 3.10+ (recommended)
- Node.js 20.x (project expects this; Node 24 may run with warnings)
- pnpm
- MongoDB configured in `frontend/.env.local`

## 4) First-Time Setup

### 4.1 Frontend dependencies

```powershell
cd X:\OpenMind-main\OpenMind-main
pnpm -C frontend install
```

### 4.2 Python environment for backend

```powershell
cd X:\OpenMind-main\OpenMind-main\openmind-subnet
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional import sanity check:

```powershell
python -c "import gateway; import gateway.mcp_server; print('OK')"
```

## 5) Run Locally (Day-to-Day)

Open two terminals.

### Terminal A: Backend gateway

```powershell
cd X:\OpenMind-main\OpenMind-main
python -m uvicorn --app-dir "X:\OpenMind-main\OpenMind-main\openmind-subnet" gateway.api:app --host 127.0.0.1 --port 8090
```

### Terminal B: Frontend

```powershell
cd X:\OpenMind-main\OpenMind-main
pnpm -C frontend dev
```

## 6) Health Checks

```powershell
Invoke-WebRequest http://127.0.0.1:8090/v1/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000 -UseBasicParsing
```

Expected: HTTP 200 responses.

## 7) Cursor MCP Setup (Local Laptop)

Use the repo config at [mcp.json](mcp.json).

Current expected content:

```json
{
  "mcpServers": {
    "openmind": {
      "command": "python",
      "args": [
        "-m",
        "gateway.mcp_server",
        "--bff-url",
        "http://127.0.0.1:3000",
        "--api-key",
        "${MINDMESH_API_KEY}"
      ],
      "env": {
        "PYTHONPATH": "X:/OpenMind-main/OpenMind-main/openmind-subnet"
      }
    }
  }
}
```

Set API key in the shell before launching Cursor:

```powershell
$env:MINDMESH_API_KEY = "om_live_YOUR_KEY"
& "C:\Path\To\Cursor\Cursor.exe"
```

If Cursor has no MCP UI, this launch method is required so env vars are inherited.

### 7.1 Claude Desktop over a remote MCP server

Claude Desktop cannot use a raw remote MCP URL directly in `claude_desktop_config.json`. Use the `mcp-remote` wrapper so Claude can launch a local stdio process that connects to the remote server for you.

Example:

```json
{
  "mcpServers": {
    "openmind": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://open-mind-85nx.onrender.com/mcp"
      }
    }
  }
}
```

If you are using ngrok instead of Render, replace the URL with your ngrok HTTPS URL. If the tunnel shows a browser warning page, add the `ngrok-skip-browser-warning: true` header in the remote transport wrapper if your client supports custom headers.

This remote wrapper path is separate from the local BFF mode. In local BFF mode, `session_id` is derived automatically from the API key when the client omits it.

## 8) Create API Key

- Open dashboard: `http://127.0.0.1:3000`
- Navigate to API and MCP
- Create key
- Use the generated `om_live_*` value for `MINDMESH_API_KEY`

## 9) Verify MCP + Dashboard Recording

After connecting in Cursor:

1. Run one memory store action
2. Run one memory query action
3. Open dashboard explorer/query view and confirm entries appear

## 10) Troubleshooting

### A) Port 8090 already in use (WinError 10048)

```powershell
$p = (Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($p) { Stop-Process -Id $p -Force }
```

Then restart backend.

### B) Frontend lock file / port 3000 conflict

```powershell
$p = (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($p) { Stop-Process -Id $p -Force }
if (Test-Path "X:\OpenMind-main\OpenMind-main\frontend\.next\dev\lock") { Remove-Item -Force "X:\OpenMind-main\OpenMind-main\frontend\.next\dev\lock" }
```

Then restart frontend.

### C) `No module named 'gateway'`

- Ensure `PYTHONPATH` points to `X:/OpenMind-main/OpenMind-main/openmind-subnet`
- Or set `command` in MCP config to the full venv Python executable

### D) Unauthorized on `/api/gateway/*`

- Verify API key is from this running instance
- Verify `MINDMESH_API_KEY` is visible to Cursor process
- Recreate API key from dashboard if needed

### E) `Not Acceptable: Client must accept text/event-stream`

A compatibility fix is already applied in [openmind-subnet/gateway/api.py](openmind-subnet/gateway/api.py) and committed.

## 11) Important Files

- [README.md](README.md)
- [mcp.json](mcp.json)
- [openmind-subnet/gateway/api.py](openmind-subnet/gateway/api.py)
- [openmind-subnet/gateway/mcp_server.py](openmind-subnet/gateway/mcp_server.py)
- [frontend/app/api/gateway/memory/store/route.ts](frontend/app/api/gateway/memory/store/route.ts)
- [frontend/app/api/gateway/memory/query/route.ts](frontend/app/api/gateway/memory/query/route.ts)

## 12) Related Commits

- `636bec6` - cross-client metadata flow + Cursor MCP configs
- `5e0adcc` - local Cursor MCP routing/config stabilization
