import json
from datetime import datetime, timezone


def log_json(level: str, service: str, message: str, correlation_id=None, **extra):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": level.upper(),
        "service": service,
        "correlation_id": correlation_id or "sem-correlation-id",
        "message": message,
    }

    if extra:
        for k, v in extra.items():
            if isinstance(v, Exception):
                payload[k] = str(v)
            else:
                payload[k] = v

    print(json.dumps(payload, ensure_ascii=False), flush=True)
