from workbench.worker import _load_worker_request_payload, run_workbench_worker


def run_content_workbench_worker(project_dir, request=None, *, request_id: str = "") -> int:
    return run_workbench_worker(project_dir, request=request, request_id=request_id)


__all__ = ["_load_worker_request_payload", "run_content_workbench_worker"]
