from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from ops.dashboard_store import pin_dashboard_recent_runs
from workbench.identity import WorkbenchViewer
from workbench.profile import PRIVATE_PROFILE, PUBLIC_PROFILE
from workbench.store import (
    append_run_index_record,
    build_content_workbench_snapshot,
    pin_workbench_surface_items,
    reorder_workbench_surface_pins,
    toggle_workbench_favorite,
    workbench_inventory_paths,
)


class WorkbenchDisplayOrderTests(unittest.TestCase):
    def _private_viewer(self) -> WorkbenchViewer:
        return WorkbenchViewer(
            owner_id="private",
            display_name="Private Workbench",
            email="",
            authenticated=True,
            public=False,
        )

    def _public_viewer(self, owner_id: str = "guest-1") -> WorkbenchViewer:
        return WorkbenchViewer(
            owner_id=owner_id,
            display_name="Public Viewer",
            email="",
            authenticated=False,
            public=True,
        )

    def _append_run(self, project_dir: Path, run_id: str, recorded_at: str, title: str, *, owner_id: str = "private") -> Path:
        run_dir = project_dir / "runtime" / "runs" / run_id
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "run_summary.json"
        write_json(
            summary_path,
            {
                "runId": run_id,
                "sceneDraftPremiseZh": title,
            },
        )
        append_run_index_record(
            project_dir,
            {
                "status": "completed",
                "runId": run_id,
                "runRoot": str(run_dir),
                "summaryPath": str(summary_path),
                "sceneDraftPremiseZh": title,
                "recordedAt": recorded_at,
                "finishedAt": recorded_at,
                "ownerId": owner_id,
                "request": {
                    "sourceKind": "scene_draft_text",
                    "endStage": "image",
                    "label": title,
                    "ownerId": owner_id,
                },
            },
        )
        return run_dir

    def _write_runtime_run_summary(self, project_dir: Path, run_id: str, title: str) -> Path:
        run_dir = project_dir / "runtime" / "runs" / run_id
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            output_dir / "run_summary.json",
            {
                "runId": run_id,
                "sceneDraftPremiseZh": title,
            },
        )
        return run_dir

    def test_inventory_paths_expose_display_order_store(self):
        with TemporaryDirectory() as temp_dir:
            paths = workbench_inventory_paths(Path(temp_dir))

        self.assertIn("displayOrderPath", paths)
        self.assertTrue(paths["displayOrderPath"].endswith("display_order.json"))

    def test_private_history_supports_pin_and_reorder_groups(self):
        viewer = self._private_viewer()
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            records = [
                ("2026-04-11T10-00-00_run_a", "2026-04-11T10:00:00", "Morning"),
                ("2026-04-11T11-00-00_run_b", "2026-04-11T11:00:00", "Noon"),
                ("2026-04-11T12-00-00_run_c", "2026-04-11T12:00:00", "Evening"),
            ]
            for run_id, recorded_at, title in records:
                self._append_run(project_dir, run_id, recorded_at, title)

            initial_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            self.assertEqual(
                [item["runId"] for item in initial_snapshot["history"][:3]],
                ["2026-04-11T10-00-00_run_a", "2026-04-11T11-00-00_run_b", "2026-04-11T12-00-00_run_c"],
            )

            pin_workbench_surface_items(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "itemIds": ["2026-04-11T10-00-00_run_a", "2026-04-11T11-00-00_run_b"],
                    "pinned": True,
                },
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            pinned_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            self.assertEqual(
                [item["runId"] for item in pinned_snapshot["historyGroups"]["pinned"]],
                ["2026-04-11T10-00-00_run_a", "2026-04-11T11-00-00_run_b"],
            )
            self.assertEqual(
                [item["runId"] for item in pinned_snapshot["historyGroups"]["regular"][:1]],
                ["2026-04-11T12-00-00_run_c"],
            )
            self.assertEqual(pinned_snapshot["historyStats"]["pinned"], 2)

            reorder_workbench_surface_pins(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "orderedItemIds": ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a"],
                },
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            reordered_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )

        self.assertEqual(
            [item["runId"] for item in reordered_snapshot["historyGroups"]["pinned"]],
            ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a"],
        )
        self.assertEqual(
            [item["runId"] for item in reordered_snapshot["history"][:3]],
            ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a", "2026-04-11T12-00-00_run_c"],
        )

    def test_pinned_history_is_applied_before_history_limit(self):
        viewer = self._private_viewer()
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            self._append_run(project_dir, "2026-04-11T10-00-00_run_a", "2026-04-11T10:00:00", "Morning")
            self._append_run(project_dir, "2026-04-11T11-00-00_run_b", "2026-04-11T11:00:00", "Noon")
            self._append_run(project_dir, "2026-04-11T12-00-00_run_c", "2026-04-11T12:00:00", "Evening")

            pin_workbench_surface_items(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "itemIds": ["2026-04-11T12-00-00_run_c"],
                    "pinned": True,
                },
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
                history_limit=1,
            )

        self.assertEqual([item["runId"] for item in snapshot["history"]], ["2026-04-11T12-00-00_run_c"])
        self.assertEqual([item["runId"] for item in snapshot["historyGroups"]["pinned"]], ["2026-04-11T12-00-00_run_c"])
        self.assertEqual(snapshot["historyStats"]["pinned"], 1)

    def test_favorite_path_pin_order_is_shared_with_global_history(self):
        viewer = self._private_viewer()
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_a = self._append_run(project_dir, "2026-04-11T10-00-00_run_a", "2026-04-11T10:00:00", "Morning")
            run_b = self._append_run(project_dir, "2026-04-11T11-00-00_run_b", "2026-04-11T11:00:00", "Noon")

            favorite_a = toggle_workbench_favorite(project_dir, {"kind": "path", "path": str(run_a)})["entry"]
            favorite_b = toggle_workbench_favorite(project_dir, {"kind": "path", "path": str(run_b)})["entry"]

            pin_workbench_surface_items(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "itemIds": [favorite_a["selectionKey"], favorite_b["selectionKey"]],
                    "pinned": True,
                },
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )
            reorder_workbench_surface_pins(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "orderedItemIds": [favorite_b["selectionKey"], favorite_a["selectionKey"]],
                },
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )

            favorites_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
                history_filter="favorites",
            )
            global_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
                history_filter="active",
            )

        self.assertEqual(
            [item["surfaceItemId"] for item in favorites_snapshot["historyGroups"]["pinned"]],
            ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a"],
        )
        self.assertEqual(
            [item["runId"] for item in favorites_snapshot["historyGroups"]["pinned"]],
            ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a"],
        )
        self.assertEqual(
            [item["runId"] for item in global_snapshot["historyGroups"]["pinned"]],
            ["2026-04-11T11-00-00_run_b", "2026-04-11T10-00-00_run_a"],
        )

    def test_private_history_order_projects_into_public_history(self):
        private_viewer = self._private_viewer()
        public_viewer = self._public_viewer(owner_id="guest-1")
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            self._append_run(
                project_dir,
                "2026-04-11T10-00-00_run_private",
                "2026-04-11T10:00:00",
                "Private Only",
                owner_id="private",
            )
            self._append_run(
                project_dir,
                "2026-04-11T11-00-00_run_guest_a",
                "2026-04-11T11:00:00",
                "Guest A",
                owner_id="guest-1",
            )
            self._append_run(
                project_dir,
                "2026-04-11T12-00-00_run_guest_b",
                "2026-04-11T12:00:00",
                "Guest B",
                owner_id="guest-1",
            )

            pin_workbench_surface_items(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "itemIds": [
                        "2026-04-11T12-00-00_run_guest_b",
                        "2026-04-11T10-00-00_run_private",
                        "2026-04-11T11-00-00_run_guest_a",
                    ],
                    "pinned": True,
                },
                viewer=private_viewer,
                profile=PRIVATE_PROFILE,
            )
            reorder_workbench_surface_pins(
                project_dir,
                {
                    "surfaceId": "workbench_history",
                    "orderedItemIds": [
                        "2026-04-11T12-00-00_run_guest_b",
                        "2026-04-11T10-00-00_run_private",
                        "2026-04-11T11-00-00_run_guest_a",
                    ],
                },
                viewer=private_viewer,
                profile=PRIVATE_PROFILE,
            )

            public_snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=public_viewer,
                profile=PUBLIC_PROFILE,
                history_filter="active",
            )

        self.assertEqual(
            [item["runId"] for item in public_snapshot["historyGroups"]["pinned"]],
            [
                "2026-04-11T12-00-00_run_guest_b",
                "2026-04-11T10-00-00_run_private",
                "2026-04-11T11-00-00_run_guest_a",
            ],
        )
        self.assertEqual(
            [item["runId"] for item in public_snapshot["history"][:3]],
            [
                "2026-04-11T12-00-00_run_guest_b",
                "2026-04-11T10-00-00_run_private",
                "2026-04-11T11-00-00_run_guest_a",
            ],
        )

    def test_runtime_qq_runs_are_indexed_for_workbench_history(self):
        viewer = self._private_viewer()
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_id = "2026-06-11T12-07-41_qqbot_generate_demo"
            self._write_runtime_run_summary(project_dir, run_id, "校园天台")

            snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )

        self.assertEqual(snapshot["history"][0]["runId"], run_id)
        self.assertEqual(snapshot["history"][0]["sceneDraftPremiseZh"], "校园天台")

    def test_ops_recent_pin_projects_to_workbench_history(self):
        viewer = self._private_viewer()
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            run_id = "2026-06-11T12-07-41_qqbot_generate_demo"
            self._write_runtime_run_summary(project_dir, run_id, "运维置顶")

            pin_dashboard_recent_runs(project_dir, {"itemIds": [run_id], "pinned": True})
            snapshot = build_content_workbench_snapshot(
                project_dir,
                viewer=viewer,
                profile=PRIVATE_PROFILE,
            )

        self.assertEqual([item["runId"] for item in snapshot["historyGroups"]["pinned"]], [run_id])
        self.assertTrue(snapshot["history"][0]["pinned"])


if __name__ == "__main__":
    unittest.main()
