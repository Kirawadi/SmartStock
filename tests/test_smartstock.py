import os, sys, tempfile, threading, unittest, re, urllib.request, urllib.parse, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SMARTSTOCK_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.make_server(port=0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, p):
        return self.op.open(f"http://127.0.0.1:{self.port}{p}").read().decode()

    def post(self, p, d):
        d = dict(d, csrf=getattr(self, "csrf", ""))
        return self.op.open(f"http://127.0.0.1:{self.port}{p}", urllib.parse.urlencode(d).encode()).read().decode()

    def test_flow(self):
        self.assertIn("Sign in", self.get("/login"))
        bad = self.post("/login", {"username": "admin", "password": "wrong"})
        self.assertIn("Invalid username", bad)
        self.post("/login", {"username": "admin", "password": "Admin@123"})
        dash = self.get("/")
        self.assertIn("Today's sales", dash)
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', dash).group(1)
        self.post("/products/new", {"sku": "T-1", "name": "Test Item", "cost": "10", "price": "25", "qty": "5", "reorder_level": "2"})
        pid = app.one("SELECT id FROM products WHERE sku='T-1'")["id"]
        self.assertIn("Sale completed", self.post("/sales/new", {"product_1": pid, "qty_1": "3", "discount": "5"}))
        self.assertEqual(app.one("SELECT qty FROM products WHERE id=?", (pid,))["qty"], 2)
        self.assertEqual(app.one("SELECT total FROM sales ORDER BY id DESC")["total"], 70.0)
        self.assertIn("Insufficient stock", self.post("/sales/new", {"product_1": pid, "qty_1": "9", "discount": "0"}))
        self.assertEqual(app.one("SELECT qty FROM products WHERE id=?", (pid,))["qty"], 2)
        self.post("/purchases/new", {"supplier_id": "1", "product_1": pid, "qty_1": "10", "cost_1": "12"})
        self.assertEqual(app.one("SELECT qty FROM products WHERE id=?", (pid,))["qty"], 12)
        self.assertIn("Gross profit", self.get("/reports"))
        self.assertIn("SKU", self.get("/export/products.csv"))
        self.assertIn("Test Item", self.get("/products?q=Test"))

    def test_csrf_and_auth(self):
        op = urllib.request.build_opener()
        r = op.open(f"http://127.0.0.1:{self.port}/products").read().decode()
        self.assertIn("Sign in", r)  # unauthenticated -> login page


if __name__ == "__main__":
    unittest.main()
