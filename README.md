# Code Fuzion 2026 H7 backend

This repository contains the Django/Channels backend foundation for the
campus-fest crowd density monitor. It is intentionally a first iteration:
feature endpoints, risk services, realtime delivery and the vision worker are
owned by separate branches described in [API_CONTRACT.md](API_CONTRACT.md).

## Local foundation checks

```powershell
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate
python -m pytest
python manage.py runserver
```

`GET http://127.0.0.1:8000/health/` is the only implemented HTTP endpoint in
the foundation. Other API paths return an explicit `501 NOT_IMPLEMENTED` until
their owning workstream is integrated. No H7 FPS or counting-accuracy target
has been measured or claimed.

Copy `.env.example` to `.env` for local configuration. Never commit secrets,
worker tokens, private source URLs or private video fixtures.
