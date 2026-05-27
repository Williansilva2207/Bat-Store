import json
import os
import redis
import time

from database import get_db_connect

redis_client = redis.Redis(
    host=os.environ["REDIS_HOST"],
    port=int(os.environ["REDIS_PORT"]),
    decode_responses=True
)

QUEUE_NAME = os.environ["QUEUE_NAME"]
REDIS_BLOCK_TIMEOUT = int(os.environ["CATALOG_CONSUMER_BLOCK_TIMEOUT"])

print("Consumer iniciado. Aguardando eventos...")

while True:

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

        print(f"Estoque atualizado para {item_id}")
