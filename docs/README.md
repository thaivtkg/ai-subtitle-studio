# Tài liệu dự án

Các plan/spec dưới đây là hồ sơ thiết kế và triển khai tại thời điểm viết, không phải backlog hiện hành. Checkbox chưa đánh dấu và trạng thái review trong tài liệu cũ không phản ánh trạng thái công việc hiện tại. Các tài liệu được giữ để bảo toàn quyết định kiến trúc, acceptance và lịch sử điều tra.

| Tài liệu | Khu vực / loại | Trạng thái hiện tại | Liên quan |
|---|---|---|---|
| [`2026-09-01-sprint-11-project-reliability-recovery-design.md`](superpowers/specs/2026-09-01-sprint-11-project-reliability-recovery-design.md) | Recovery — design spec | Lịch sử; thiết kế đã triển khai | [Plan](superpowers/plans/2026-09-01-sprint-11-project-reliability-recovery.md) |
| [`2026-09-01-sprint-11-project-reliability-recovery.md`](superpowers/plans/2026-09-01-sprint-11-project-reliability-recovery.md) | Recovery — implementation plan | Lịch sử; không phải checklist đang chạy | [Spec](superpowers/specs/2026-09-01-sprint-11-project-reliability-recovery-design.md) |
| [`2026-09-02-sprint-12-contextual-transcription-media-import-design.md`](superpowers/specs/2026-09-02-sprint-12-contextual-transcription-media-import-design.md) | Transcription/media import — design spec | Lịch sử thiết kế | [Plan](superpowers/plans/2026-09-02-sprint-12-contextual-transcription-media-import.md) |
| [`2026-09-02-sprint-12-contextual-transcription-media-import.md`](superpowers/plans/2026-09-02-sprint-12-contextual-transcription-media-import.md) | Transcription/media import — implementation plan | Lịch sử; checkbox không phải trạng thái backlog | [Spec](superpowers/specs/2026-09-02-sprint-12-contextual-transcription-media-import-design.md) |
| [`2026-09-04-help-center-guided-tour-design.md`](superpowers/specs/2026-09-04-help-center-guided-tour-design.md) | Help Center/guided tour — design spec | Lịch sử; phần triển khai tiếp tục qua các milestone | [Milestone A](superpowers/plans/2026-09-04-help-center-guided-tour-milestone-a.md), [C1](superpowers/plans/2026-09-06-help-center-c1.md) |
| [`2026-09-04-help-center-guided-tour-milestone-a.md`](superpowers/plans/2026-09-04-help-center-guided-tour-milestone-a.md) | Guided tour — implementation plan | Lịch sử milestone | [Design](superpowers/specs/2026-09-04-help-center-guided-tour-design.md) |
| [`2026-09-06-help-center-c1.md`](superpowers/plans/2026-09-06-help-center-c1.md) | Help Center C1 — implementation plan | Lịch sử milestone | Cùng chuỗi Help Center/guided tour |
| [`2026-09-08-c4-demo-capture-pipeline-design.md`](superpowers/specs/2026-09-08-c4-demo-capture-pipeline-design.md) | Demo capture C4 — design spec | Lịch sử; implementation/asset validation đã có | [Plan](superpowers/plans/2026-09-08-c4-demo-capture-pipeline.md) |
| [`2026-09-08-c4-demo-capture-pipeline.md`](superpowers/plans/2026-09-08-c4-demo-capture-pipeline.md) | Demo capture C4 — implementation plan | Lịch sử; không phải checklist hiện hành | [Spec](superpowers/specs/2026-09-08-c4-demo-capture-pipeline-design.md) |
| [`2026-09-10-c5-production-guided-tour-content-release-acceptance-design.md`](superpowers/specs/2026-09-10-c5-production-guided-tour-content-release-acceptance-design.md) | Guided tour C5 — specification/acceptance | Hồ sơ lịch sử; dòng “ready for review” phản ánh thời điểm viết | [Plan](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance.md), [self-review](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance-self-review.md) |
| [`2026-09-10-c5-production-guided-tour-content-release-acceptance.md`](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance.md) | C5 — implementation/release acceptance plan | Lịch sử; acceptance hiện hành không được xác định bằng checkbox cũ | [Spec](superpowers/specs/2026-09-10-c5-production-guided-tour-content-release-acceptance-design.md), [self-review](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance-self-review.md) |
| [`2026-09-10-c5-production-guided-tour-content-release-acceptance-self-review.md`](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance-self-review.md) | C5 — normative plan companion/self-review | Giữ làm rationale và hiệu chỉnh kế hoạch | [Plan](superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance.md) |
| [`2026-09-18-feature-33-project-autosave-design.md`](superpowers/specs/2026-09-18-feature-33-project-autosave-design.md) | Feature 33 — autosave design | Lịch sử; PR #33 đã merge, status “amended for review” đã cũ | [Plan](superpowers/plans/2026-09-18-feature-33-project-autosave.md) |
| [`2026-09-18-feature-33-project-autosave.md`](superpowers/plans/2026-09-18-feature-33-project-autosave.md) | Feature 33 — implementation plan | Lịch sử; không phải backlog hiện hành | [Spec](superpowers/specs/2026-09-18-feature-33-project-autosave-design.md) |
| [`2026-09-20-feature-33-1-e5-project-identity.md`](superpowers/plans/2026-09-20-feature-33-1-e5-project-identity.md) | Feature 33.1 E.5 — project identity plan | Lịch sử; implementation commit `dbd7288f` có trong lịch sử master | `tests/test_queue_project_identity.py` |
| [Task 1 brief](../.superpowers/sdd/task1/task-1-brief.md) | Recovery paths/source fingerprint — brief | Historical SDD input; keep | [Report](../.superpowers/sdd/task1/task-1-report.md), [progress](../.superpowers/sdd/task1/progress.md) |
| [Task 1 progress](../.superpowers/sdd/task1/progress.md) | Task 1 — review/progress record | Historical evidence; completion recorded | [Brief](../.superpowers/sdd/task1/task-1-brief.md), [report](../.superpowers/sdd/task1/task-1-report.md) |
| [Task 1 report](../.superpowers/sdd/task1/task-1-report.md) | Task 1 — implementation report | Historical completion and verification evidence | [Brief](../.superpowers/sdd/task1/task-1-brief.md) |
| [Task 2 progress](../.superpowers/sdd/task2-progress.md) | Recovery models/schema validator — progress/review | Historical decisions and parked findings; keep | [Report](../.superpowers/sdd/task2-report.md) |
| [Task 2 report](../.superpowers/sdd/task2-report.md) | Task 2 — implementation report | Historical implementation/test evidence | [Progress](../.superpowers/sdd/task2-progress.md) |
| [Test_Report_Sprint 4.xlsx](../Test_Report_Sprint%204.xlsx) | Sprint 4 — manual QA report | Historical test evidence; unique workbook, retained | — |

## Build/test cleanup debt

**RESOLVED — CLEANUP.6 (`7ae2b3a6`):** Build dùng `build/ai_subtitle_studio.spec`; `tests/test_packaging_constraints.py` kiểm tra trực tiếp spec này thay vì quét `*.spec` ở root. Spec Alpha cũ đã được xóa; `curl_cffi` vẫn được loại khỏi bundle theo packaging policy.

**REVIEW-LATER:** `test_curl_cffi_is_strictly_excluded` kiểm tra môi trường Python chạy test, không tự chứng minh nội dung bundle. Cần xem lại contract và thông báo lỗi `SECURITY BREACH` / `maintain the SSRF boundary` trong phase test riêng; CLEANUP.6 không xác lập đã có lỗ hổng SSRF.

README chính: [README.md](../README.md).
