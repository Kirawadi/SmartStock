# 4. Testing (SDLC Phase 4)

Automated: `python tests/test_smartstock.py` (end-to-end over real HTTP, temp database).
Covered: login failure/success, product create, sale (stock decrement, discount total), oversell rejection with rollback, purchase increases stock, reports, CSV export, search, unauthenticated redirect.

## Manual test cases
| ID | Steps | Expected |
|----|-------|----------|
| TC1 | Login with wrong password 5x | Locked for 5 min |
| TC2 | Staff opens /reports or /users | Redirected, error message |
| TC3 | Create product with duplicate SKU | Error, no duplicate |
| TC4 | Sell more than available | "Insufficient stock", nothing saved |
| TC5 | Discount greater than subtotal | Rejected |
| TC6 | Adjust stock below zero | Rejected |
| TC7 | POST without CSRF token | 403 |
| TC8 | Delete product with past sales | Hidden, history/invoices intact |
| TC9 | Receive purchase | Qty up, cost updated, movement logged |
| TC10 | Reports date filter | Figures match invoices in range |
