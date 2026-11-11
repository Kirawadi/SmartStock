#!/usr/bin/env python3
"""SmartStock - Inventory, Sales & Business Management System.
Stack: HTML + CSS (templates/static), Python 3 (stdlib only), SQL (SQLite).
Run:  python app.py   ->  http://127.0.0.1:8000   (admin / Admin@123)
"""
import csv, hashlib, hmac, html, io, os, re, secrets, sqlite3, time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("SMARTSTOCK_DB", os.path.join(BASE, "smartstock.db"))
CUR = "\u20b9"
ROWS = 6  # line-item rows on sale / purchase forms
FAILS = {}  # ip -> [timestamps] (login throttling)


# ---------------------------------------------------------------- database
def connect():
    c = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def rows(sql, args=()):
    c = connect()
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


def run(sql, args=()):
    c = connect()
    try:
        return c.execute(sql, args).lastrowid
    finally:
        c.close()


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${h}"


def check_pw(pw, stored):
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_pw(pw, salt), stored)


def init_db():
    if os.path.exists(DB_PATH):
        return
    c = connect()
    for f in ("schema.sql", "seed.sql"):
        with open(os.path.join(BASE, "database", f), encoding="utf-8") as fh:
            c.executescript(fh.read())
    c.execute("INSERT INTO users(username,full_name,pw_hash,role) VALUES (?,?,?,?)",
              ("admin", "Administrator", hash_pw("Admin@123"), "admin"))
    c.execute("INSERT INTO users(username,full_name,pw_hash,role) VALUES (?,?,?,?)",
              ("staff", "Store Staff", hash_pw("Staff@123"), "staff"))
    c.close()


# ---------------------------------------------------------------- helpers
TPL = os.path.join(BASE, "templates")


def render(_tpl, /, **ctx):
    """Load templates/<name>.html and fill {{placeholders}} (values are pre-escaped HTML)."""
    with open(os.path.join(TPL, _tpl + ".html"), encoding="utf-8") as fh:
        src = fh.read()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx.get(m.group(1), "")), src)


def options(opts, cur=None, blank=None):
    o = f'<option value="">{blank}</option>' if blank else ""
    return o + "".join(f'<option value="{v}" {"selected" if str(v) == str(cur) else ""}>{e(t)}</option>' for v, t in opts)


