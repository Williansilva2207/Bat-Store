import json
import redis

class BatBrokerMiddleware:
    def __init__(self, host="localhost", port=6379):
        try:
            self.client = redis.Redis(host=host, port=port, decode_responses=True)
        except Exception:
            self.client = None

    def publish_event(self, queue_name: str, payload: dict):
        if self.client:
            try:
                self.client.lpush(queue_name, json.dumps(payload))
                print(f"[MIDDLEWARE LOG] Evento publicado com sucesso na fila: {queue_name}")
            except redis.RedisError:
                print("[MIDDLEWARE WARNING] Falha crítica no Broker. Evento descartado.")