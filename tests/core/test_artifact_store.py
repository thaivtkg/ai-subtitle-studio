import os
import tempfile
import unittest
from unittest.mock import patch

from core.artifacts.artifact import Artifact
from core.artifacts.artifact_store import ArtifactStore
from core.artifacts.artifact_types import ArtifactStatus, ArtifactType


class TestArtifactStore(unittest.TestCase):
    def test_to_dict_preserves_absolute_path_when_relpath_cannot_cross_mounts(self):
        store = ArtifactStore()
        artifact_path = os.path.abspath(os.path.join(tempfile.gettempdir(), "active.srt"))
        store.register(
            Artifact(
                artifact_id="active",
                artifact_type=ArtifactType.TIMING,
                path=artifact_path,
                created_at="now",
                updated_at="now",
                source_project_id="project",
                status=ArtifactStatus.READY,
            )
        )

        with patch(
            "core.artifacts.artifact_store.os.path.relpath",
            side_effect=ValueError("path is on mount 'D:', start on mount 'C:'"),
        ):
            manifest = store.to_dict(os.path.join(os.path.splitdrive(artifact_path)[0], "project"))

        self.assertEqual(manifest["artifacts"][0]["path"], artifact_path.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
