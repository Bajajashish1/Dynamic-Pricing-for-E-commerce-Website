from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from database import (
    connect,
    get_or_create_cart,
    get_product_signals,
    get_user,
    init_db,
    public_user,
    rows_to_dicts,
    hash_password,
    verify_password,
)
from pricing_model import DynamicPricingModel, PricingInput


ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
MODEL = DynamicPricingModel()


class CommerceHandler(BaseHTTPRequestHandler):
    server_version = "DynamicCommerce/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.serve_static("index.html")
        elif parsed.path.startswith("/static/"):
            self.serve_static(parsed.path.removeprefix("/static/"))
        elif parsed.path == "/api/products":
            self.handle_products(parse_qs(parsed.query))
        elif parsed.path == "/api/cart":
            self.handle_cart_get(parse_qs(parsed.query))
        elif parsed.path == "/api/pricing/insights":
            self.handle_pricing_insights(parse_qs(parsed.query))
        else:
            self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            self.handle_event()
        elif parsed.path == "/api/login":
            self.handle_login()
        elif parsed.path == "/api/register":
            self.handle_register()
        elif parsed.path == "/api/products":
            self.handle_product_post()
        elif parsed.path == "/api/cart":
            self.handle_cart_post()
        elif parsed.path == "/api/checkout":
            self.handle_checkout()
        else:
            self.send_error(404, "Not found")

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/products":
            self.handle_product_patch()
        elif parsed.path == "/api/cart":
            self.handle_cart_patch()
        else:
            self.send_error(404, "Not found")

    def serve_static(self, relative_path: str) -> None:
        path = (STATIC_DIR / relative_path).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())) or not path.exists():
            self.send_error(404, "File not found")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def dynamic_product(self, conn, product: dict, user_id: int) -> dict:
        user = get_user(conn, user_id)
        added_by = None
        if product.get("added_by_user_id"):
            added_by = conn.execute(
                "SELECT name, role FROM users WHERE id = ?",
                (product["added_by_user_id"],),
            ).fetchone()
        signals = get_product_signals(conn, int(product["id"]))
        result = MODEL.predict(
            PricingInput(
                base_price=float(product["base_price"]),
                stock=int(product["stock"]),
                max_stock=int(product["max_stock"]),
                user_loyalty_score=float(user["loyalty_score"]),
                **signals,
            )
        )
        product["dynamic_price"] = result.price
        product["pricing"] = {
            "demand_score": result.demand_score,
            "stock_pressure": result.stock_pressure,
            "behavior_score": result.behavior_score,
            "adjustment": result.adjustment,
            "explanation": result.explanation,
        }
        product["added_by"] = dict(added_by) if added_by else None
        product["added_by_role"] = added_by["role"] if added_by else "system"
        return product

    def handle_login(self) -> None:
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not email or not password:
            self.send_json({"error": "Email and password are required"}, 400)
            return

        with connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
            if row is None or not verify_password(password, row["password_hash"]):
                self.send_json({"error": "Invalid email or password"}, 401)
                return
            self.send_json({"user": public_user(row)})

    def handle_register(self) -> None:
        data = self.read_json()
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if not name or not email or len(password) < 6:
            self.send_json({"error": "Name, email, and a 6+ character password are required"}, 400)
            return

        with connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, loyalty_score)
                    VALUES (?, ?, ?, 'user', 0.35)
                    """,
                    (name, email, hash_password(password)),
                )
            except Exception:
                self.send_json({"error": "An account with this email already exists"}, 409)
                return
            user = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
            self.send_json({"user": public_user(user)}, 201)

    def handle_products(self, query: dict[str, list[str]]) -> None:
        user_id = int(query.get("user_id", ["1"])[0])
        search = f"%{query.get('search', [''])[0].strip()}%"
        category = query.get("category", ["all"])[0]
        with connect() as conn:
            if category == "all":
                rows = conn.execute(
                    """
                    SELECT * FROM products
                    WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
                    ORDER BY category, name
                    """,
                    (search, search, search),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM products
                    WHERE category = ? AND (name LIKE ? OR description LIKE ?)
                    ORDER BY name
                    """,
                    (category, search, search),
                ).fetchall()
            products = [self.dynamic_product(conn, dict(row), user_id) for row in rows]
            categories = rows_to_dicts(conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall())
        self.send_json({"products": products, "categories": [item["category"] for item in categories]})

    def handle_product_post(self) -> None:
        data = self.read_json()
        admin_user_id = int(data.get("admin_user_id", 0))
        name = str(data.get("name", "")).strip()
        category = str(data.get("category", "")).strip()
        description = str(data.get("description", "")).strip()
        image_url = str(data.get("image_url", "")).strip()
        try:
            base_price = float(data.get("base_price", 0))
            stock = int(data.get("stock", 0))
            max_stock = int(data.get("max_stock", stock))
            rating = float(data.get("rating", 4.5))
        except (TypeError, ValueError):
            self.send_json({"error": "Price, stock, max stock, and rating must be valid numbers"}, 400)
            return

        if not name or not category or not description or base_price <= 0 or stock < 0 or max_stock <= 0:
            self.send_json({"error": "Complete product details are required"}, 400)
            return
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=900&q=80"

        with connect() as conn:
            try:
                admin = get_user(conn, admin_user_id)
            except ValueError:
                self.send_json({"error": "Admin user not found"}, 403)
                return
            if admin.get("role") != "admin":
                self.send_json({"error": "Only admins can add products"}, 403)
                return
            cur = conn.execute(
                """
                INSERT INTO products
                (name, category, description, base_price, stock, max_stock, image_url, rating, added_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, category, description, base_price, stock, max(max_stock, stock), image_url, rating, admin_user_id),
            )
            product = dict(conn.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone())
            product = self.dynamic_product(conn, product, admin_user_id)
        self.send_json({"product": product}, 201)

    def handle_product_patch(self) -> None:
        data = self.read_json()
        admin_user_id = int(data.get("admin_user_id", 0))
        product_id = int(data.get("product_id", 0))
        name = str(data.get("name", "")).strip()
        category = str(data.get("category", "")).strip()
        description = str(data.get("description", "")).strip()
        image_url = str(data.get("image_url", "")).strip()
        try:
            base_price = float(data.get("base_price", 0))
            stock = int(data.get("stock", 0))
            max_stock = int(data.get("max_stock", stock))
            rating = float(data.get("rating", 4.5))
        except (TypeError, ValueError):
            self.send_json({"error": "Price, stock, max stock, and rating must be valid numbers"}, 400)
            return

        if product_id <= 0 or not name or not category or not description or base_price <= 0 or stock < 0 or max_stock <= 0:
            self.send_json({"error": "Complete product details are required"}, 400)
            return
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=900&q=80"

        with connect() as conn:
            try:
                admin = get_user(conn, admin_user_id)
            except ValueError:
                self.send_json({"error": "Admin user not found"}, 403)
                return
            if admin.get("role") != "admin":
                self.send_json({"error": "Only admins can edit products"}, 403)
                return
            existing = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
            if existing is None:
                self.send_json({"error": "Product not found"}, 404)
                return
            conn.execute(
                """
                UPDATE products
                SET name = ?, category = ?, description = ?, base_price = ?,
                    stock = ?, max_stock = ?, image_url = ?, rating = ?
                WHERE id = ?
                """,
                (name, category, description, base_price, stock, max(max_stock, stock), image_url, rating, product_id),
            )
            product = dict(conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone())
            product = self.dynamic_product(conn, product, admin_user_id)
        self.send_json({"product": product})

    def handle_event(self) -> None:
        data = self.read_json()
        user_id = int(data.get("user_id", 1))
        product_id = int(data["product_id"])
        event_type = data["event_type"]
        if event_type not in {"view", "cart_add", "purchase"}:
            self.send_json({"error": "Invalid event type"}, 400)
            return
        with connect() as conn:
            conn.execute(
                "INSERT INTO behavior_events (user_id, product_id, event_type) VALUES (?, ?, ?)",
                (user_id, product_id, event_type),
            )
        self.send_json({"ok": True}, 201)

    def handle_cart_get(self, query: dict[str, list[str]]) -> None:
        user_id = int(query.get("user_id", ["1"])[0])
        with connect() as conn:
            cart_id = get_or_create_cart(conn, user_id)
            items = self.cart_items(conn, cart_id, user_id)
        self.send_json({"items": items, "total": round(sum(item["line_total"] for item in items), 2)})

    def handle_cart_post(self) -> None:
        data = self.read_json()
        user_id = int(data.get("user_id", 1))
        product_id = int(data["product_id"])
        quantity = max(1, int(data.get("quantity", 1)))
        with connect() as conn:
            cart_id = get_or_create_cart(conn, user_id)
            product = dict(conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone())
            price = self.dynamic_product(conn, product, user_id)["dynamic_price"]
            conn.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity, price_at_add)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cart_id, product_id)
                DO UPDATE SET quantity = quantity + excluded.quantity, price_at_add = excluded.price_at_add
                """,
                (cart_id, product_id, quantity, price),
            )
            conn.execute(
                "INSERT INTO behavior_events (user_id, product_id, event_type) VALUES (?, ?, 'cart_add')",
                (user_id, product_id),
            )
            items = self.cart_items(conn, cart_id, user_id)
        self.send_json({"items": items, "total": round(sum(item["line_total"] for item in items), 2)}, 201)

    def handle_cart_patch(self) -> None:
        data = self.read_json()
        user_id = int(data.get("user_id", 1))
        product_id = int(data["product_id"])
        quantity = int(data.get("quantity", 0))
        with connect() as conn:
            cart_id = get_or_create_cart(conn, user_id)
            if quantity <= 0:
                conn.execute("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?", (cart_id, product_id))
            else:
                conn.execute(
                    "UPDATE cart_items SET quantity = ? WHERE cart_id = ? AND product_id = ?",
                    (quantity, cart_id, product_id),
                )
            items = self.cart_items(conn, cart_id, user_id)
        self.send_json({"items": items, "total": round(sum(item["line_total"] for item in items), 2)})

    def handle_checkout(self) -> None:
        data = self.read_json()
        user_id = int(data.get("user_id", 1))
        payment_token = str(data.get("payment_token", "")).strip()
        payment_method = str(data.get("payment_method", "")).strip()
        payment_reference = str(data.get("payment_reference", "")).strip()
        shipping_address = str(data.get("shipping_address", "")).strip()
        shipping_city = str(data.get("shipping_city", "")).strip()
        shipping_pincode = str(data.get("shipping_pincode", "")).strip()
        allowed_methods = {"upi", "card", "wallet", "cod"}
        if len(shipping_address) < 10 or len(shipping_city) < 2 or len(shipping_pincode) < 5:
            self.send_json({"error": "Complete delivery address, city, and pincode are required"}, 400)
            return
        if payment_method not in allowed_methods:
            self.send_json({"error": "Choose a valid payment method"}, 400)
            return
        if payment_method != "cod" and len(payment_token) < 6:
            self.send_json({"error": "Payment gateway did not approve the payment"}, 400)
            return

        with connect() as conn:
            cart_id = get_or_create_cart(conn, user_id)
            items = self.cart_items(conn, cart_id, user_id)
            if not items:
                self.send_json({"error": "Cart is empty"}, 400)
                return
            total = round(sum(item["line_total"] for item in items), 2)
            order = conn.execute(
                """
                INSERT INTO orders
                (user_id, total, payment_status, payment_method, payment_reference,
                 shipping_address, shipping_city, shipping_pincode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    total,
                    "pending" if payment_method == "cod" else "paid",
                    payment_method,
                    payment_reference or None,
                    shipping_address,
                    shipping_city,
                    shipping_pincode,
                ),
            )
            order_id = int(order.lastrowid)
            for item in items:
                conn.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (order_id, item["id"], item["quantity"], item["price"]),
                )
                conn.execute(
                    "UPDATE products SET stock = max(stock - ?, 0) WHERE id = ?",
                    (item["quantity"], item["id"]),
                )
                conn.execute(
                    "INSERT INTO behavior_events (user_id, product_id, event_type) VALUES (?, ?, 'purchase')",
                    (user_id, item["id"]),
                )
            conn.execute("UPDATE carts SET status = 'checked_out' WHERE id = ?", (cart_id,))
        self.send_json(
            {
                "order_id": order_id,
                "total": total,
                "payment_status": "pending" if payment_method == "cod" else "paid",
                "payment_method": payment_method,
                "payment_reference": payment_reference,
                "shipping_address": shipping_address,
                "shipping_city": shipping_city,
                "shipping_pincode": shipping_pincode,
            },
            201,
        )

    def handle_pricing_insights(self, query: dict[str, list[str]]) -> None:
        user_id = int(query.get("user_id", ["1"])[0])
        with connect() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
            products = [self.dynamic_product(conn, dict(row), user_id) for row in rows]
        self.send_json({"products": products})

    def cart_items(self, conn, cart_id: int, user_id: int) -> list[dict]:
        rows = conn.execute(
            """
            SELECT p.*, ci.quantity, ci.price_at_add
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = ?
            ORDER BY p.name
            """,
            (cart_id,),
        ).fetchall()
        items = []
        for row in rows:
            product = self.dynamic_product(conn, dict(row), user_id)
            price = float(product["dynamic_price"])
            quantity = int(product["quantity"])
            items.append(
                {
                    "id": product["id"],
                    "name": product["name"],
                    "quantity": quantity,
                    "price": price,
                    "line_total": round(price * quantity, 2),
                    "stock": product["stock"],
                }
            )
        return items


def run() -> None:
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), CommerceHandler)
    print(f"Dynamic commerce server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