e = lambda s: html.escape("" if s is None else str(s), quote=True)
money = lambda v: f"{CUR}{(v or 0):,.2f}"
now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Req:
    def __init__(self, h, method):
        u = urlparse(h.path)
        self.h, self.method, self.path = h, method, u.path
        self.query = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.form = {}
        if method == "POST":
            n = int(h.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                raise ValueError("Request too large")
            self.form = {k: v[0] for k, v in parse_qs(h.rfile.read(n).decode("utf-8", "replace"),
                                                       keep_blank_values=True).items()}
        self.sid = None
        ck = h.headers.get("Cookie", "")
        m = re.search(r"sid=([A-Za-z0-9_\-]+)", ck)
        self.user = self.csrf = None
        if m:
            r = one("SELECT u.*, s.csrf, s.token FROM sessions s JOIN users u ON u.id=s.user_id "
                    "WHERE s.token=? AND u.active=1", (m.group(1),))
            if r:
                self.user, self.csrf, self.sid = r, r["csrf"], r["token"]

    def f(self, k, d=""):
        return self.form.get(k, d).strip()

    @property
    def admin(self):
        return self.user and self.user["role"] == "admin"


def flash(req, msg, kind="ok"):
    if req.sid:
        run("UPDATE sessions SET flash=? WHERE token=?", (f"{kind}|{msg}", req.sid))


def redirect(loc, cookie=None):
    h = [("Location", loc)]
    if cookie:
        h.append(("Set-Cookie", cookie))
    return 303, h, b""


def page(req, title, body, active=""):
    nav = [("/", "Dashboard"), ("/products", "Products"), ("/sales", "Sales"),
           ("/purchases", "Purchases"), ("/customers", "Customers"),
           ("/suppliers", "Suppliers"), ("/categories", "Categories")]
    if req.admin:
        nav += [("/reports", "Reports"), ("/users", "Users")]
    links = "".join(f'<a href="{p}" class="{"on" if p == active else ""}">{n}</a>' for p, n in nav)
    fl = ""
    if req.sid:
        r = one("SELECT flash FROM sessions WHERE token=?", (req.sid,))
        if r and r["flash"]:
            k, m = r["flash"].split("|", 1)
            fl = f'<div class="flash {"ok" if k == "ok" else "err"}">{e(m)}</div>'
            run("UPDATE sessions SET flash=NULL WHERE token=?", (req.sid,))
    side = render("sidebar", links=links, fullname=e(req.user["full_name"]), role=req.user["role"], tok=tok(req))
    return html_resp(render("layout", title=e(title), side=side, flash=fl, body=body))


def html_resp(s, status=200):
    return status, [("Content-Type", "text/html; charset=utf-8")], s.encode()


tok = lambda req: f'<input type="hidden" name="csrf" value="{e(req.csrf)}">'


def fld(name, label, val="", typ="text", req=False, extra=""):
    return (f'<label>{label}<input name="{name}" type="{typ}" value="{e(val)}" '
            f'{"required" if req else ""} {extra}></label>')


def sel(name, label, opts, cur=None, blank="-- none --", req=False):
    o = f'<option value="">{blank}</option>' if blank else ""
    o += "".join(f'<option value="{v}" {"selected" if str(v) == str(cur) else ""}>{e(t)}</option>' for v, t in opts)
    return f'<label>{label}<select name="{name}" {"required" if req else ""}>{o}</select></label>'


def table(heads, body, nums=()):
    th = "".join(f'<th class="{"n" if i in nums else ""}">{h}</th>' for i, h in enumerate(heads))
    tr = "".join("<tr>" + "".join(f'<td class="{"n" if i in nums else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                 for r in body) or f'<tr><td colspan="{len(heads)}" class="mut">No records found.</td></tr>'
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def post_btn(req, action, label, cls="btn sm sec", confirm=""):
    return (f'<form class="inline" method="post" action="{action}">{tok(req)}'
            f'<button class="{cls}">{label}</button></form>')


def stock_tag(p):
    if p["qty"] == 0:
        return '<span class="tag out">Out of stock</span>'
    if p["qty"] <= p["reorder_level"]:
        return '<span class="tag low">Low</span>'
    return '<span class="tag ok">OK</span>'


# ---------------------------------------------------------------- routing
ROUTES = []


def route(method, pattern, admin=False, public=False):
    def deco(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn, admin, public))
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    server_version = "SmartStock/1.0"

    def log_message(self, *a):
        pass

    def _dispatch(self, method):
        try:
            if method == "GET" and self.path.startswith("/static/"):
                return self._static()
            req = Req(self, method)
            for m, rx, fn, adm, pub in ROUTES:
                mt = rx.match(req.path)
                if m == method and mt:
                    if not pub and not req.user:
                        return self._send(*redirect("/login"))
                    if adm and not req.admin:
                        flash(req, "Administrator access required.", "err")
                        return self._send(*redirect("/"))
                    if method == "POST" and not pub and not hmac.compare_digest(req.f("csrf"), req.csrf or "x"):
                        return self._send(*html_resp("Invalid CSRF token", 403))
                    return self._send(*fn(req, *mt.groups()))
            self._send(*html_resp("<h1>404 Not found</h1>", 404))
        except Exception as ex:  # last-resort handler: never leak a traceback to the browser
            print("ERROR:", repr(ex))
            self._send(*html_resp("<h1>Something went wrong</h1><a href='/'>Home</a>", 500))

    def _static(self):
        name = os.path.basename(urlparse(self.path).path)
        fp = os.path.join(BASE, "static", name)
        if not os.path.isfile(fp):
            return self._send(*html_resp("Not found", 404))
        with open(fp, "rb") as fh:
            self._send(200, [("Content-Type", "text/css"), ("Cache-Control", "max-age=300")], fh.read())

    def _send(self, status, headers, body):
        self.send_response(status)
        for k, v in headers + [("X-Frame-Options", "DENY"), ("X-Content-Type-Options", "nosniff"),
                               ("Content-Security-Policy", "default-src 'self'; style-src 'self'")]:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


# ---------------------------------------------------------------- auth
@route("GET", "/login", public=True)
def login_form(req, err=""):
    msg = f'<div class="flash err">{e(err)}</div>' if err else ""
    return html_resp(render("login", msg=msg))


@route("POST", "/login", public=True)
def login(req):
    ip = req.h.client_address[0]
    FAILS[ip] = [t for t in FAILS.get(ip, []) if time.time() - t < 300]
    if len(FAILS[ip]) >= 5:
        return login_form(req, "Too many attempts. Try again in 5 minutes.")
    u = one("SELECT * FROM users WHERE username=? AND active=1", (req.f("username"),))
    if not u or not check_pw(req.form.get("password", ""), u["pw_hash"]):
        FAILS[ip].append(time.time())
        return login_form(req, "Invalid username or password.")
    token = secrets.token_urlsafe(32)
    run("INSERT INTO sessions(token,user_id,csrf) VALUES (?,?,?)", (token, u["id"], secrets.token_urlsafe(24)))
    return redirect("/", f"sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")


@route("POST", "/logout")
def logout(req):
    run("DELETE FROM sessions WHERE token=?", (req.sid,))
    return redirect("/login", "sid=; Max-Age=0; Path=/")


@route("GET", "/account")
def account(req):
    return page(req, "My account", render("account", tok=tok(req)))


@route("POST", "/account")
def account_save(req):
    if not check_pw(req.form.get("old", ""), req.user["pw_hash"]):
        flash(req, "Current password is incorrect.", "err")
    elif len(req.form.get("new", "")) < 8:
        flash(req, "New password must be at least 8 characters.", "err")
    else:
        run("UPDATE users SET pw_hash=? WHERE id=?", (hash_pw(req.form["new"]), req.user["id"]))
        flash(req, "Password updated.")
    return redirect("/account")


# ---------------------------------------------------------------- dashboard
@route("GET", "/")
def dashboard(req):
    today = datetime.now().strftime("%Y-%m-%d")
    month = today[:7]
    k = one("SELECT (SELECT COALESCE(SUM(total),0) FROM sales WHERE date(created)=?) t,"
            "(SELECT COALESCE(SUM(total),0) FROM sales WHERE strftime('%Y-%m',created)=?) m,"
            "(SELECT COUNT(*) FROM products WHERE active=1) p,"
            "(SELECT COUNT(*) FROM low_stock) l,"
            "(SELECT COALESCE(SUM(qty*cost),0) FROM products WHERE active=1) v", (today, month))
    kp = "".join(f'<div class="kpi"><span>{a}</span><b>{b}</b></div>' for a, b in [
        ("Today's sales", money(k["t"])), ("This month", money(k["m"])), ("Active products", k["p"]),
        ("Low-stock items", k["l"]), ("Stock value (cost)", money(k["v"]))])
    days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    tot = {r["d"]: r["t"] for r in rows("SELECT date(created) d, SUM(total) t FROM sales "
                                        "WHERE date(created)>=? GROUP BY d", (days[0],))}
    mx = max(tot.values(), default=0) or 1
    chart = "".join(f'<div class="row"><span class="l">{d[5:]}</span><div class="bar" style="width:{int(tot.get(d, 0) / mx * 70)}%"></div>'
                    f'<span>{money(tot.get(d, 0))}</span></div>' for d in days)
    low = table(["Product", "Qty", "Reorder"], [[e(p["name"]), p["qty"], p["reorder_level"]] for p in
                rows("SELECT * FROM low_stock ORDER BY qty LIMIT 8")], (1, 2))
    rec = table(["Invoice", "Customer", "Total"], [
        [f'<a href="/sales/{s["id"]}">INV-{s["id"]:05d}</a>', e(s["cn"] or "Walk-in"), money(s["total"])] for s in
        rows("SELECT s.id,s.total,c.name cn FROM sales s LEFT JOIN customers c ON c.id=s.customer_id "
             "ORDER BY s.id DESC LIMIT 6")], (2,))
    return page(req, "Dashboard", render("dashboard", kpis=kp, chart=chart, low=low, recent=rec), "/")


# ---------------------------------------------------------------- products
def num(v, cast=float, lo=0):
    x = cast(v)
    if x < lo:
        raise ValueError
    return x


def product_form(req, p=None):
    new = p is None
    cats = [(r["id"], r["name"]) for r in rows("SELECT * FROM categories ORDER BY name")]
    sups = [(r["id"], r["name"]) for r in rows("SELECT * FROM suppliers ORDER BY name")]
    g = lambda k, d="": e(p[k]) if not new and p[k] is not None else d
    return render("product_form", tok=tok(req), action="/products/new" if new else f'/products/{p["id"]}/edit',
                  sku=g("sku"), name=g("name"), cost=g("cost", 0), price=g("price", 0), reorder=g("reorder_level", 5),
                  categories=options(cats, g("category_id"), "-- none --"), suppliers=options(sups, g("supplier_id"), "-- none --"),
                  qty_field=render("qty_field") if new else "")


@route("GET", "/products")
def products(req):
    q = req.query.get("q", "")
    low = req.query.get("low")
    sql = ("SELECT p.*, c.name cat FROM products p LEFT JOIN categories c ON c.id=p.category_id "
           "WHERE p.active=1 AND (p.name LIKE ? OR p.sku LIKE ?)")
    if low:
        sql += " AND p.qty<=p.reorder_level"
    data = rows(sql + " ORDER BY p.name", (f"%{q}%", f"%{q}%"))
    body = []
    for p in data:
        act = f'<a class="btn sm sec" href="/products/{p["id"]}">Open</a> <a class="btn sm sec" href="/products/{p["id"]}/edit">Edit</a>'
        if req.admin:
            act += " " + post_btn(req, f'/products/{p["id"]}/delete', "Delete", "btn sm red")
        body.append([e(p["sku"]), e(p["name"]), e(p["cat"] or "-"), money(p["cost"]), money(p["price"]),
                     p["qty"], stock_tag(p), act])
    tbl = table(["SKU", "Name", "Category", "Cost", "Price", "Qty", "Status", ""], body, (3, 4, 5))
    return page(req, "Products", render("products", q=e(q), table=tbl), "/products")


@route("GET", "/products/new")
def product_new(req):
    return page(req, "New product", product_form(req), "/products")


def save_product(req, pid=None):
    try:
        v = (req.f("sku"), req.f("name"), req.f("category_id") or None, req.f("supplier_id") or None,
             num(req.f("cost")), num(req.f("price")), num(req.f("reorder_level"), int))
        if not v[0] or not v[1]:
            raise ValueError
        if pid:
            run("UPDATE products SET sku=?,name=?,category_id=?,supplier_id=?,cost=?,price=?,reorder_level=? WHERE id=?",
                v + (pid,))
        else:
            q = num(req.f("qty", "0"), int)
            pid = run("INSERT INTO products(sku,name,category_id,supplier_id,cost,price,reorder_level,qty) "
                      "VALUES (?,?,?,?,?,?,?,?)", v + (q,))
            if q:
                run("INSERT INTO stock_movements(product_id,change,reason,user_id,created) VALUES (?,?,?,?,?)",
                    (pid, q, "Opening stock", req.user["id"], now()))
        flash(req, "Product saved.")
        return redirect("/products")
    except sqlite3.IntegrityError:
        flash(req, "SKU already exists or invalid reference.", "err")
    except ValueError:
        flash(req, "Please enter valid values (no negatives, required fields filled).", "err")
    return redirect(req.path)


@route("POST", "/products/new")
def product_create(req):
    return save_product(req)


@route("GET", r"/products/(\d+)/edit")
def product_edit(req, pid):
    p = one("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    return page(req, "Edit product", product_form(req, p), "/products") if p else redirect("/products")


@route("POST", r"/products/(\d+)/edit")
def product_update(req, pid):
    return save_product(req, int(pid))


@route("POST", r"/products/(\d+)/delete", admin=True)
def product_delete(req, pid):
    run("UPDATE products SET active=0 WHERE id=?", (pid,))  # soft delete keeps sales history intact
    flash(req, "Product removed (history preserved).")
    return redirect("/products")


@route("GET", r"/products/(\d+)")
def product_view(req, pid):
    p = one("SELECT p.*, c.name cat, s.name sup FROM products p LEFT JOIN categories c ON c.id=p.category_id "
            "LEFT JOIN suppliers s ON s.id=p.supplier_id WHERE p.id=?", (pid,))
    if not p:
        return redirect("/products")
    mv = table(["Date", "Change", "Reason"], [[e(m["created"]), f'{m["change"]:+d}', e(m["reason"])] for m in
               rows("SELECT * FROM stock_movements WHERE product_id=? ORDER BY id DESC LIMIT 30", (pid,))], (1,))
    return page(req, "Product details", render("product_detail", tok=tok(req), pid=pid, name=e(p["name"]), sku=e(p["sku"]),
                category=e(p["cat"] or "-"), supplier=e(p["sup"] or "-"), qty=p["qty"], status=stock_tag(p),
                cost=money(p["cost"]), price=money(p["price"]), history=mv), "/products")


@route("POST", r"/products/(\d+)/adjust")
def product_adjust(req, pid):
    try:
        ch = int(req.f("change"))
        reason = req.f("reason")
        c = connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            p = c.execute("SELECT qty FROM products WHERE id=?", (pid,)).fetchone()
            if ch == 0 or not reason or not p or p["qty"] + ch < 0:
                raise ValueError
            c.execute("UPDATE products SET qty=qty+? WHERE id=?", (ch, pid))
            c.execute("INSERT INTO stock_movements(product_id,change,reason,user_id,created) VALUES (?,?,?,?,?)",
                      (pid, ch, "Adjustment: " + reason, req.user["id"], now()))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()
        flash(req, "Stock adjusted.")
    except ValueError:
        flash(req, "Invalid adjustment (stock cannot go below zero).", "err")
    return redirect(f"/products/{pid}")


@route("GET", "/export/products.csv")
def export_products(req):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SKU", "Name", "Category", "Cost", "Price", "Qty", "Reorder level"])
    for p in rows("SELECT p.*, c.name cat FROM products p LEFT JOIN categories c ON c.id=p.category_id "
                  "WHERE p.active=1 ORDER BY p.name"):
        w.writerow([p["sku"], p["name"], p["cat"], p["cost"], p["price"], p["qty"], p["reorder_level"]])
    return 200, [("Content-Type", "text/csv"), ("Content-Disposition", "attachment; filename=products.csv")], buf.getvalue().encode()


# ---------------------------------------------------------------- simple master data (categories/suppliers/customers)
ENT = {"categories": ("Category", [("name", "Name", True)]),
       "suppliers": ("Supplier", [("name", "Name", True), ("phone", "Phone", False), ("email", "Email", False), ("address", "Address", False)]),
       "customers": ("Customer", [("name", "Name", True), ("phone", "Phone", False), ("email", "Email", False), ("address", "Address", False)])}


def ent_routes(tbl, label, cols):
    @route("GET", f"/{tbl}")
    def lst(req):
        edit = one(f"SELECT * FROM {tbl} WHERE id=?", (req.query["edit"],)) if req.query.get("edit", "").isdigit() else None
        fields = "".join(fld(c, l, edit[c] if edit else "", req=r) for c, l, r in cols)
        action = f"/{tbl}/{edit['id']}/edit" if edit else f"/{tbl}/new"
        body = []
        for r in rows(f"SELECT * FROM {tbl} ORDER BY name"):
            act = f'<a class="btn sm sec" href="/{tbl}?edit={r["id"]}">Edit</a>'
            if req.admin:
                act += " " + post_btn(req, f'/{tbl}/{r["id"]}/delete', "Delete", "btn sm red")
            body.append([e(r[c]) for c, _, _ in cols] + [act])
        tbl_html = table([l for _, l, _ in cols] + [""], body)
        return page(req, "Categories" if label == "Category" else label + "s",
                    render("entity", heading=("Edit " if edit else "Add ") + label.lower(), action=action, tok=tok(req),
                           fields=fields, table=tbl_html), f"/{tbl}")

    @route("POST", f"/{tbl}/new")
    def add(req):
        vals = [req.f(c) for c, _, _ in cols]
        if not vals[0]:
            flash(req, "Name is required.", "err")
        else:
            try:
                run(f"INSERT INTO {tbl}({','.join(c for c, _, _ in cols)}) VALUES ({','.join('?' * len(cols))})", vals)
                flash(req, f"{label} added.")
            except sqlite3.IntegrityError:
                flash(req, f"{label} already exists.", "err")
        return redirect(f"/{tbl}")

    @route("POST", rf"/{tbl}/(\d+)/edit")
    def upd(req, i):
        vals = [req.f(c) for c, _, _ in cols]
        if vals[0]:
            try:
                run(f"UPDATE {tbl} SET {','.join(c + '=?' for c, _, _ in cols)} WHERE id=?", vals + [i])
                flash(req, f"{label} updated.")
            except sqlite3.IntegrityError:
                flash(req, "Name already exists.", "err")
        return redirect(f"/{tbl}")

    @route("POST", rf"/{tbl}/(\d+)/delete", admin=True)
    def dele(req, i):
        run(f"DELETE FROM {tbl} WHERE id=?", (i,))
        flash(req, f"{label} deleted.")
        return redirect(f"/{tbl}")


for _t, (_l, _c) in ENT.items():
    ent_routes(_t, _l, _c)


# ---------------------------------------------------------------- line-item forms
def item_rows(prods, costmode):
    opts = lambda: "".join(f'<option value="{p["id"]}">{e(p["name"])} (stock {p["qty"]}, {money(p["cost"] if costmode else p["price"])})</option>' for p in prods)
    out = ""
    for i in range(1, ROWS + 1):
        extra = f'<td><input name="cost_{i}" type="number" step="0.01" min="0" placeholder="unit cost"></td>' if costmode else ""
        out += (f'<tr><td><select name="product_{i}"><option value="">-- select product --</option>{opts()}</select></td>'
                f'<td><input name="qty_{i}" type="number" min="1" placeholder="qty"></td>{extra}</tr>')
    return out


def parse_items(req, costmode):
    items = {}
    for i in range(1, ROWS + 1):
        pid, q = req.f(f"product_{i}"), req.f(f"qty_{i}")
        if pid or q:
            pid, q = int(pid), int(q)
            if q <= 0:
                raise ValueError("Quantity must be positive.")
            cost = float(req.f(f"cost_{i}") or -1) if costmode else None
            if costmode and cost < 0:
                cost = None
            prev = items.get(pid, (0, cost))
            items[pid] = (prev[0] + q, cost if cost is not None else prev[1])
    if not items:
        raise ValueError("Add at least one item.")
    return items


# ---------------------------------------------------------------- sales
@route("GET", "/sales")
def sales(req):
    data = rows("SELECT s.*, c.name cn, u.full_name un FROM sales s LEFT JOIN customers c ON c.id=s.customer_id "
                "LEFT JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 200")
    body = [[f'INV-{s["id"]:05d}', e(s["created"]), e(s["cn"] or "Walk-in"), e(s["un"] or "-"), money(s["total"]),
             f'<a class="btn sm sec" href="/sales/{s["id"]}">Invoice</a>'] for s in data]
    return page(req, "Sales", '<p><a class="btn" href="/sales/new">+ New sale</a></p><div class="card">' +
                table(["Invoice", "Date", "Customer", "Cashier", "Total", ""], body, (4,)) + "</div>", "/sales")


@route("GET", "/sales/new")
def sale_new(req):
    prods = rows("SELECT * FROM products WHERE active=1 AND qty>0 ORDER BY name")
    cust = [(c["id"], c["name"]) for c in rows("SELECT * FROM customers ORDER BY name")]
    return page(req, "New sale", render("sale_new", tok=tok(req), customers=options(cust, None, "Walk-in"),
                rows=item_rows(prods, False)), "/sales")


@route("POST", "/sales/new")
def sale_create(req):
    c = connect()
    try:
        items = parse_items(req, False)
        disc = num(req.f("discount", "0") or "0")
        c.execute("BEGIN IMMEDIATE")
        lines, sub = [], 0.0
        for pid, (q, _) in items.items():
            p = c.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
            if not p:
                raise ValueError("Product not found.")
            if p["qty"] < q:
                raise ValueError(f'Insufficient stock for {p["name"]} (available {p["qty"]}).')
            lines.append((p, q))
            sub += p["price"] * q
        if disc > sub:
            raise ValueError("Discount cannot exceed subtotal.")
        sid = c.execute("INSERT INTO sales(customer_id,subtotal,discount,total,user_id,created) VALUES (?,?,?,?,?,?)",
                        (req.f("customer_id") or None, sub, disc, sub - disc, req.user["id"], now())).lastrowid
        for p, q in lines:
            c.execute("INSERT INTO sale_items(sale_id,product_id,qty,price,cost) VALUES (?,?,?,?,?)",
                      (sid, p["id"], q, p["price"], p["cost"]))
            c.execute("UPDATE products SET qty=qty-? WHERE id=?", (q, p["id"]))
            c.execute("INSERT INTO stock_movements(product_id,change,reason,user_id,created) VALUES (?,?,?,?,?)",
                      (p["id"], -q, f"Sale INV-{sid:05d}", req.user["id"], now()))
        c.execute("COMMIT")
        flash(req, "Sale completed.")
        return redirect(f"/sales/{sid}")
    except (ValueError, sqlite3.Error) as ex:
        if c.in_transaction:
            c.execute("ROLLBACK")
        flash(req, str(ex) if isinstance(ex, ValueError) and "invalid literal" not in str(ex) else "Please check the items and quantities.", "err")
        return redirect("/sales/new")
    finally:
        c.close()


@route("GET", r"/sales/(\d+)")
def invoice(req, sid):
    s = one("SELECT s.*, c.name cn, c.phone, c.address FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?", (sid,))
    if not s:
        return redirect("/sales")
    it = rows("SELECT si.*, p.name FROM sale_items si JOIN products p ON p.id=si.product_id WHERE sale_id=?", (sid,))
    t = table(["Item", "Qty", "Price", "Amount"], [[e(i["name"]), i["qty"], money(i["price"]), money(i["qty"] * i["price"])] for i in it], (1, 2, 3))
    return page(req, f"Invoice INV-{s['id']:05d}", render("invoice", date=e(s["created"]), customer=e(s["cn"] or "Walk-in"),
                phone=e(s["phone"] or ""), items=t, subtotal=money(s["subtotal"]), discount=money(s["discount"]),
                total=money(s["total"])), "/sales")


# ---------------------------------------------------------------- purchases (stock in)
@route("GET", "/purchases")
def purchases(req):
    data = rows("SELECT p.*, s.name sn FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id DESC LIMIT 200")
    body = [[f'PO-{p["id"]:05d}', e(p["created"]), e(p["sn"] or "-"), money(p["total"])] for p in data]
    return page(req, "Purchases", '<p><a class="btn" href="/purchases/new">+ Receive stock</a></p><div class="card">' +
                table(["Ref", "Date", "Supplier", "Total"], body, (3,)) + "</div>", "/purchases")


@route("GET", "/purchases/new")
def purchase_new(req):
    prods = rows("SELECT * FROM products WHERE active=1 ORDER BY name")
    sups = [(s["id"], s["name"]) for s in rows("SELECT * FROM suppliers ORDER BY name")]
    return page(req, "Receive stock", render("purchase_new", tok=tok(req), suppliers=options(sups, None, "-- select --"),
                rows=item_rows(prods, True)), "/purchases")


@route("POST", "/purchases/new")
def purchase_create(req):
    c = connect()
    try:
        items = parse_items(req, True)
        if not req.f("supplier_id"):
            raise ValueError("Select a supplier.")
        c.execute("BEGIN IMMEDIATE")
        lines, total = [], 0.0
        for pid, (q, cost) in items.items():
            p = c.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
            if not p:
                raise ValueError("Product not found.")
            cost = p["cost"] if cost is None else cost
            lines.append((p, q, cost))
            total += q * cost
        pid_ = c.execute("INSERT INTO purchases(supplier_id,total,user_id,created) VALUES (?,?,?,?)",
                         (req.f("supplier_id"), total, req.user["id"], now())).lastrowid
        for p, q, cost in lines:
            c.execute("INSERT INTO purchase_items(purchase_id,product_id,qty,cost) VALUES (?,?,?,?)", (pid_, p["id"], q, cost))
            c.execute("UPDATE products SET qty=qty+?, cost=? WHERE id=?", (q, cost, p["id"]))
            c.execute("INSERT INTO stock_movements(product_id,change,reason,user_id,created) VALUES (?,?,?,?,?)",
                      (p["id"], q, f"Purchase PO-{pid_:05d}", req.user["id"], now()))
        c.execute("COMMIT")
        flash(req, "Stock received.")
        return redirect("/purchases")
    except (ValueError, sqlite3.Error) as ex:
        if c.in_transaction:
            c.execute("ROLLBACK")
        flash(req, "Please check the items, quantities and costs." if "invalid literal" in str(ex) or not isinstance(ex, ValueError) else str(ex), "err")
        return redirect("/purchases/new")
    finally:
        c.close()


# ---------------------------------------------------------------- reports (admin)
@route("GET", "/reports", admin=True)
def reports(req):
    d1 = req.query.get("from", datetime.now().strftime("%Y-%m-01"))
    d2 = req.query.get("to", datetime.now().strftime("%Y-%m-%d"))
    s = one("SELECT COUNT(*) n, COALESCE(SUM(total),0) rev, COALESCE(SUM(discount),0) disc FROM sales WHERE date(created) BETWEEN ? AND ?", (d1, d2))
    cogs = one("SELECT COALESCE(SUM(si.qty*si.cost),0) c FROM sale_items si JOIN sales s ON s.id=si.sale_id "
               "WHERE date(s.created) BETWEEN ? AND ?", (d1, d2))["c"]
    pur = one("SELECT COALESCE(SUM(total),0) t FROM purchases WHERE date(created) BETWEEN ? AND ?", (d1, d2))["t"]
    kp = "".join(f'<div class="kpi"><span>{a}</span><b>{b}</b></div>' for a, b in [
        ("Invoices", s["n"]), ("Revenue", money(s["rev"])), ("Cost of goods", money(cogs)),
        ("Gross profit", money(s["rev"] - cogs)), ("Purchases", money(pur))])
    top = table(["Product", "Units", "Revenue", "Profit"], [[e(r["name"]), r["u"], money(r["rev"]), money(r["pr"])] for r in rows(
        "SELECT p.name, SUM(si.qty) u, SUM(si.qty*si.price) rev, SUM(si.qty*(si.price-si.cost)) pr FROM sale_items si "
        "JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id WHERE date(s.created) BETWEEN ? AND ? "
        "GROUP BY p.id ORDER BY u DESC LIMIT 10", (d1, d2))], (1, 2, 3))
    cat = table(["Category", "Revenue"], [[e(r["n"] or "Uncategorised"), money(r["rev"])] for r in rows(
        "SELECT c.name n, SUM(si.qty*si.price) rev FROM sale_items si JOIN sales s ON s.id=si.sale_id "
        "JOIN products p ON p.id=si.product_id LEFT JOIN categories c ON c.id=p.category_id "
        "WHERE date(s.created) BETWEEN ? AND ? GROUP BY c.id ORDER BY rev DESC", (d1, d2))], (1,))
    return page(req, "Reports", render("reports", d1=e(d1), d2=e(d2), kpis=kp, top=top, cat=cat), "/reports")


# ---------------------------------------------------------------- user management (admin)
@route("GET", "/users", admin=True)
def users(req):
    body = []
    for u in rows("SELECT * FROM users ORDER BY id"):
        act = "" if u["id"] == req.user["id"] else post_btn(req, f'/users/{u["id"]}/toggle', "Deactivate" if u["active"] else "Activate")
        body.append([e(u["username"]), e(u["full_name"]), u["role"], "Active" if u["active"] else "Disabled", act])
    return page(req, "Users", render("users", tok=tok(req), table=table(["Username", "Name", "Role", "Status", ""], body)), "/users")


@route("POST", "/users/new", admin=True)
def user_create(req):
    if len(req.form.get("password", "")) < 8 or not req.f("username") or req.f("role") not in ("admin", "staff"):
        flash(req, "Provide username, valid role and a password of at least 8 characters.", "err")
    else:
        try:
            run("INSERT INTO users(username,full_name,pw_hash,role) VALUES (?,?,?,?)",
                (req.f("username"), req.f("full_name"), hash_pw(req.form["password"]), req.f("role")))
            flash(req, "User created.")
        except sqlite3.IntegrityError:
            flash(req, "Username already taken.", "err")
    return redirect("/users")


@route("POST", r"/users/(\d+)/toggle", admin=True)
def user_toggle(req, uid):
    if int(uid) != req.user["id"]:
        run("UPDATE users SET active=1-active WHERE id=?", (uid,))
        run("DELETE FROM sessions WHERE user_id=?", (uid,))
    return redirect("/users")


# ---------------------------------------------------------------- main
def make_server(host="127.0.0.1", port=8000):
    init_db()
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    srv = make_server(port=port)
    print(f"SmartStock running at http://127.0.0.1:{port}  (admin / Admin@123)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
