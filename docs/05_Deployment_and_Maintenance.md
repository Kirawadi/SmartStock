# 5. Deployment & Maintenance (SDLC Phases 5-6)

## Deployment
Requirements: Python 3.8+. Steps: unzip, `python app.py`, open the URL, change default passwords. For LAN use, edit `make_server(host="0.0.0.0")`; for internet use, place behind an HTTPS reverse proxy (nginx/Caddy) and add the `Secure` cookie flag.

## Maintenance
- Backup: copy `smartstock.db` while idle (or `sqlite3 smartstock.db ".backup b.db"`).
- Reset: delete `smartstock.db`.
- Updates: schema changes via new SQL migration scripts; run tests before release.
- Monitoring: console shows server errors; users never see tracebacks.

## Future enhancements
Barcode scanning, GST/tax, returns & credit notes, multi-branch, email low-stock alerts, PostgreSQL migration.
