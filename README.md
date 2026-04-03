# OpenMind Project

This repository contains the OpenMind memory platform with:

- frontend/ (web dashboard, auth, API proxy routes)
- openmind-subnet/ (gateway + memory processing modules)

The project now runs in local mode without Bittensor miner/validator roles and
without evaluation leaderboard logic.

## Public API-only deployment

To deploy OpenMind so anyone can use it with an API key, run it as a public
web app plus a bearer-authenticated API:

1. Put MongoDB in a managed service such as MongoDB Atlas.
2. Deploy `frontend/` to a public HTTPS host.
3. Deploy `openmind-subnet/` as a private backend service or a second public
	service behind the frontend.
4. Set `AUTH_OPEN=true` and `NEXT_PUBLIC_AUTH_OPEN=true` so users can sign up
	and create API keys.
5. Set `API_KEY_HASH_PEPPER` to a long random value and keep it stable across
	restarts.
6. Set `SUBNET_GATEWAY_URL` to the deployed gateway URL.
7. Give users `om_live_...` keys from the dashboard, then have them call
	`/api/gateway/*` with `Authorization: Bearer om_live_...`.

Production env vars:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `AUTH_OPEN=true`
- `NEXT_PUBLIC_AUTH_OPEN=true`
- `API_KEY_HASH_PEPPER`
- `SUBNET_GATEWAY_URL`
- `NEXT_PUBLIC_API_BASE_URL`

If you want to keep the dashboard private, you can still expose only the API
routes publicly and manage key creation internally.

## Deploy on Vercel

Use Vercel for the Next.js frontend in `frontend/`, and deploy the Python
gateway separately on a backend host. Vercel can serve the dashboard and the
`/api/*` routes, but it will not run the long-lived Python gateway process from
`openmind-subnet/`.

Recommended setup:

1. Create a Vercel project with the root directory set to `frontend/`.
2. Add these Vercel environment variables:
	- `MONGODB_URI`
	- `MONGODB_DB_NAME=openmind`
	- `AUTH_OPEN=true`
	- `NEXT_PUBLIC_AUTH_OPEN=true`
	- `API_KEY_HASH_PEPPER` (long random secret)
	- `SUBNET_GATEWAY_URL` (public URL of the deployed gateway)
	- `NEXT_PUBLIC_API_BASE_URL` (your Vercel app URL, optional if same-origin)
3. Deploy the Python gateway from `openmind-subnet/` to a separate service
	such as Render, Fly.io, Railway, Azure, or a VM.
4. Make sure the deployed gateway is reachable from Vercel over HTTPS.
5. Use the dashboard on Vercel to create `om_live_...` API keys.
6. Call `Authorization: Bearer om_live_...` against `/api/gateway/*` on the
	Vercel domain.

If you only want a public API and not the dashboard UI, you can still keep the
Vercel project online for the API routes while hiding the dashboard behind
authentication or a private route policy.

## Main project locations

- frontend/ (web dashboard, auth, API proxy routes)
- openmind-subnet/ (gateway + memory processing modules)

## Runtime docs

- Setup: openmind-subnet/SETUP_INSTRUCTIONS.md
- Run: openmind-subnet/RUN_INSTRUCTIONS.md
- Code map: openmind-subnet/SUBNET_CODE.md
