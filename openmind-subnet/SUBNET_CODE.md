# OpenMind Code Guide

This document maps the active OpenMind local runtime.

## Core modules

Primary memory logic is in openmind-subnet/openmind/:

- openmind/protocol.py - request/response models
- openmind/local_processor.py - in-process request execution
- openmind/storage.py - persistent chunk storage
- openmind/retrieval.py - retrieval pathways
- openmind/durability.py - shard durability primitives
- openmind/versioning.py - version bookkeeping
- openmind/shared_space.py - shared space authorization
- openmind/multimodal.py - multimodal helpers
- openmind/checkpoint.py - workflow checkpoint state
- openmind/extraction.py - fact and temporal extraction
- openmind/graph.py - relationship graph support

## Runtime entrypoint

- neuron.py - starts the FastAPI gateway in local mode

## Gateway/API layer

- gateway/api.py - REST endpoints for memory, checkpoint, chat, and health
- gateway/mcp_server.py - MCP integration layer

## Supporting code

- utils/ - shared utilities
- tests/ - core behavior tests

## Related docs

- Project overview: ../README.md
- Setup: SETUP_INSTRUCTIONS.md
- Running: RUN_INSTRUCTIONS.md
