INSERT INTO categories(name) VALUES ('Electronics'),('Stationery'),('Groceries'),('Accessories');
INSERT INTO suppliers(name,phone,email,address) VALUES
 ('TechSource Pvt Ltd','9800000001','sales@techsource.example','Bengaluru'),
 ('OfficeMart','9800000002','hello@officemart.example','Mysuru'),
 ('FreshTrade Co','9800000003','orders@freshtrade.example','Mangaluru');
INSERT INTO customers(name,phone,email,address) VALUES
 ('Walk-in Customer','','',''),('Asha Rao','9811111111','asha@example.com','Bengaluru'),
 ('Ravi Kumar','9822222222','ravi@example.com','Hubballi');
INSERT INTO products(sku,name,category_id,supplier_id,cost,price,qty,reorder_level) VALUES
 ('EL-001','USB-C Cable 1m',1,1,120,249,40,10),
 ('EL-002','Wireless Mouse',1,1,350,699,18,8),
 ('EL-003','Bluetooth Speaker',1,1,900,1599,6,6),
 ('ST-001','A4 Notebook 200pg',2,2,45,90,60,20),
 ('ST-002','Gel Pen (Blue)',2,2,6,15,150,40),
 ('GR-001','Basmati Rice 5kg',3,3,380,520,25,10),
 ('GR-002','Olive Oil 1L',3,3,520,749,4,8),
 ('AC-001','Laptop Sleeve 15"',4,1,260,549,12,5);
INSERT INTO stock_movements(product_id,change,reason)
 SELECT id, qty, 'Opening stock' FROM products;
INSERT INTO sales(customer_id,subtotal,discount,total,created) VALUES
 (2, 948,0,948, datetime('now','localtime','-6 day')),
 (3,1599,100,1499, datetime('now','localtime','-4 day')),
 (1, 540,0,540, datetime('now','localtime','-2 day')),
 (2,1398,0,1398, datetime('now','localtime','-1 day')),
 (1, 520,0,520, datetime('now','localtime'));
INSERT INTO sale_items(sale_id,product_id,qty,price,cost) VALUES
 (1,1,2,249,120),(1,2,1,699,350),(2,3,1,1599,900),
 (3,4,6,90,45),(4,2,2,699,350),(5,6,1,520,380);
