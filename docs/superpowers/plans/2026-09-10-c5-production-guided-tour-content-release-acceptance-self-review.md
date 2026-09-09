# C5 Implementation Plan — Self-Review Corrections

**Status:** NORMATIVE COMPANION TO THE C5 IMPLEMENTATION PLAN  
**Applies to:** `docs/superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance.md`  
**Reason:** Final self-review found two test-command details that must be tightened before execution. These corrections do not change the locked C5 architecture/specification.

---

## Correction 1 — Task 4 zero-mutation assertions must inspect service method calls

In Task 4 Step 2, replace:

```python
self.media_import_service.assert_not_called()
self.recovery_manager.assert_not_called()
```

with:

```python
self.media_import_service.import_from_url.assert_not_called()
self.assertEqual(self.media_import_service.method_calls, [])
self.assertEqual(self.recovery_manager.method_calls, [])
```

Keep the existing explicit `ProjectService` mutation-method assertions and:

```python
self.window.subtitle_generation_service.start_generation.assert_not_called()
soft_export.assert_not_called()
hard_export.assert_not_called()
```

Rationale: `MagicMock.assert_not_called()` on the service object only proves the mock itself was not invoked as a callable; it does not reject calls made to child methods. `method_calls` and the explicit `import_from_url` assertion prove the intended zero-mutation boundary.

---

## Correction 2 — Task 5 GIF inspection command must directly verify frame count and duration

In Task 5 Step 7, replace the one-line Pillow inspection command with:

```powershell
python -c "from pathlib import Path; from PIL import Image; p=Path('resources/tutorials/assets/getting_started_generation.gif'); im=Image.open(p); assert im.format == 'GIF'; assert im.size == (960, 540); assert 2 <= im.n_frames <= 200; durations=[]; [durations.append((im.seek(i), int(im.info.get('duration', 0) or 0))[1]) for i in range(im.n_frames)]; total=sum(durations); assert total <= 20000; assert p.stat().st_size <= 8*1024*1024; print(p, im.size, im.n_frames, total, p.stat().st_size)"
```

Expected output includes:

```text
resources/tutorials/assets/getting_started_generation.gif
(960, 540)
frame count between 2 and 200
total duration <= 20000 ms
file size <= 8 MiB
```

The authoritative C4 validator must still run immediately before this command:

```powershell
python -m tools.demo_capture validate
```

---

## Self-review result

No architecture or scope changes are required.

The implementation still uses:

```text
9 production steps
6 production anchors
1 ACTION (REQUIRED + CLICK)
5 FALLBACK_TO_INFO orientation targets
0 new routes
0 production resolvers
0 TourEngine changes
1 C4-generated local GIF
mandatory manual acceptance
mandatory Windows/PyInstaller smoke
```

Execution MUST read this correction file together with the main Implementation Plan.