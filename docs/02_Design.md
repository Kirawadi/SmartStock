# 2. System Design (SDLC Phase 2)

## 2.1 Architecture
Three layers in one process: Presentation (server-rendered HTML + CSS) -> Application (Python routing + business rules in `app.py`) -> Data (SQLite via parameterised SQL).

```
Browser --HTTP--> Handler/Router --> Route functions --> sqlite3 --> smartstock.db
```

## 2.2 Database design (ERD)
```
users 1--* sessions            categories 1--* products *--1 suppliers
users 1--* sales               customers  1--* sales 1--* sale_items *--1 products
users 1--* purchases           suppliers  1--* purchases 1--* purchase_items *--1 products
products 1--* stock_movements
```
Normalised to 3NF. Key rules: `qty >= 0`, `price/cost >= 0`, unique SKU, role CHECK, foreign keys ON, sale_items snapshots `price` and `cost` so historical profit never changes. View `low_stock` powers alerts. Indexes on name, sales date, sale_items.sale_id, stock_movements.product_id.

## 2.3 Key flows
Sale: validate input -> BEGIN IMMEDIATE -> check each product stock -> insert sale + items -> decrement stock -> log movement -> COMMIT (any error -> ROLLBACK).
Purchase: same pattern, increments stock and updates cost.

## 2.4 Security design
PBKDF2-SHA256 (200k iterations, per-user salt); random 256-bit session tokens, HttpOnly + SameSite=Strict cookie; per-session CSRF token on every POST; all SQL parameterised; all output HTML-escaped; CSP `default-src 'self'`, X-Frame-Options DENY; login throttling (5 fails / 5 min / IP); role checks server-side.

## 2.5 UI design
Sidebar navigation, card layout, KPI tiles, status tags (OK/Low/Out), responsive grid, print stylesheet for invoices.
