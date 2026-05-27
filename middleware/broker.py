import json
import os
import threading
import time

import redis

from middleware.structured_logging import log_json


class BatBrokerMiddleware:
    def __init__(self, host, port, service_name="bat-order-service"):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.reconnect_interval = int(os.environ.get("REDIS_RECONNECT_INTERVAL", "5"))
        self.client = None
        self._reconnect_thread = None
        self._connect()

    def _connect(self):
        try:
            self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True, socket_timeout=3)
            self.client.ping()
            log_json("info", self.service_name, "redis_connection_restored", None)
            self._reconnect_thread = None
            return True
        except redis.RedisError as error:
            self.client = None
            log_json("error", self.service_name, "redis_connection_failed", error)
            self._schedule_reconnect()
            return False

    def _schedule_reconnect(self):
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return

        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def _reconnect_loop(self):
        while True:
            try:
                self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True, socket_timeout=3)
                self.client.ping()
                log_json("info", self.service_name, "redis_connection_restored", None)
                return
            except redis.RedisError as error:
                log_json("error", self.service_name, "redis_connection_failed", error)
                time.sleep(self.reconnect_interval)

    def publish_event(self, queue_name: str, payload: dict):
        if not self.client:
            connected = self._connect()
            if not connected:
                log_json(
                    "warning",
                    self.service_name,
                    "publish_event_deferred",
                    "Redis indisponível, evento mantido para reconexão",
                    queue_name=queue_name,
                )
                self._schedule_reconnect()
                return False

        try:
            self.client.lpush(queue_name, json.dumps(payload))
            log_json(
                "info",
                self.service_name,
                "event_published",
                None,
                queue_name=queue_name,
            )
            return True
        except redis.RedisError as error:
            self.client = None
            log_json("error", self.service_name, "redis_connection_failed", error)
            self._schedule_reconnect()
            log_json(
                "warning",
                self.service_name,
                "publish_event_deferred",
                error,
                queue_name=queue_name,
            )
            return False
