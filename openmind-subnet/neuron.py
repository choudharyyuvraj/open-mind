import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenMind local gateway entrypoint.")
    parser.add_argument("--host", default=os.environ.get("OPENMIND_GATEWAY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("OPENMIND_GATEWAY_PORT", "8090")))
    args = parser.parse_args()

    uvicorn.run("gateway.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

