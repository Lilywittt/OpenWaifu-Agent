# Social Sampling Tools

Use this directory for maintenance tools that inspect the real social sampling collectors.

```powershell
python run_social_sampling_audit.py
python run_social_sampling_audit.py --fail-on-unavailable
python run_social_sampling_audit.py --only bilibili_anime reddit_teenagers
```

The audit runs the registered collectors directly and writes reports under:

```text
runtime/service_state/social_sampling_audits/
```
