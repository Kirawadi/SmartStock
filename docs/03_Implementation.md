# 3. Implementation (SDLC Phase 3)

| Concern | File |
|---------|------|
| Schema, constraints, view | `database/schema.sql` |
| Demo data | `database/seed.sql` |
| HTML pages (`{{placeholder}}` templates) | `templates/*.html` |
| Server, routing, auth, modules, reports | `app.py` |
| Styling | `static/style.css` |

Coding standards: parameterised SQL only, escape on output, small route functions, transactions for multi-table writes, soft delete for products, input validation on every POST.
Route map: `/login /logout /account /` `/products[/new|/<id>|/<id>/edit|/<id>/adjust|/<id>/delete]` `/sales[/new|/<id>]` `/purchases[/new]` `/customers /suppliers /categories` `/reports` `/users` `/export/products.csv`.
