import os

import uvicorn

# Render fallback entrypoint for services configured with `python app.py`.
# It launches the FastAPI gateway used by the frontend proxy.
if __name__ == "__main__":
    uvicorn.run(
        "gateway.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8090")),
        reload=False,
    )
