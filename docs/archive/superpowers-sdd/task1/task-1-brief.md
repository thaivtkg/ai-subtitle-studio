# Task 1 brief — Recovery Paths and Shared Source Fingerprint

Implement/verify Task 1 exactly as specified by the user in the conversation:
- Add tests/test_recovery_foundation.py with the three unittest cases supplied by the user.
- Add RuntimePaths recovery getters and ensure_user_data_dirs creation of recovery, sessions, quarantine.
- Add core/project/source_fingerprint.py with frozen SourceInfo and generate_source_info using the specified SHA-256 size + first/last 1 MiB sampling algorithm.
- Delegate ProjectService._generate_fingerprint to generate_source_info while preserving Project's existing SourceInfo compatibility.
- Run the foundation and regression suites requested by the user.

Workspace already contains uncommitted Task 1 edits. Preserve user changes; inspect and minimally correct only if needed. Do not spawn subagents. Commit only Task 1 files if implementation is needed; do not touch unrelated modified files.
