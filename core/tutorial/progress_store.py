"""Atomic, offline-first persistence for guided-tour progress."""

from __future__ import annotations

import copy
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


class GuideProgressStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"
    OUTDATED = "OUTDATED"
    COMPLETED_NEWER_VERSION = "COMPLETED_NEWER_VERSION"
    UNKNOWN = "UNKNOWN"
    NONE = "NOT_STARTED"


@dataclass(frozen=True)
class GuideProgress:
    status: GuideProgressStatus
    content_version: Optional[int] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    dismissed_at: Optional[str] = None


class TourProgressStore:
    SCHEMA_VERSION = 1
    LEGACY_SCHEMA_VERSION = 0

    def __init__(self, file_path: Path):
        self._file_path = Path(file_path)
        self._progress: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._read_only = False
        self._updated_at: Optional[str] = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._file_path.exists():
            return

        try:
            with self._file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                raise ValueError("Progress payload root must be a JSON object")
            self._updated_at = payload.get("updated_at")
            schema_version = payload.get("schema_version")
            if schema_version == self.LEGACY_SCHEMA_VERSION:
                self._progress = self._migrate_v0(payload)
            elif schema_version == self.SCHEMA_VERSION:
                self._progress = self._decode_v1(payload)
            elif isinstance(schema_version, int) and schema_version > self.SCHEMA_VERSION:
                self._read_only = True
            else:
                raise ValueError(f"Unsupported schema version: {schema_version!r}")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Invalid guided-tour progress; quarantining: %s", exc)
            if not self._quarantine():
                self._read_only = True
            self._progress = {}

    @staticmethod
    def _migrate_v0(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        completed = payload.get("completed_guides", payload.get("completed", {}))
        dismissed = payload.get("dismissed", {})
        if not isinstance(completed, dict):
            raise ValueError("completed_guides must be an object")
        migrated: dict[str, dict[str, Any]] = {}
        for guide_id, version in completed.items():
            if not isinstance(guide_id, str) or not isinstance(version, int):
                raise ValueError("invalid legacy guide progress")
            migrated[guide_id] = {
                "content_version": version,
                "status": GuideProgressStatus.COMPLETED.value,
                "completed_at": None,
            }
        if not isinstance(dismissed, dict):
            raise ValueError("dismissed must be an object")
        for guide_id, version in dismissed.items():
            if not isinstance(guide_id, str) or not isinstance(version, int):
                raise ValueError("invalid legacy guide progress")
            migrated[guide_id] = {
                "content_version": version,
                "status": GuideProgressStatus.DISMISSED.value,
                "dismissed_at": None,
            }
        return migrated

    @staticmethod
    def _decode_v1(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        guides = payload.get("progress", payload.get("guides", {}))
        if not isinstance(guides, dict):
            raise ValueError("guides must be an object")
        decoded: dict[str, dict[str, Any]] = {}
        for guide_id, record in guides.items():
            if not isinstance(guide_id, str) or not isinstance(record, dict):
                raise ValueError("invalid guide progress record")
            version = record.get("content_version")
            status = record.get("status")
            if not isinstance(version, int) or version < 0:
                raise ValueError("invalid content version")
            if status not in (GuideProgressStatus.COMPLETED.value, GuideProgressStatus.DISMISSED.value):
                raise ValueError("invalid guide progress status")
            decoded[guide_id] = {
                "content_version": version,
                "status": status,
                **({"completed_at": record["completed_at"]} if "completed_at" in record else {}),
                **({"dismissed_at": record["dismissed_at"]} if "dismissed_at" in record else {}),
            }
        return decoded

    def _quarantine(self) -> bool:
        if not self._file_path.exists():
            return True
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine = self._file_path.with_name(
            f"{self._file_path.stem}.corrupt.{stamp}{self._file_path.suffix}"
        )
        try:
            os.replace(self._file_path, quarantine)
            return True
        except OSError as exc:
            logger.error("Could not quarantine guided-tour progress: %s", exc)
            return False

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _atomic_write(self, guides: dict[str, dict[str, Any]]) -> bool:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "updated_at": self._now(),
            "progress": guides,
        }
        temporary = self._file_path.with_name(
            f"{self._file_path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        )
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._file_path)
            return True
        except OSError as exc:
            logger.error("Could not atomically save guided-tour progress: %s", exc)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def status(self, guide_id: str, content_version: int) -> GuideProgress:
        self._load()
        if self._read_only:
            return GuideProgress(GuideProgressStatus.UNKNOWN)
        record = self._progress.get(guide_id)
        if record is None:
            return GuideProgress(GuideProgressStatus.NOT_STARTED)
        stored_version = record["content_version"]
        stored_status = GuideProgressStatus(record["status"])
        if stored_version < content_version:
            status = GuideProgressStatus.OUTDATED
        elif stored_version > content_version and stored_status is GuideProgressStatus.COMPLETED:
            status = GuideProgressStatus.COMPLETED_NEWER_VERSION
        else:
            status = stored_status
        return GuideProgress(
            status,
            stored_version,
            self._updated_at,
            record.get("completed_at"),
            record.get("dismissed_at"),
        )

    def is_completed(self, guide_id: str, content_version: int) -> bool:
        return self.status(guide_id, content_version).status in (
            GuideProgressStatus.COMPLETED,
            GuideProgressStatus.COMPLETED_NEWER_VERSION,
        )

    def is_dismissed(self, guide_id: str, content_version: int) -> bool:
        return self.status(guide_id, content_version).status is GuideProgressStatus.DISMISSED

    def _mark(self, guide_id: str, content_version: int, status: GuideProgressStatus) -> bool:
        self._load()
        if self._read_only or not isinstance(content_version, int) or content_version < 0:
            return False
        current = self._progress.get(guide_id)
        if current and current["content_version"] > content_version:
            return True
        candidate = copy.deepcopy(self._progress)
        record = candidate.get(guide_id, {})
        candidate[guide_id] = {
            "content_version": content_version,
            "status": status.value,
            **({"completed_at": self._now()} if status is GuideProgressStatus.COMPLETED else {}),
            **({"dismissed_at": self._now()} if status is GuideProgressStatus.DISMISSED else {}),
        }
        if record.get("content_version") == content_version:
            candidate[guide_id].update(
                {key: value for key, value in record.items()
                 if key in ("completed_at", "dismissed_at") and key not in candidate[guide_id]}
            )
        if not self._atomic_write(candidate):
            return False
        self._progress = candidate
        return True

    def mark_completed(self, guide_id: str, content_version: int) -> bool:
        return self._mark(guide_id, content_version, GuideProgressStatus.COMPLETED)

    def mark_dismissed(self, guide_id: str, content_version: int) -> bool:
        return self._mark(guide_id, content_version, GuideProgressStatus.DISMISSED)

    def reset(self, guide_id: Optional[str] = None) -> bool:
        self._load()
        if self._read_only:
            return False
        candidate = copy.deepcopy(self._progress)
        if guide_id is None:
            candidate = {}
        else:
            candidate.pop(guide_id, None)
        if not self._atomic_write(candidate):
            return False
        self._progress = candidate
        return True


ProgressStatus = GuideProgressStatus
