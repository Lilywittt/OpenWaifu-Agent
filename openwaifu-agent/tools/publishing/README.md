# Publishing Smoke Tools

`run_publish_smoke.py` prepares browser publishing drafts through the same adapter interfaces used by the workbench. By default it disables final submission, writes request and receipt artifacts under the selected run, and reports whether each target reached a publishable state.

Examples:

```powershell
python run_publish_smoke.py
python run_publish_smoke.py --targets bilibili_dynamic instagram_browser_draft
python run_publish_smoke.py --run-id latest --json
```

Use `--allow-submit` only for deliberate live publishing tests.
