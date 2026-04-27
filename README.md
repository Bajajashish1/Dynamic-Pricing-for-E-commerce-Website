# E-commerce Platform with Dynamic Pricing

A lightweight Python-backed e-commerce demo where product prices adjust using stock, demand, and user behavior signals. The backend uses only Python standard library modules, so the project is easy to run without dependency installation.

## Features

- SQLite schema for products, users, carts, orders, and behavior events
- Dynamic pricing engine with a small online linear model plus business guardrails
- Accessible responsive storefront served by the Python backend
- Product search, filters, cart, checkout, and mock payment flow
- Sign in and register screens with admin/user roles
- Admin product creation with rupee pricing
- Admin-style pricing summary API for demand, stock, and computed price factors

## Run

```powershell
python server.py
```

Then open:

```text
http://localhost:8000
```

To run on another system or hosting platform, set `HOST` and `PORT`:

```powershell
$env:HOST="0.0.0.0"
$env:PORT="8000"
python server.py
```

Deployment-ready files are included:

- `Procfile`
- `requirements.txt`
- `runtime.txt`
- `render.yaml`

If `python` is not available on your PATH, try:

```powershell
py server.py
```

## API

- `POST /api/login` - sign in as admin or user
- `POST /api/register` - create a customer account
- `GET /api/products` - list products with dynamic prices
- `POST /api/products` - admin-only product creation
- `POST /api/events` - record product behavior such as view or cart add
- `GET /api/cart?user_id=1` - get the active cart
- `POST /api/cart` - add a product to cart
- `PATCH /api/cart` - update cart quantity
- `POST /api/checkout` - place a mock paid order
- `GET /api/pricing/insights` - inspect pricing factors

## Demo Accounts

- Admin: `admin@example.com` / `Ashish@25.....`
- User: `user@example.com` / `User@12345`

## Project Structure

```text
server.py              Python backend and API routing
pricing_model.py       Dynamic pricing model
database.py            SQLite schema, seed data, queries
static/
  index.html           Accessible storefront shell
  styles.css           Responsive UI styling
  app.js               Storefront interactions
```
