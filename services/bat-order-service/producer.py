import redis
import json

redis_client = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)

def publish_order_event(data):

    redis_client.publish(
        'orders',
        json.dumps(data)
    )

    print("Evento publicado no Redis")