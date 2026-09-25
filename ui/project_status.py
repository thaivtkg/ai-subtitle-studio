import os


def format_project_status(
    project,
    save_status,
    *,
    project_root=None,
    video_path=None,
):
    """Format the active project identity and canonical save presentation."""
    del video_path

    if project is None:
        return "No Project"

    name = str(getattr(project, "name", "") or "").strip()
    if not name:
        root_name = os.path.basename(os.path.normpath(project_root or ""))
        if root_name.lower().endswith(".ai-subtitle"):
            root_name = root_name[: -len(".ai-subtitle")]
        name = root_name.strip()
    if not name:
        name = str(getattr(project, "project_id", "") or "").strip()
    if not name:
        name = "Untitled Project"

    return f"{name} · {save_status}"
