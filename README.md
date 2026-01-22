# GM CAR A/C SERVICE & MULTIBRAND BILLING

A full-stack billing system for an Indian automobile A/C and multibrand service center. The system includes invoice generation, GST handling, PDF storage, WhatsApp sharing, admin controls, and monthly GST reports.

## Features

- Admin login and secure dashboard
- Invoice creation with GST toggle and auto-numbering (GM-INV-0001)
- Strict printable invoice layout
- Payment tracking (Unpaid / Partially Paid / Paid)
- Automatic PDF generation and local storage
- WhatsApp invoice sharing with template messaging
- Monthly GST reports with PDF and Excel exports
- Backup & export tools for invoices

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Flask application:
   ```bash
   python app.py
   ```

3. Open `http://localhost:5500` in your browser.

## Default Admin Login

- Username: `admin`
- Password: `admin123`

## Storage

- SQLite database stored in `data/billing.db`
- Invoice PDFs stored in `invoices/YYYY/MM/GM-INV-0001.pdf`
