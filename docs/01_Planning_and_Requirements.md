# 1. Planning & Requirements Analysis (SDLC Phase 1)

## 1.1 Problem statement
Small retailers track stock, sales and purchases on paper or spreadsheets, causing stock-outs, billing errors and no profit visibility. SmartStock centralises these in one web application.

## 1.2 Objectives
Real-time stock tracking, fast invoicing, supplier purchasing, profit reporting, role-based security.

## 1.3 Scope
In scope: auth, products, categories, suppliers, customers, sales, purchases, stock movements, reports, users.
Out of scope: payment gateways, tax/GST filing, multi-store, barcode hardware.

## 1.4 Stakeholders / actors
Admin (owner/manager) - full access. Staff (cashier/store keeper) - sales, purchases, products, masters (no deletes, reports, users).

## 1.5 Feasibility
Technical: stdlib Python + SQLite, zero dependencies. Economic: free stack. Operational: runs on any PC. Schedule: one iteration.

## 1.6 Functional requirements
| ID | Requirement |
|----|-------------|
| FR1 | Users log in/out; passwords hashed; admin and staff roles |
| FR2 | Manage products (SKU unique, cost, price, reorder level); soft delete |
| FR3 | Manage categories, suppliers, customers |
| FR4 | Create sale with multiple items; reject if stock insufficient; deduct stock atomically |
| FR5 | Receive purchase; increase stock; update cost |
| FR6 | Manual stock adjustment with reason; movement history per product |
| FR7 | Dashboard KPIs and low-stock alerts |
| FR8 | Reports: revenue, COGS, profit, top products, category revenue by date range |
| FR9 | Export products to CSV |
| FR10 | Admin manages users (create, activate/deactivate) |

## 1.7 Non-functional requirements
Security (OWASP: injection, CSRF, XSS, session), integrity (CHECK constraints, transactions), usability (responsive, printable invoice), portability, maintainability, performance (indexes; <200 ms typical page).

## 1.8 Risks
Concurrent sales of last unit -> `BEGIN IMMEDIATE` transactions. Data loss -> single-file DB backup (see maintenance doc). Weak passwords -> min length rule.
