-- SmartStock schema (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
  pw_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('admin','staff')),
  active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE TABLE sessions (
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL, flash TEXT, created TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);

CREATE TABLE suppliers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, address TEXT);

CREATE TABLE customers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, address TEXT);

CREATE TABLE products (
  id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
  cost REAL NOT NULL CHECK (cost >= 0), price REAL NOT NULL CHECK (price >= 0),
  qty INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),
  reorder_level INTEGER NOT NULL DEFAULT 5 CHECK (reorder_level >= 0),
  active INTEGER NOT NULL DEFAULT 1);

CREATE TABLE purchases (
  id INTEGER PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
  total REAL NOT NULL, user_id INTEGER REFERENCES users(id),
  created TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE TABLE purchase_items (
  id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL CHECK (qty > 0),
  cost REAL NOT NULL);

CREATE TABLE sales (
  id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
  subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, total REAL NOT NULL,
  user_id INTEGER REFERENCES users(id),
  created TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE TABLE sale_items (
  id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL CHECK (qty > 0),
  price REAL NOT NULL, cost REAL NOT NULL);

CREATE TABLE stock_movements (
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
  change INTEGER NOT NULL, reason TEXT NOT NULL, user_id INTEGER REFERENCES users(id),
  created TEXT NOT NULL DEFAULT (datetime('now','localtime')));

CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_sales_created ON sales(created);
CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX idx_moves_product ON stock_movements(product_id);

CREATE VIEW low_stock AS
  SELECT * FROM products WHERE active = 1 AND qty <= reorder_level;
