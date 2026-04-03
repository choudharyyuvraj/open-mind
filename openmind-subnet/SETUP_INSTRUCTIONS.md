# Setup Instructions

Use these steps to prepare OpenMind local mode.

## 1) Prerequisites

- Python 3.10+ for openmind-subnet/
- Node.js 20+ for frontend/
- MongoDB instance for dashboard/auth data (frontend side)

## 2) Install Python dependencies

From openmind-subnet/:

```bash
pip install -r requirements.txt
```

## 3) Configure Python runtime environment

Optional local gateway variables:

- OPENMIND_GATEWAY_HOST (default: 127.0.0.1)
- OPENMIND_GATEWAY_PORT (default: 8090)
- OPENMIND_STORAGE_DIR (default: .openmind_storage)
- OPENMIND_STORAGE_BACKEND (legacy or sqlite)
- OPENMIND_STORAGE_DUAL_WRITE (true/false)

Optional chat model variables (for /v1/chat/respond):

- OPENAI_API_KEY
- OPENAI_BASE_URL (default: https://api.openai.com/v1)

## 4) Configure frontend environment

In frontend/.env.local set at least:

- SUBNET_GATEWAY_URL=http://127.0.0.1:8090
- MONGODB_URI=...
- MONGODB_DB_NAME=...
- API_KEY_HASH_PEPPER=...

## 5) Verify setup

Before running:

- Python dependencies install without errors
- Node dependencies install without errors
- SUBNET_GATEWAY_URL points to the local gateway

Then continue with RUN_INSTRUCTIONS.md.
