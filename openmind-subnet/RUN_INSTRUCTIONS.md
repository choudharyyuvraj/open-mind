# Run Instructions

Use this guide to run OpenMind in local mode.

## 1) Start the gateway (PowerShell)

```powershell
cd x:\OpenMind-main\OpenMind-main\openmind-subnet
python neuron.py
```

Optional explicit bind:

```powershell
python neuron.py --host 127.0.0.1 --port 8090
```

## 2) Start the frontend (PowerShell)

```powershell
cd x:\OpenMind-main\OpenMind-main\frontend
pnpm install
pnpm dev
```

## 3) Operational checks

- Gateway health: GET http://127.0.0.1:8090/v1/health
- Frontend loads and authenticates
- Memory flows work through /api/gateway/* routes

## 4) Useful file references

- Entrypoint: neuron.py
- Gateway API: gateway/api.py
- Local processor: openmind/local_processor.py
- Protocol models: openmind/protocol.py
