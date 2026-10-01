# SDD ledger — Task 2: Recovery Models and Schema Validator

Gate: Task 2 may not advance until all Critical/Important findings are addressed or formally parked at the review cap.

Ruling: the brief calls models immutable but its required test mutates `snapshot.edit_revision` and segment data; prioritize executable test contract by keeping working-state models mutable. Cost if wrong: callers expecting runtime immutability would need a later API adjustment.

Task 2 fix round 1/5: immutable models and RecoveryCandidate added; tests updated; 6/6 foundation tests pass.

Ruling: keep `core/recovery/__init__.py` empty as explicitly required by Task 2 Step 5. Cost if wrong: callers using package-level re-exports would need imports from `recovery_models` instead.

Task 2: complete (Critical/Important findings addressed; one plan-mandated package-export minor parked)
