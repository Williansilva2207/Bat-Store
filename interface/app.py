import os
import requests
from flask import Flask, render_template, request, session, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")

# Service URLs
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://bat-auth-service:8000")
CATALOG_SERVICE_URL = os.environ.get("CATALOG_SERVICE_URL", "http://bat-catalog-service:8000")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://bat-order-service:8000")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://bat-payment-service:8000")
NOTIFICATION_SERVICE_URL = os.environ.get("NOTIFICATION_SERVICE_URL", "http://bat-notification-service:8000")

TIMEOUT = 3.0

def check_service_health(service_url):
    try:
        response = requests.get(f"{service_url}/", timeout=TIMEOUT)
        return response.status_code == 200
    except:
        return False

@app.route("/")
def home():
    services = {
        "bat-auth-service": AUTH_SERVICE_URL,
        "bat-catalog-service": CATALOG_SERVICE_URL,
        "bat-order-service": ORDER_SERVICE_URL,
        "bat-payment-service": PAYMENT_SERVICE_URL,
        "bat-notification-service": NOTIFICATION_SERVICE_URL,
    }
    
    service_status = {}
    for name, url in services.items():
        service_status[name] = "Online" if check_service_health(url) else "Offline"
    
    return render_template("index.html", services=service_status)

@app.route("/action/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    
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
        else:
            session["login_error"] = response.json().get("detail", "Erro ao fazer login")
    except Exception as e:
        session["login_error"] = str(e)
        
    return redirect(url_for("home"))

@app.route("/action/catalog", methods=["POST"])
def catalog():
    item_id = request.form.get("item_id")
    try:
        response = requests.get(f"{CATALOG_SERVICE_URL}/items/{item_id}", timeout=TIMEOUT)
        if response.status_code == 200:
            session["catalog_result"] = response.json()
        else:
            session["catalog_result"] = response.json()
    except Exception as e:
        session["catalog_result"] = {"error": str(e)}
        
    return redirect(url_for("home"))

@app.route("/action/order", methods=["POST"])
def create_order():
    token = session.get("token")
    if not token:
        session["order_result"] = {"error": "Usuário não autenticado. Faça login primeiro."}
        return redirect(url_for("home"))
        
    item_id = request.form.get("item_id")
    quantity = int(request.form.get("quantity", 1))
    method = request.form.get("method")
    
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
        session["order_result"] = response.json()
    except Exception as e:
        session["order_result"] = {"error": str(e)}
        
    return redirect(url_for("home"))

@app.route("/action/notify", methods=["POST"])
def notify():
    order_id = request.form.get("order_id")
    try:
        response = requests.get(f"{NOTIFICATION_SERVICE_URL}/notifications/{order_id}", timeout=TIMEOUT)
        session["notify_result"] = response.json()
    except Exception as e:
        session["notify_result"] = {"error": str(e)}
        
    return redirect(url_for("home"))

@app.route("/action/payment", methods=["POST"])
def payment():
    token = session.get("token")
    if not token:
        session["payment_result"] = {"error": "Usuário não autenticado. Faça login primeiro."}
        return redirect(url_for("home"))
        
    order_id = request.form.get("order_id")
    try:
        response = requests.get(
            f"{PAYMENT_SERVICE_URL}/payments/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT
        )
        session["payment_result"] = response.json()
    except Exception as e:
        session["payment_result"] = {"error": str(e)}
        
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
