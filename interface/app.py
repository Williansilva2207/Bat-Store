import os
import requests
import json
from datetime import datetime
from flask import Flask, render_template, request, session, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")

# Service URLs
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://auth:8000")
CATALOG_SERVICE_URL = os.environ.get("CATALOG_SERVICE_URL", "http://catalog:8000")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order:8000")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://payment:8000")
NOTIFICATION_SERVICE_URL = os.environ.get("NOTIFICATION_SERVICE_URL", "http://notification:8000")

# Timeout for requests
TIMEOUT = 3.0

def check_service_health(service_url):
    """Check if a service is healthy."""
    try:
        response = requests.get(f"{service_url}/", timeout=TIMEOUT)
        return response.status_code == 200
    except:
        return False

@app.route("/")
def home():
    """Home page with service status."""
    services = {
        "Autenticação": AUTH_SERVICE_URL,
        "Catálogo": CATALOG_SERVICE_URL,
        "Pedidos": ORDER_SERVICE_URL,
        "Pagamentos": PAYMENT_SERVICE_URL,
        "Notificações": NOTIFICATION_SERVICE_URL,
    }
    
    service_status = {}
    for name, url in services.items():
        service_status[name] = check_service_health(url)
    
    token = session.get("token")
    username = session.get("username")
    
    return render_template("index.html", services=service_status, token=token, username=username)

@app.route("/auth")
def auth_page():
    """Authentication page."""
    return render_template("auth.html")

@app.route("/api/login", methods=["POST"])
def login():
    """Login endpoint."""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    
    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/login",
            json={"username": username, "password": password},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            session["token"] = result["access_token"]
            session["username"] = username
            session["role"] = result.get("role", "user")
            return jsonify({"success": True, "token": result["access_token"]}), 200
        else:
            return jsonify({"success": False, "error": response.json().get("detail", "Erro ao fazer login")}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/catalog")
def catalog():
    """Catalog page."""
    items = []
    try:
        response = requests.get(f"{CATALOG_SERVICE_URL}/../", timeout=TIMEOUT)
        if response.status_code == 200:
            # Get items one by one by IDs
            item_ids = ["bat-01", "bat-02", "bat-03", "bat-04", "bat-05"]
            for item_id in item_ids:
                try:
                    item_response = requests.get(f"{CATALOG_SERVICE_URL}/{item_id}", timeout=TIMEOUT)
                    if item_response.status_code == 200:
                        items.append(item_response.json())
                except:
                    pass
    except:
        pass
    
    return render_template("catalog.html", items=items)

@app.route("/orders")
def orders():
    """Orders page."""
    token = session.get("token")
    if not token:
        return redirect(url_for("auth_page"))
    
    items = []
    try:
        item_ids = ["bat-01", "bat-02", "bat-03", "bat-04", "bat-05"]
        for item_id in item_ids:
            try:
                item_response = requests.get(f"{CATALOG_SERVICE_URL}/{item_id}", timeout=TIMEOUT)
                if item_response.status_code == 200:
                    items.append(item_response.json())
            except:
                pass
    except:
        pass
    
    return render_template("orders.html", items=items, token=token)

@app.route("/api/create-order", methods=["POST"])
def create_order():
    """Create order endpoint."""
    token = session.get("token")
    if not token:
        return jsonify({"success": False, "error": "Token não encontrado"}), 401
    
    data = request.get_json()
    item_id = data.get("item_id")
    quantity = int(data.get("quantity", 1))
    method = data.get("method", "credit_card")
    
    try:
        response = requests.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={
                "item_id": item_id,
                "quantity": quantity,
                "method": method
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({"success": True, "order": result}), 200
        else:
            return jsonify({"success": False, "error": response.json().get("detail", "Erro ao criar pedido")}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/get-notification/<int:order_id>", methods=["GET"])
def get_notification(order_id):
    """Get notification by order ID."""
    try:
        response = requests.get(
            f"{NOTIFICATION_SERVICE_URL}/notifications/{order_id}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({"success": True, "notifications": result}), 200
        else:
            return jsonify({"success": False, "error": "Notificação não encontrada"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/get-payment/<int:order_id>", methods=["GET"])
def get_payment(order_id):
    """Get payment by order ID."""
    token = session.get("token")
    if not token:
        return jsonify({"success": False, "error": "Token não encontrado"}), 401
    
    try:
        response = requests.get(
            f"{PAYMENT_SERVICE_URL}/payments/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({"success": True, "payment": result}), 200
        elif response.status_code == 403:
            return jsonify({"success": False, "error": "Apenas administradores podem acessar"}), 403
        else:
            return jsonify({"success": False, "error": "Pagamento não encontrado"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/observability")
def observability():
    """Observability page with links to Grafana and Jaeger."""
    grafana_url = "http://localhost:3000"
    jaeger_url = "http://localhost:16686"
    
    return render_template("observability.html", grafana_url=grafana_url, jaeger_url=jaeger_url)

@app.route("/logout", methods=["POST"])
def logout():
    """Logout endpoint."""
    session.clear()
    return jsonify({"success": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
