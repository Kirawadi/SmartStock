# SmartStock - Inventory, Sales & Business Management System

Stack : **HTML + CSS, Python 3 (standard library only), SQL (SQLite)**. .

## Run
```
python app.py          # then open http://127.0.0.1:8000
python tests/test_smartstock.py   # automated tests
```
Optional: `PORT=9000 python app.py`. The database `smartstock.db` is created from `database/schema.sql` + `seed.sql` on first run (delete it to reset).

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | admin    | Admin@123  |
| Staff | staff    | Staff@123  |

Change both passwords after first login (My account).

## Features
- Secure login (PBKDF2 hashing, sessions, CSRF tokens, login throttling, security headers), admin/staff roles
- Dashboard: KPIs, 7-day sales chart (pure CSS), low-stock alerts, recent sales
- Products: CRUD, search, low-stock filter, CSV export, stock adjustment with full movement history
- Sales / POS: multi-item invoices, discount, atomic stock deduction, stock validation, printable invoice
- Purchases: receive stock from suppliers, updates quantity and cost
- Customers, Suppliers, Categories management
- Reports (admin): revenue, COGS, gross profit, purchases, top products, revenue by category, date filter
- User management (admin)

## Structure
```
app.py              Python server, routing, business logic (fills HTML templates)
database/           schema.sql (tables, constraints, indexes, view), seed.sql
templates/          HTML pages (layout, login, dashboard, forms, invoice ...)
static/style.css    CSS
tests/              unittest end-to-end tests
docs/               SDLC documents (01-05)
```
