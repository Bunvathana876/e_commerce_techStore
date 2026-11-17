#!/usr/bin/env python3
"""Verify a local production backend image against disposable PostgreSQL.

Requires Docker and cached postgres:16-alpine. Uses no existing database or
.env file, publishes only a random loopback API port, and stops its own
containers/network on exit. No persistent volumes are created.
"""
import argparse
import json
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--backend-image", required=True, help="Already-built local production image")
args = parser.parse_args()
prefix = "bp-check-" + secrets.token_hex(4)
image = args.backend_image
created = []
network_created = False
password = secrets.token_hex(24)
jwt_secret = secrets.token_hex(32)

def run(*args, input=None):
    result = subprocess.run(args, input=input, text=True, capture_output=True)
    if result.returncode:
        message = (result.stderr or result.stdout)[-2500:]
        for secret in (password, jwt_secret):
            message = message.replace(secret, "[REDACTED]")
        raise RuntimeError(message)
    return result.stdout.strip()

try:
    with tempfile.TemporaryDirectory(prefix="bp-smoke-") as tmp:
        config = Path(tmp) / "runtime.env"
        config.write_text("\n".join([
            "ENVIRONMENT=production", "POSTGRES_DB=bp_smoke", "POSTGRES_USER=bp_test",
            "POSTGRES_PASSWORD=" + password,
            "DATABASE_URL=postgresql+psycopg2://bp_test:" + password + "@" + prefix + "-db:5432/bp_smoke",
            "JWT_SECRET_KEY=" + jwt_secret,
            "CORS_ORIGINS=https://shop.example.test", "AUTO_INIT_DB=false", "SEED_DEMO_DATA=false",
            "UPLOAD_DIR=/var/lib/blue-panda/uploads", "RATE_LIMITING_ENABLED=false",
        ]) + "\n")
        config.chmod(0o600)
        run("docker", "image", "inspect", image)
        run("docker", "image", "inspect", "postgres:16-alpine")
        run("docker", "network", "create", prefix)
        network_created = True
        run("docker", "run", "-d", "--rm", "--name", prefix + "-db", "--network", prefix,
            "--env-file", str(config), "--tmpfs", "/var/lib/postgresql/data", "postgres:16-alpine")
        created.append(prefix + "-db")
        for _ in range(40):
            result = subprocess.run(["docker", "exec", prefix + "-db", "pg_isready", "-U", "bp_test", "-d", "bp_smoke"], capture_output=True)
            if result.returncode == 0: break
            time.sleep(.5)
        else: raise RuntimeError("Temporary PostgreSQL did not become ready")
        common = ["docker", "run", "--rm", "--network", prefix, "--env-file", str(config),
            "--read-only", "--tmpfs", "/tmp", "--tmpfs", "/var/lib/blue-panda/uploads:uid=10001,gid=10001"]
        run(*common, image, "alembic", "upgrade", "head")
        print("PASS production image migrations on empty PostgreSQL 16", flush=True)
        seed = """from app.db.database import SessionLocal
from app.models.user import User
from app.models.category import Category
from app.models.product import Product
from app.core.security import hash_password
from sqlalchemy import select, func
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(User)) == 0
    db.add(User(name='Runtime Admin', email='admin@example.com', role='admin', is_active=True, password_hash=hash_password('Runtime-test-password-123')))
    cat = Category(name='Runtime category', is_active=True)
    db.add(cat)
    db.flush()
    db.add(Product(name='Runtime product', category_id=cat.id, price=20, stock=10, is_active=True))
    db.commit()
"""
        run(*common, "-i", image, "python", "-", input=seed)
        run(*common[:3], "-d", "--name", prefix + "-api", "--publish", "127.0.0.1::8000", *common[3:], image)
        created.append(prefix + "-api")
        port = run("docker", "port", prefix + "-api", "8000/tcp").split(":")[-1]
        base = "http://127.0.0.1:" + port
        def req(method, path, body=None, token=None, headers=None):
            headers = dict(headers or {})
            if token: headers["Authorization"] = "Bearer " + token
            if body is not None: headers["Content-Type"] = "application/json"
            request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
            try: response = urllib.request.urlopen(request, timeout=10)
            except urllib.error.HTTPError as exc: response = exc
            raw = response.read()
            try: data = json.loads(raw)
            except ValueError: data = None
            return response.status, data, response.headers
        for _ in range(40):
            try:
                if req("GET", "/readyz")[0] == 200: break
            except OSError: pass
            time.sleep(.5)
        else: raise RuntimeError("Production API failed readiness")
        assert run("docker", "exec", prefix + "-api", "id", "-u") == "10001"
        assert req("GET", "/health")[0] == 200
        assert req("GET", "/docs")[0] == 404
        assert req("GET", "/api/orders/all")[0] in (401, 403)
        status, data, _ = req("POST", "/api/auth/login", {"email":"admin@example.com", "password":"Runtime-test-password-123"})
        assert status == 200, f"Login returned HTTP {status}"
        admin = data["data"]["access_token"]
        status, data, _ = req("POST", "/api/auth/register", {"name":"Runtime Customer", "email":"customer@example.com", "password":"Runtime-test-password-123"})
        assert status in (200,201), f"Registration returned HTTP {status}"
        status, data, _ = req("POST", "/api/auth/login", {"email":"customer@example.com", "password":"Runtime-test-password-123"})
        customer = data["data"]["access_token"]
        for api in ("/api", "/api/v1"):
            assert req("GET", api + "/orders/all", token=customer)[0] == 403
            payload = {"shipping_address":"123 Runtime Test Street", "payment_method":"Cash on Delivery", "items":[{"product_id":1,"quantity":2}], "idempotency_key":"runtime-" + api}
            status, order, _ = req("POST", api + "/orders", payload, customer)
            assert status == 201, f"Checkout returned HTTP {status}"
            status, replay, headers = req("POST", api + "/orders", payload, customer)
            assert status == 200 and replay["data"]["id"] == order["data"]["id"]
            assert headers.get("Idempotent-Replayed") == "true"
            assert order["data"]["payment_status"] == "pending"
            assert req("DELETE", api + "/orders/" + str(order["data"]["id"]), token=customer)[0] == 403
            assert req("DELETE", api + "/orders/" + str(order["data"]["id"]), token=admin)[0] == 200
            assert req("DELETE", api + "/orders/" + str(order["data"]["id"]), token=admin)[0] == 409
        assert req("GET", "/api/products/1")[1]["data"]["stock"] == 10
        status, _, headers = req("OPTIONS", "/api/orders", headers={"Origin":"https://shop.example.test", "Access-Control-Request-Method":"POST", "Access-Control-Request-Headers":"authorization,idempotency-key,content-type"})
        assert status == 200 and headers.get("Access-Control-Allow-Origin") == "https://shop.example.test"
        assert req("OPTIONS", "/api/orders", headers={"Origin":"https://untrusted.example.test", "Access-Control-Request-Method":"POST"})[0] == 400
        print("PASS non-root read-only production API, readiness, auth/role denials, COD, retry, cancellation, stock and CORS on both API prefixes", flush=True)
finally:
    for name in reversed(created):
        subprocess.run(["docker", "stop", name], capture_output=True)
    if network_created:
        subprocess.run(["docker", "network", "rm", prefix], capture_output=True)
    print("Temporary smoke resources stopped", flush=True)
