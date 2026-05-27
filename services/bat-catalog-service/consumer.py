import json
import os
import time

import redis

from database import get_db_connect
from middleware.structured_logging import log_json

QUEUE_NAME = os.environ["QUEUE_NAME"]
REDIS_BLOCK_TIMEOUT = int(os.environ["CATALOG_CONSUMER_BLOCK_TIMEOUT"])
REDIS_RECONNECT_INTERVAL = int(os.environ.get("REDIS_RECONNECT_INTERVAL", "5"))


def conectar_redis():
    while True:
        try:
            cliente = redis.Redis(
                host=os.environ["REDIS_HOST"],
                port=int(os.environ["REDIS_PORT"]),
                decode_responses=True,
                socket_timeout=3,
            )
            cliente.ping()
            log_json("info", "bat-catalog-service", "redis_connection_restored", None)
            return cliente
        except redis.RedisError as error:
            log_json("error", "bat-catalog-service", "redis_connection_failed", error)
            time.sleep(REDIS_RECONNECT_INTERVAL)


redis_client = conectar_redis()
log_json("info", "bat-catalog-service", "consumer_started", None, queue_name=QUEUE_NAME)

while True:
    try:
        evento = redis_client.brpop(QUEUE_NAME, timeout=REDIS_BLOCK_TIMEOUT)

        if evento:
            _, payload = evento

            data = json.loads(payload)

            item_id = data["item_id"]
            quantity = data["quantity"]

            conecta = get_db_connect()

            cursor = conecta.cursor()

            cursor.execute(
                "UPDATE items SET stock = stock - ? WHERE id = ?",
                (quantity, item_id)
            )

            conecta.commit()

            conecta.close()

            log_json(
                "info",
                "bat-catalog-service",
                "stock_updated",
                None,
                item_id=item_id,
                quantity=quantity,
            )
    except redis.RedisError as error:
        log_json("error", "bat-catalog-service", "redis_connection_failed", error)
        redis_client = conectar_redis()
    except json.JSONDecodeError as error:
        log_json("error", "bat-catalog-service", "message_parse_failed", error)
    except Exception as error:
        log_json("error", "bat-catalog-service", "catalog_consumer_failed", error)
