import json
import redis
import time

from database import get_db_connect

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

print("Consumer iniciado. Aguardando eventos...")

while True:

    evento = redis_client.brpop("fila_pedidos", timeout=0)

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