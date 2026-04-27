from __future__ import annotations

import sqlite3
import hashlib
import os
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).with_name("commerce.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                loyalty_score REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                base_price REAL NOT NULL,
                stock INTEGER NOT NULL,
                max_stock INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                rating REAL NOT NULL DEFAULT 4.5,
                added_by_user_id INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS behavior_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                event_type TEXT NOT NULL CHECK(event_type IN ('view', 'cart_add', 'purchase')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                price_at_add REAL NOT NULL,
                PRIMARY KEY (cart_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                total REAL NOT NULL,
                payment_status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                PRIMARY KEY (order_id, product_id)
            );
            """
        )
        migrate_users(conn)
        migrate_orders(conn)
        ensure_inr_prices(conn)
        seed_data(conn)
        ensure_catalog_categories(conn)
        ensure_category_depth(conn)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, _digest = stored_hash.split("$", 1)
    return hash_password(password, salt) == stored_hash


def migrate_users(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "password_hash" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "role" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    product_columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "added_by_user_id" not in product_columns:
        conn.execute("ALTER TABLE products ADD COLUMN added_by_user_id INTEGER REFERENCES users(id)")


def migrate_orders(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
    if "payment_method" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT")
    if "payment_reference" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN payment_reference TEXT")
    if "shipping_address" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN shipping_address TEXT")
    if "shipping_city" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN shipping_city TEXT")
    if "shipping_pincode" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN shipping_pincode TEXT")


def seed_data(conn: sqlite3.Connection) -> None:
    ensure_user(conn, "Ashish Admin", "admin@example.com", "Ashish@25.....", "admin", 0.95)
    ensure_user(conn, "Demo User", "user@example.com", "User@12345", "user", 0.72)
    admin_id = conn.execute("SELECT id FROM users WHERE email = 'admin@example.com'").fetchone()["id"]
    conn.execute(
        """
        UPDATE products
        SET added_by_user_id = ?
        WHERE name IN ('Adjustable Laptop Stand') AND added_by_user_id IS NULL
        """,
        (admin_id,),
    )

    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] > 0:
        return

    products = [
        (
            "Adaptive Running Shoes",
            "Shoes",
            "Lightweight trainers with responsive cushioning for everyday runs.",
            6999.0,
            22,
            80,
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",
            4.8,
        ),
        (
            "Smart Travel Backpack",
            "Backpacks",
            "Weather-resistant backpack with modular storage and USB passthrough.",
            3499.0,
            12,
            60,
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=80",
            4.7,
        ),
        (
            "Noise Canceling Headphones",
            "Headsets",
            "Wireless headphones with long battery life and clear calls.",
            8999.0,
            7,
            45,
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",
            4.9,
        ),
        (
            "Ceramic Desk Lamp",
            "Lamps",
            "Warm dimmable lighting with a compact ceramic base.",
            1999.0,
            41,
            70,
            "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=80",
            4.5,
        ),
        (
            "Insulated Steel Bottle",
            "Bottles",
            "Keeps drinks cold for 24 hours with a leak-proof cap.",
            799.0,
            56,
            100,
            "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=80",
            4.6,
        ),
        (
            "Ergonomic Office Chair",
            "Chairs",
            "Adjustable support for focused workdays and long study sessions.",
            12499.0,
            9,
            35,
            "https://images.unsplash.com/photo-1580480055273-228ff5388ef8?auto=format&fit=crop&w=900&q=80",
            4.8,
        ),
        (
            "AMOLED Fitness Watch",
            "Watches",
            "Tracks workouts, heart rate, and sleep with a bright always-on display.",
            4999.0,
            18,
            65,
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80",
            4.6,
        ),
        (
            "Compact Kitchen Mixer",
            "Kitchen",
            "Powerful mixer for smoothies, sauces, and everyday meal prep.",
            2999.0,
            24,
            75,
            "https://images.unsplash.com/photo-1570222094114-d054a817e56b?auto=format&fit=crop&w=900&q=80",
            4.4,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO products
        (name, category, description, base_price, stock, max_stock, image_url, rating)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    event_seed = [
        (1, 1, "view"),
        (1, 1, "cart_add"),
        (1, 2, "view"),
        (1, 3, "view"),
        (1, 3, "view"),
        (1, 3, "cart_add"),
        (1, 3, "purchase"),
        (1, 6, "view"),
        (1, 6, "cart_add"),
    ]
    conn.executemany(
        "INSERT INTO behavior_events (user_id, product_id, event_type) VALUES (?, ?, ?)",
        event_seed,
    )


def ensure_user(
    conn: sqlite3.Connection,
    name: str,
    email: str,
    password: str,
    role: str,
    loyalty_score: float,
) -> None:
    password_hash = hash_password(password)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        conn.execute(
            """
            UPDATE users
            SET name = ?, password_hash = ?, role = ?, loyalty_score = ?
            WHERE email = ?
            """,
            (name, password_hash, role, loyalty_score, email),
        )
        return
    conn.execute(
        """
        INSERT INTO users (name, email, password_hash, role, loyalty_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, email, password_hash, role, loyalty_score),
    )


def ensure_catalog_categories(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'catalog_categories'").fetchone()
    if row and row["value"] == "v2":
        return

    category_updates = {
        "Adaptive Running Shoes": "Shoes",
        "Smart Travel Backpack": "Backpacks",
        "Noise Canceling Headphones": "Headsets",
        "Ceramic Desk Lamp": "Lamps",
        "Insulated Steel Bottle": "Bottles",
        "Ergonomic Office Chair": "Chairs",
    }
    for name, category in category_updates.items():
        conn.execute("UPDATE products SET category = ? WHERE name = ?", (category, name))

    extra_products = [
        (
            "AMOLED Fitness Watch",
            "Watches",
            "Tracks workouts, heart rate, and sleep with a bright always-on display.",
            4999.0,
            18,
            65,
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80",
            4.6,
        ),
        (
            "Compact Kitchen Mixer",
            "Kitchen",
            "Powerful mixer for smoothies, sauces, and everyday meal prep.",
            2999.0,
            24,
            75,
            "https://images.unsplash.com/photo-1570222094114-d054a817e56b?auto=format&fit=crop&w=900&q=80",
            4.4,
        ),
    ]
    for product in extra_products:
        existing = conn.execute("SELECT id FROM products WHERE name = ?", (product[0],)).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO products
                (name, category, description, base_price, stock, max_stock, image_url, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                product,
            )

    conn.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES ('catalog_categories', 'v2')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )


def ensure_category_depth(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'category_depth'").fetchone()
    if row and row["value"] == "v1":
        return

    category_specs = {
        "Shoes": [
            ("Trail Grip Shoes", 5499, "Rugged shoes for outdoor walking and light trekking."),
            ("City Runner Sneakers", 3999, "Breathable sneakers for daily city movement."),
            ("Court Classic Shoes", 3299, "Low-profile casual shoes with cushioned insoles."),
            ("Air Flex Trainers", 4599, "Flexible training shoes for gym and cardio sessions."),
            ("Formal Oxford Shoes", 5999, "Polished office shoes with durable soles."),
            ("Slip-On Walking Shoes", 2799, "Easy slip-on comfort for everyday errands."),
            ("Waterproof Hiking Shoes", 6999, "Supportive shoes built for wet trails."),
            ("Canvas Street Shoes", 1899, "Light canvas shoes for casual outfits."),
            ("Marathon Pace Shoes", 8999, "High-energy running shoes for long-distance runs."),
        ],
        "Backpacks": [
            ("Campus Day Backpack", 1499, "Compact backpack for books, lunch, and essentials."),
            ("Laptop Work Backpack", 2499, "Padded laptop storage with organized compartments."),
            ("Hiking Trail Backpack", 3999, "Outdoor pack with breathable back support."),
            ("Anti-Theft Travel Backpack", 3299, "Secure zippers and hidden back pocket for travel."),
            ("Roll-Top City Backpack", 2799, "Weather-ready roll-top design for commuting."),
            ("Kids School Backpack", 1199, "Lightweight school bag with playful color blocks."),
            ("Camera Gear Backpack", 5499, "Padded dividers for camera and lens storage."),
            ("Gym Duffel Backpack", 2199, "Hybrid gym bag with shoe pocket."),
            ("Minimal Office Backpack", 3499, "Clean professional backpack for workdays."),
        ],
        "Headsets": [
            ("Gaming RGB Headset", 2999, "Surround-style audio with a clear boom microphone."),
            ("Wireless Work Headset", 4499, "Comfortable headset for calls and meetings."),
            ("Bass Boost Headphones", 2499, "Deep bass tuning for music and movies."),
            ("Studio Monitor Headphones", 6999, "Balanced sound for creators and editors."),
            ("Kids Volume Safe Headset", 1299, "Volume-limited headset for young listeners."),
            ("Sports Neckband Headset", 1799, "Sweat-resistant neckband for workouts."),
            ("USB-C Office Headset", 1999, "Plug-in headset for laptops and tablets."),
            ("Travel ANC Headset", 9999, "Noise cancellation for flights and busy commutes."),
            ("Compact Earbud Headset", 1599, "Small wired earbuds with inline mic."),
        ],
        "Chairs": [
            ("Mesh Study Chair", 4999, "Breathable study chair with adjustable height."),
            ("Executive Office Chair", 8999, "High-back office chair with padded arms."),
            ("Gaming Recliner Chair", 14999, "Reclining chair with head and lumbar pillows."),
            ("Dining Accent Chair", 2999, "Upholstered dining chair with sturdy legs."),
            ("Foldable Visitor Chair", 1799, "Space-saving chair for guests and waiting areas."),
            ("Wooden Lounge Chair", 6999, "Relaxed lounge chair with warm wood finish."),
            ("Drafting Stool Chair", 6499, "Tall adjustable chair for counters and studios."),
            ("Kids Study Chair", 2299, "Compact ergonomic chair for young students."),
            ("Premium Task Chair", 10999, "Supportive chair for long work sessions."),
        ],
        "Bottles": [
            ("Copper Water Bottle", 999, "Copper-finish bottle for daily hydration."),
            ("Kids Sipper Bottle", 499, "Easy-grip sipper bottle for school bags."),
            ("Sports Shaker Bottle", 699, "Leak-proof shaker with measurement marks."),
            ("Glass Infuser Bottle", 899, "Glass bottle with fruit infuser chamber."),
            ("Thermal Coffee Flask", 1299, "Keeps coffee hot during commutes."),
            ("Wide Mouth Trek Bottle", 1199, "Durable bottle for hikes and gym days."),
            ("Slim Office Bottle", 799, "Minimal bottle that fits desk and bag pockets."),
            ("Collapsible Travel Bottle", 599, "Foldable bottle for light packing."),
            ("Premium Steel Tumbler", 1499, "Double-wall tumbler with spill-resistant lid."),
        ],
        "Lamps": [
            ("LED Study Lamp", 1199, "Adjustable study lamp with three brightness levels."),
            ("Wooden Bedside Lamp", 1899, "Warm bedside lighting with a wood base."),
            ("Clip-On Reading Lamp", 699, "Portable reading lamp for books and desks."),
            ("Smart Color Lamp", 2499, "App-ready lamp with color scenes."),
            ("Floor Corner Lamp", 3999, "Tall corner lamp for living rooms."),
            ("Rechargeable Desk Lamp", 1499, "Cordless lamp with touch controls."),
            ("Industrial Table Lamp", 2199, "Metal lamp with a clean industrial look."),
            ("Night Glow Lamp", 599, "Soft night light for bedrooms."),
            ("Architect Swing Lamp", 2799, "Classic adjustable arm lamp for work tables."),
        ],
        "Watches": [
            ("Classic Leather Watch", 2999, "Analog watch with a polished leather strap."),
            ("Digital Sports Watch", 1799, "Water-resistant digital watch with stopwatch."),
            ("Hybrid Smart Watch", 6499, "Analog style with smart notifications."),
            ("Kids Tracker Watch", 2499, "Colorful watch with activity reminders."),
            ("Luxury Steel Watch", 8999, "Stainless steel watch for formal wear."),
            ("Minimal Slim Watch", 1999, "Clean slim watch for everyday outfits."),
            ("Outdoor Compass Watch", 4499, "Adventure watch with compass-style details."),
            ("Women Rose Watch", 3499, "Rose-tone watch with elegant dial."),
            ("Fitness Band Pro", 2999, "Slim band for steps, sleep, and workouts."),
        ],
        "Kitchen": [
            ("Non-Stick Fry Pan", 1299, "Daily-use non-stick pan with cool-touch handle."),
            ("Chef Knife Set", 2499, "Sharp kitchen knives with storage block."),
            ("Electric Rice Cooker", 3299, "Automatic rice cooker for family meals."),
            ("Glass Storage Jars", 899, "Airtight jars for pantry organization."),
            ("Silicone Spatula Set", 499, "Heat-safe spatulas for cooking and baking."),
            ("Induction Saucepan", 1599, "Steel saucepan compatible with induction cooktops."),
            ("Manual Coffee Grinder", 1999, "Compact grinder for fresh coffee beans."),
            ("Bamboo Chopping Board", 799, "Durable board for vegetables and prep."),
            ("Air Fryer Basket", 4999, "Compact air fryer for quick snacks."),
        ],
        "Laptop Stands": [
            ("Portable Laptop Riser", 1499, "Lightweight riser for travel and study desks."),
            ("Desk Cooling Stand", 2199, "Laptop stand with cooling vents and stable feet."),
            ("Wooden Laptop Stand", 1799, "Warm wood stand for home office setups."),
            ("Adjustable Pro Stand", 2999, "Height-adjustable stand for ergonomic screens."),
            ("Foldable Tablet Stand", 999, "Small stand for tablets and compact laptops."),
            ("Aluminum Dock Stand", 3499, "Premium aluminum stand with cable routing."),
            ("Vertical Laptop Holder", 1299, "Space-saving vertical desktop holder."),
            ("Dual-Angle Study Stand", 1199, "Two-angle stand for typing and reading."),
            ("Heavy Duty Work Stand", 3999, "Strong stand for larger work laptops."),
        ],
    }

    image_by_category = {
        "Shoes": "https://images.unsplash.com/photo-1549298916-b41d501d3772?auto=format&fit=crop&w=900&q=80",
        "Backpacks": "https://images.unsplash.com/photo-1622560480605-d83c853bc5c3?auto=format&fit=crop&w=900&q=80",
        "Headsets": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=900&q=80",
        "Chairs": "https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?auto=format&fit=crop&w=900&q=80",
        "Bottles": "https://images.unsplash.com/photo-1523362628745-0c100150b504?auto=format&fit=crop&w=900&q=80",
        "Lamps": "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?auto=format&fit=crop&w=900&q=80",
        "Watches": "https://images.unsplash.com/photo-1434056886845-dac89ffe9b56?auto=format&fit=crop&w=900&q=80",
        "Kitchen": "https://images.unsplash.com/photo-1556910103-1c02745aae4d?auto=format&fit=crop&w=900&q=80",
        "Laptop Stands": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=900&q=80",
    }

    for category, products in category_specs.items():
        for index, (name, price, description) in enumerate(products, start=1):
            existing = conn.execute("SELECT id FROM products WHERE name = ?", (name,)).fetchone()
            if existing:
                continue
            max_stock = 55 + (index * 5)
            stock = max(8, max_stock - (index * 4))
            rating = round(4.1 + ((index % 7) * 0.1), 1)
            conn.execute(
                """
                INSERT INTO products
                (name, category, description, base_price, stock, max_stock, image_url, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, category, description, price, stock, max_stock, image_by_category[category], rating),
            )

    conn.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES ('category_depth', 'v1')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )


def ensure_inr_prices(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'currency'").fetchone()
    if row and row["value"] == "INR":
        return

    inr_prices = {
        "Adaptive Running Shoes": 6999.0,
        "Smart Travel Backpack": 3499.0,
        "Noise Canceling Headphones": 8999.0,
        "Ceramic Desk Lamp": 1999.0,
        "Insulated Steel Bottle": 799.0,
        "Ergonomic Office Chair": 12499.0,
    }
    for name, price in inr_prices.items():
        conn.execute("UPDATE products SET base_price = ? WHERE name = ?", (price, name))
    conn.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES ('currency', 'INR')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def get_user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("User not found")
    return dict(row)


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    user = dict(row)
    user.pop("password_hash", None)
    return user


def get_product_signals(conn: sqlite3.Connection, product_id: int) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS recent_views,
            SUM(CASE WHEN event_type = 'cart_add' THEN 1 ELSE 0 END) AS recent_cart_adds,
            SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS recent_purchases
        FROM behavior_events
        WHERE product_id = ?
          AND created_at >= datetime('now', '-7 days')
        """,
        (product_id,),
    ).fetchone()
    return {
        "recent_views": int(row["recent_views"] or 0),
        "recent_cart_adds": int(row["recent_cart_adds"] or 0),
        "recent_purchases": int(row["recent_purchases"] or 0),
    }


def get_or_create_cart(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM carts WHERE user_id = ? AND status = 'active'",
        (user_id,),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
    return int(cur.lastrowid)
