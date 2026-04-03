"""
Local in-process request processor for OpenMind.

This mirrors the former miner request handling path but without Bittensor
transport or chain dependencies.
"""

from __future__ import annotations

import datetime
import logging
import os
import uuid
from typing import Any, Dict

from openmind import checkpoint, extraction, graph, retrieval, shared_space, storage, storage_v2
from openmind.protocol import OpenMindRequest, OpenMindResponse

logger = logging.getLogger(__name__)


class LocalProcessor:
    def __init__(self) -> None:
        self.storage_backend = os.environ.get("OPENMIND_STORAGE_BACKEND", "legacy").lower()
        self.storage_dual_write = (
            os.environ.get("OPENMIND_STORAGE_DUAL_WRITE", "false").lower() == "true"
        )

    def _primary_storage(self):
        return storage_v2 if self.storage_backend == "sqlite" else storage

    def _secondary_storage(self):
        return storage if self.storage_backend == "sqlite" else storage_v2

    def process(self, request: OpenMindRequest) -> OpenMindResponse:
        if request.shared_space_id is not None:
            authorized = shared_space.authorize_access(
                shared_space_id=request.shared_space_id,
                author=request.author,
                auth_metadata=request.auth_metadata,
            )
            if not authorized:
                logger.warning("Unauthorized shared-space access.")
                return OpenMindResponse(results=[])

        action = (request.filters or {}).get("_action")

        if action == "store":
            return self._handle_store(request)
        if action == "query_smart":
            return self._handle_query_smart(request)
        if action == "compact":
            return self._handle_compact(request)
        if action == "checkpoint_save":
            return self._handle_checkpoint_save(request)
        if action == "checkpoint_resume":
            return self._handle_checkpoint_resume(request)

        return self._handle_retrieve(request)

    def _handle_store(self, request: OpenMindRequest) -> OpenMindResponse:
        chunk_id = str(uuid.uuid4())
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        content = request.query or ""
        role = (request.filters or {}).get("_role", "user")
        event_at = request.event_at or extraction.extract_temporal(content)

        retrieval.add_chunk(
            session_id=request.session_id,
            content=content,
            embedding=request.embedding or [],
            metadata={
                "id": chunk_id,
                "type": "episode",
                "role": role,
                "timestamp": ts,
                "recorded_at": ts,
                "event_at": event_at,
                "multimodal_type": request.multimodal_type,
            },
        )

        facts = extraction.extract_facts(
            content=content,
            episode_id=chunk_id,
            session_id=request.session_id,
            role=role,
            recorded_at=ts,
        )

        existing_facts = retrieval.get_facts_for_session(request.session_id)
        for fact in facts:
            retrieval.add_chunk(
                session_id=request.session_id,
                content=fact["content"],
                embedding=request.embedding or [],
                metadata={
                    "id": fact["id"],
                    "type": "fact",
                    "source_episode_id": fact["source_episode_id"],
                    "subject": fact["subject"],
                    "predicate": fact["predicate"],
                    "object": fact["object"],
                    "confidence": fact["confidence"],
                    "recorded_at": fact["recorded_at"],
                    "event_at": fact["event_at"],
                    "valid_from": fact["valid_from"],
                    "valid_until": fact["valid_until"],
                    "is_latest": True,
                    "role": fact["role"],
                    "fact_keys": fact["fact_keys"],
                    "timestamp": ts,
                },
            )

            edges = graph.detect_relationships(fact, existing_facts)
            for edge in edges:
                if edge["relation"] == "supersedes":
                    old_id = edge["target_id"]
                    retrieval.update_fact_latest(request.session_id, old_id, False)
                    self._primary_storage().update_chunk_metadata(
                        request.session_id,
                        old_id,
                        {"is_latest": False, "valid_until": ts},
                    )
                    if self.storage_dual_write:
                        self._secondary_storage().update_chunk_metadata(
                            request.session_id,
                            old_id,
                            {"is_latest": False, "valid_until": ts},
                        )

            existing_facts.append(fact)

        all_session_facts = retrieval.get_facts_for_session(request.session_id)
        anchor = extraction.generate_anchor(
            request.session_id,
            all_session_facts,
            retrieval.get_anchor_for_session(request.session_id),
        )
        if anchor:
            retrieval.add_chunk(
                session_id=request.session_id,
                content=anchor["content"],
                embedding=[],
                metadata=anchor,
            )

        logger.info(
            "Stored episode %s + %d facts for session %s",
            chunk_id,
            len(facts),
            request.session_id,
        )
        return OpenMindResponse(
            results=[
                {
                    "id": chunk_id,
                    "content": content,
                    "role": role,
                    "status": "stored",
                    "timestamp": ts,
                    "fact_count": len(facts),
                }
            ]
        )

    def _handle_query_smart(self, request: OpenMindRequest) -> OpenMindResponse:
        clean_filters = {
            k: v for k, v in (request.filters or {}).items() if not k.startswith("_")
        }
        results = retrieval.retrieve_smart(
            session_id=request.session_id,
            query=request.query,
            embedding=request.embedding,
            top_k=request.top_k,
            filters=clean_filters,
            time_point=request.as_of_timestamp,
        )
        return OpenMindResponse(results=results)

    def _handle_compact(self, request: OpenMindRequest) -> OpenMindResponse:
        all_facts = retrieval.get_facts_for_session(request.session_id)
        existing_anchor = retrieval.get_anchor_for_session(request.session_id)
        anchor = extraction.generate_anchor(request.session_id, all_facts, existing_anchor)
        if anchor:
            retrieval.add_chunk(
                session_id=request.session_id,
                content=anchor["content"],
                embedding=[],
                metadata=anchor,
            )
            return OpenMindResponse(results=[{"status": "compacted", "anchor": anchor}])
        return OpenMindResponse(results=[{"status": "no_compaction_needed"}])

    def _handle_checkpoint_save(self, request: OpenMindRequest) -> OpenMindResponse:
        step = int((request.filters or {}).get("step", 0))
        state = (request.filters or {}).get("state", {})
        workflow_id = request.workflow_id or ""
        if not workflow_id:
            return OpenMindResponse(results=[{"status": "missing_workflow_id"}])
        cp = checkpoint.save_checkpoint(workflow_id=workflow_id, step=step, state=state)
        cp_dict = {
            "workflow_id": cp.workflow_id,
            "step": cp.step,
            "timestamp": cp.timestamp,
            "state": cp.state,
        }
        return OpenMindResponse(results=[{"status": "checkpoint_saved"}], checkpoint=cp_dict)

    def _handle_checkpoint_resume(self, request: OpenMindRequest) -> OpenMindResponse:
        workflow_id = request.workflow_id or ""
        if not workflow_id:
            return OpenMindResponse(results=[{"status": "missing_workflow_id"}])
        cp = checkpoint.load_checkpoint(workflow_id=workflow_id)
        if cp is None:
            return OpenMindResponse(results=[{"status": "checkpoint_not_found"}], checkpoint=None)
        return OpenMindResponse(results=[{"status": "checkpoint_loaded"}], checkpoint=cp)

    def _handle_retrieve(self, request: OpenMindRequest) -> OpenMindResponse:
        clean_filters = {
            k: v for k, v in (request.filters or {}).items() if not k.startswith("_")
        }
        results = retrieval.retrieve(
            session_id=request.session_id,
            query=request.query,
            embedding=request.embedding,
            top_k=request.top_k,
            filters=clean_filters,
            as_of_timestamp=request.as_of_timestamp,
            version_id=request.version_id,
            diff_since=request.diff_since,
        )
        checkpoint_payload = None
        if request.resume_from_checkpoint and request.workflow_id:
            checkpoint_payload = checkpoint.load_checkpoint(workflow_id=request.workflow_id)
        return OpenMindResponse(
            results=results,
            version_diff=None,
            provenance_path=None,
            checkpoint=checkpoint_payload,
        )


PROCESSOR = LocalProcessor()


def process_request(request: OpenMindRequest) -> OpenMindResponse:
    return PROCESSOR.process(request)
