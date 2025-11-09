"""Persistent storage for Pulse probe payload overrides."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional

# Security limits to prevent abuse
MAX_PAYLOAD_SIZE_BYTES = 1024 * 1024  # 1MB per payload
MAX_TOTAL_STORAGE_BYTES = 10 * 1024 * 1024  # 10MB total storage
ENDPOINT_ID_PATTERN = re.compile(r'^[A-Z]+ /[a-zA-Z0-9/_\-{}]+$')


class PulsePayloadStore:
    """Manages persistent custom payload overrides for endpoints."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self._payloads: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            with self.file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._payloads = data
        except Exception:
            # If the file is corrupted, ignore and start fresh.
            self._payloads = {}

    def _flush(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(self._payloads, handle, indent=2, ensure_ascii=False)
        tmp_path.replace(self.file_path)

    def get(self, endpoint_id: str) -> Optional[Dict[str, Any]]:
        return self._payloads.get(endpoint_id)

    def set(self, endpoint_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Validate endpoint_id format to prevent path traversal
        if not ENDPOINT_ID_PATTERN.match(endpoint_id):
            raise ValueError(
                f"Invalid endpoint_id format: {endpoint_id}. "
                f"Expected format: 'METHOD /path' (e.g., 'GET /users/{{id}}')"
            )

        # Sanitize and validate payload
        cleaned = self._sanitize_payload(payload)

        # Check individual payload size
        payload_json = json.dumps(cleaned, ensure_ascii=False)
        payload_size = len(payload_json.encode('utf-8'))
        if payload_size > MAX_PAYLOAD_SIZE_BYTES:
            raise ValueError(
                f"Payload too large: {payload_size} bytes. "
                f"Maximum allowed: {MAX_PAYLOAD_SIZE_BYTES} bytes ({MAX_PAYLOAD_SIZE_BYTES // 1024}KB)"
            )

        with self._lock:
            # Check total storage size before adding
            if self.file_path.exists():
                current_size = self.file_path.stat().st_size
                if endpoint_id not in self._payloads and current_size > MAX_TOTAL_STORAGE_BYTES:
                    raise ValueError(
                        f"Storage limit exceeded. Current: {current_size} bytes, "
                        f"Maximum: {MAX_TOTAL_STORAGE_BYTES} bytes ({MAX_TOTAL_STORAGE_BYTES // 1024 // 1024}MB)"
                    )

            self._payloads[endpoint_id] = cleaned
            self._flush()
        return cleaned

    def delete(self, endpoint_id: str) -> None:
        with self._lock:
            if endpoint_id in self._payloads:
                del self._payloads[endpoint_id]
                self._flush()

    def all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._payloads)

    @staticmethod
    def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        path_params = payload.get("path_params") or {}
        query_params = payload.get("query") or {}
        headers = payload.get("headers") or {}
        body = payload.get("body") if "body" in payload else None
        media_type = payload.get("media_type")

        return {
            "path_params": path_params,
            "query": query_params,
            "headers": headers,
            "body": body,
            "media_type": media_type,
        }


__all__ = ["PulsePayloadStore"]
