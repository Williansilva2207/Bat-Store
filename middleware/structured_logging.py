import json
from datetime import datetime, timezone


def log_json(level: str, svc: str, event: str, error=None, **extra):
    payload = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "level": level,
        "svc": svc,
        "event": event,
    }

    if error is not None:
        payload["error"] = str(error)

    if extra:
        payload.update(extra)

    print(json.dumps(payload, ensure_ascii=False))
