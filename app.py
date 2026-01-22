from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
import sqlite3
import os
import io
import xlsxwriter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INVOICE_DIR = os.path.join(BASE_DIR, "invoices")
LOGO_PATH = os.path.join(BASE_DIR, "static", "img", "logo.png")
DATABASE_PATH = os.path.join(DATA_DIR, "billing.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gmcaracservice-secret-key")

DEFAULT_SETTINGS = {
    "company_name": "GM CAR A/C SERVICE & MULTIBRAND",
    "company_address_line1": "No:16 Gangai Amman Kallikuppam, Ambattur Chennai-53 Tamilnadu",
    "company_address_line2": "Chennai, Tamil Nadu - 600053",
    "company_phone": "+91 84280 00085",
    "company_email": "gmautocool@gmail.com",
    "company_website": "www.gmcaracservice.com",
    "company_logo_path": LOGO_PATH,
    "gst_cgst_rate": "9",
    "gst_sgst_rate": "9",
    "gst_igst_rate": "18",
    "gst_default_type": "cgst_sgst",
    "invoice_sequence": "0",
    "whatsapp_template": "Hello {{Customer Name}},\nThank you for choosing GM Car A/C Service.\nInvoice {{Invoice Number}} attached.",
}


def ensure_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(INVOICE_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "static", "img"), exist_ok=True)


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    ensure_directories()
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                vehicle TEXT,
                vehicle_number TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                price REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER,
                date TEXT,
                gst_enabled INTEGER,
                gst_type TEXT,
                cgst_rate REAL,
                sgst_rate REAL,
                igst_rate REAL,
                subtotal REAL,
                total REAL,
                amount_paid REAL,
                payment_method TEXT,
                payment_status TEXT,
                pdf_path TEXT,
                created_at TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                description TEXT,
                amount REAL,
                FOREIGN KEY(invoice_id) REFERENCES invoices(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        for key, value in DEFAULT_SETTINGS.items():
            existing = conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone()
            if not existing:
                conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        user_exists = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        if not user_exists:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash("admin123")),
            )


def to_decimal(value):
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0")


def normalize_amount(value):
    decimal_value = to_decimal(value)
    return decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_number(value):
    if value is None:
        return ""
    decimal_value = normalize_amount(value)
    text = f"{decimal_value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


@app.template_filter("currency")
def currency_filter(value):
    if value is None or value == "":
        return ""
    return f"₹{format_number(value)}"


def get_setting(conn, key, default=""):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_settings():
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def update_settings(values):
    with get_db() as conn:
        for key, value in values.items():
            conn.execute("UPDATE settings SET value = ? WHERE key = ?", (str(value), key))


def get_next_invoice_number(conn):
    sequence_value = conn.execute(
        "SELECT value FROM settings WHERE key = ?", ("invoice_sequence",)
    ).fetchone()
    current = int(sequence_value["value"]) if sequence_value else 0
    next_value = current + 1
    conn.execute(
        "UPDATE settings SET value = ? WHERE key = ?",
        (str(next_value), "invoice_sequence"),
    )
    return f"GM-INV-{next_value:04d}"


def calculate_gst(subtotal, gst_enabled, gst_type, cgst_rate, sgst_rate, igst_rate):
    subtotal_amount = normalize_amount(subtotal)
    gst_amounts = {
        "subtotal": subtotal_amount,
        "cgst": Decimal("0"),
        "sgst": Decimal("0"),
        "igst": Decimal("0"),
        "total": subtotal_amount,
        "total_gst": Decimal("0"),
    }
    if not gst_enabled:
        return gst_amounts
    if gst_type == "igst":
        igst = subtotal_amount * to_decimal(igst_rate) / Decimal("100")
        gst_amounts["igst"] = normalize_amount(igst)
    else:
        cgst = subtotal_amount * to_decimal(cgst_rate) / Decimal("100")
        sgst = subtotal_amount * to_decimal(sgst_rate) / Decimal("100")
        gst_amounts["cgst"] = normalize_amount(cgst)
        gst_amounts["sgst"] = normalize_amount(sgst)
    gst_amounts["total_gst"] = normalize_amount(
        gst_amounts["cgst"] + gst_amounts["sgst"] + gst_amounts["igst"]
    )
    gst_amounts["total"] = normalize_amount(subtotal_amount + gst_amounts["total_gst"])
    return gst_amounts


def determine_payment_status(total_amount, amount_paid):
    total_decimal = normalize_amount(total_amount)
    paid_decimal = normalize_amount(amount_paid)
    if paid_decimal <= Decimal("0"):
        return "Unpaid"
    if paid_decimal < total_decimal:
        return "Partially Paid"
    return "Paid"


def build_invoice_pdf_path(invoice_number, invoice_date):
    date_value = datetime.strptime(invoice_date, "%Y-%m-%d")
    year = f"{date_value.year:04d}"
    month = f"{date_value.month:02d}"
    directory = os.path.join(INVOICE_DIR, year, month)
    os.makedirs(directory, exist_ok=True)
    filename = f"{invoice_number}.pdf"
    return os.path.join(directory, filename)


def generate_invoice_pdf(invoice, customer, items, settings):
    pdf_path = build_invoice_pdf_path(invoice["invoice_number"], invoice["date"])
    if os.path.exists(pdf_path):
        return pdf_path

    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 18 * mm

    canvas_obj.setFillColorRGB(0, 0, 0)
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(margin, height - margin, settings.get("company_name", ""))

    canvas_obj.setFont("Helvetica", 9)
    header_lines = [
        settings.get("company_address_line1", ""),
        settings.get("company_address_line2", ""),
        f"Phone: {settings.get('company_phone', '')}",
        f"Email: {settings.get('company_email', '')}",
        f"Website: {settings.get('company_website', '')}",
    ]
    text_y = height - margin - 14
    for line in header_lines:
        canvas_obj.drawString(margin, text_y, line)
        text_y -= 12

    logo_path = settings.get("company_logo_path", "")
    if logo_path and os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_width = 90
        logo_height = 90
        canvas_obj.drawImage(
            logo,
            width - margin - logo_width,
            height - margin - logo_height + 5,
            width=logo_width,
            height=logo_height,
            mask='auto',
        )

    divider_y = text_y - 6
    canvas_obj.line(margin, divider_y, width - margin, divider_y)

    details_top = divider_y - 18
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(margin, details_top, "Invoice To:")
    canvas_obj.drawString(width - margin - 170, details_top, "Invoice Details:")

    canvas_obj.setFont("Helvetica", 9)
    customer_lines = [
        customer.get("name", ""),
        customer.get("phone", ""),
        customer.get("vehicle", ""),
        customer.get("vehicle_number", ""),
    ]
    detail_y = details_top - 12
    for line in customer_lines:
        canvas_obj.drawString(margin, detail_y, line)
        detail_y -= 12

    invoice_lines = [
        f"Invoice #: {invoice['invoice_number']}",
        f"Date: {invoice['date']}",
    ]
    invoice_y = details_top - 12
    for line in invoice_lines:
        canvas_obj.drawString(width - margin - 170, invoice_y, line)
        invoice_y -= 12

    table_top = min(detail_y, invoice_y) - 10
    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.drawString(margin, table_top, "Description")
    canvas_obj.drawRightString(width - margin, table_top, "Amount")
    canvas_obj.line(margin, table_top - 4, width - margin, table_top - 4)

    row_y = table_top - 16
    canvas_obj.setFont("Helvetica", 9)
    for item in items:
        canvas_obj.drawString(margin, row_y, item["description"] or "")
        canvas_obj.drawRightString(width - margin, row_y, f"₹{format_number(item['amount'])}")
        row_y -= 14

    totals_y = row_y - 10
    canvas_obj.setFont("Helvetica", 9)
    if invoice["gst_enabled"]:
        canvas_obj.drawRightString(width - margin, totals_y, f"Subtotal: ₹{format_number(invoice['subtotal'])}")
        totals_y -= 12
        if invoice["gst_type"] == "igst":
            canvas_obj.drawRightString(
                width - margin,
                totals_y,
                f"IGST ({format_number(invoice['igst_rate'])} %): ₹{format_number(invoice['igst_amount'])}",
            )
            totals_y -= 12
        else:
            canvas_obj.drawRightString(
                width - margin,
                totals_y,
                f"CGST ({format_number(invoice['cgst_rate'])} %): ₹{format_number(invoice['cgst_amount'])}",
            )
            totals_y -= 12
            canvas_obj.drawRightString(
                width - margin,
                totals_y,
                f"SGST ({format_number(invoice['sgst_rate'])} %): ₹{format_number(invoice['sgst_amount'])}",
            )
            totals_y -= 12

    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawRightString(width - margin, totals_y, f"Total: ₹{format_number(invoice['total'])}")

    footer_y = 40
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawCentredString(width / 2, footer_y + 12, "Thank you for choosing our service!")
    canvas_obj.drawCentredString(width / 2, footer_y, '"No Warranty and No Guarantee"')

    canvas_obj.showPage()
    canvas_obj.save()

    with open(pdf_path, "wb") as output_file:
        output_file.write(buffer.getvalue())

    return pdf_path


def fetch_invoice_data(conn, invoice_id):
    invoice = conn.execute(
        """
        SELECT invoices.*, customers.name as customer_name, customers.phone as customer_phone,
               customers.vehicle as customer_vehicle, customers.vehicle_number as customer_vehicle_number
        FROM invoices
        LEFT JOIN customers ON invoices.customer_id = customers.id
        WHERE invoices.id = ?
        """,
        (invoice_id,),
    ).fetchone()
    if not invoice:
        return None, None, None
    items = conn.execute(
        "SELECT description, amount FROM invoice_items WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchall()
    customer = {
        "name": invoice["customer_name"] or "",
        "phone": invoice["customer_phone"] or "",
        "vehicle": invoice["customer_vehicle"] or "",
        "vehicle_number": invoice["customer_vehicle_number"] or "",
    }
    return invoice, items, customer


def prepare_invoice_context(invoice, items, customer):
    gst_details = calculate_gst(
        invoice["subtotal"],
        invoice["gst_enabled"],
        invoice["gst_type"],
        invoice["cgst_rate"],
        invoice["sgst_rate"],
        invoice["igst_rate"],
    )
    invoice_context = dict(invoice)
    total_amount = normalize_amount(invoice["total"])
    amount_paid = normalize_amount(invoice["amount_paid"])
    balance_amount = normalize_amount(total_amount - amount_paid)
    invoice_context.update(
        {
            "cgst_amount": float(gst_details["cgst"]),
            "sgst_amount": float(gst_details["sgst"]),
            "igst_amount": float(gst_details["igst"]),
            "subtotal_display": format_number(invoice["subtotal"]),
            "total_display": format_number(invoice["total"]),
            "cgst_rate_display": format_number(invoice["cgst_rate"]),
            "sgst_rate_display": format_number(invoice["sgst_rate"]),
            "igst_rate_display": format_number(invoice["igst_rate"]),
            "cgst_amount_display": format_number(gst_details["cgst"]),
            "sgst_amount_display": format_number(gst_details["sgst"]),
            "igst_amount_display": format_number(gst_details["igst"]),
            "amount_paid_display": format_number(amount_paid),
            "balance_display": format_number(balance_amount),
        }
    )
    return invoice_context


def login_required(view):
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


init_db()


@app.route("/")
def home():
    return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    default_date = date.today().isoformat()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Invalid username or password")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    with get_db() as conn:
        total_invoices = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        total_revenue = conn.execute("SELECT COALESCE(SUM(total), 0) FROM invoices").fetchone()[0]
        unpaid_count = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE payment_status != 'Paid'"
        ).fetchone()[0]
    return render_template(
        "admin_dashboard.html",
        total_invoices=total_invoices,
        total_customers=total_customers,
        total_revenue=total_revenue,
        unpaid_count=unpaid_count,
    )


@app.route("/admin/invoices")
@login_required
def admin_invoices():
    status_filter = request.args.get("status", "")
    search_query = request.args.get("q", "").strip()
    query = (
        "SELECT invoices.*, customers.name as customer_name "
        "FROM invoices LEFT JOIN customers ON invoices.customer_id = customers.id"
    )
    clauses = []
    params = []
    if status_filter:
        clauses.append("invoices.payment_status = ?")
        params.append(status_filter)
    if search_query:
        clauses.append("(invoices.invoice_number LIKE ? OR customers.name LIKE ?)")
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY invoices.date DESC"
    with get_db() as conn:
        invoices = conn.execute(query, params).fetchall()
    return render_template(
        "admin_invoices.html",
        invoices=invoices,
        status_filter=status_filter,
        search_query=search_query,
    )


@app.route("/admin/invoices/new", methods=["GET", "POST"])
@login_required
def admin_invoice_new():
    with get_db() as conn:
        customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        services = conn.execute("SELECT id, description, price FROM services").fetchall()
        settings = get_settings()
    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        customer_name = request.form.get("customer_name", "").strip()
        customer_phone = request.form.get("customer_phone", "").strip()
        customer_vehicle = request.form.get("customer_vehicle", "").strip()
        customer_vehicle_number = request.form.get("customer_vehicle_number", "").strip()
        invoice_date = request.form.get("invoice_date", date.today().isoformat())
        gst_enabled = request.form.get("gst_enabled") == "yes"
        gst_type = request.form.get("gst_type", settings.get("gst_default_type", "cgst_sgst"))
        cgst_rate = request.form.get("cgst_rate", settings.get("gst_cgst_rate"))
        sgst_rate = request.form.get("sgst_rate", settings.get("gst_sgst_rate"))
        igst_rate = request.form.get("igst_rate", settings.get("gst_igst_rate"))
        descriptions = request.form.getlist("item_description")
        amounts = request.form.getlist("item_amount")
        amount_paid = request.form.get("amount_paid", "0")
        payment_method = request.form.get("payment_method", "Cash")

        items = []
        for description, amount in zip(descriptions, amounts):
            if not description and not amount:
                continue
        items.append({"description": description.strip(), "amount": amount or "0"})
        if not items:
            return render_template(
                "admin_invoice_form.html",
                customers=customers,
                services=services,
                settings=settings,
                default_date=invoice_date,
                error="Please add at least one service item.",
            )

        with get_db() as conn:
            if customer_id and customer_id != "new":
                customer = conn.execute(
                    "SELECT id FROM customers WHERE id = ?", (customer_id,)
                ).fetchone()
                customer_db_id = customer["id"] if customer else None
            else:
                customer_db_id = None
            if not customer_db_id:
                conn.execute(
                    """
                    INSERT INTO customers (name, phone, vehicle, vehicle_number, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        customer_name,
                        customer_phone,
                        customer_vehicle,
                        customer_vehicle_number,
                        datetime.now().isoformat(),
                    ),
                )
                customer_db_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            invoice_number = get_next_invoice_number(conn)
            subtotal = sum([normalize_amount(item["amount"]) for item in items], Decimal("0"))
            gst_details = calculate_gst(
                subtotal,
                gst_enabled,
                gst_type,
                cgst_rate,
                sgst_rate,
                igst_rate,
            )
            total_amount = gst_details["total"]
            payment_status = determine_payment_status(total_amount, amount_paid)

            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_number, customer_id, date, gst_enabled, gst_type, cgst_rate,
                    sgst_rate, igst_rate, subtotal, total, amount_paid, payment_method,
                    payment_status, pdf_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_number,
                    customer_db_id,
                    invoice_date,
                    1 if gst_enabled else 0,
                    gst_type,
                    float(normalize_amount(cgst_rate)),
                    float(normalize_amount(sgst_rate)),
                    float(normalize_amount(igst_rate)),
                    float(gst_details["subtotal"]),
                    float(total_amount),
                    float(normalize_amount(amount_paid)),
                    payment_method,
                    payment_status,
                    "",
                    datetime.now().isoformat(),
                ),
            )
            invoice_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            for item in items:
                conn.execute(
                    "INSERT INTO invoice_items (invoice_id, description, amount) VALUES (?, ?, ?)",
                    (invoice_id, item["description"], float(normalize_amount(item["amount"]))),
                )

            invoice, db_items, customer_info = fetch_invoice_data(conn, invoice_id)
            invoice_context = prepare_invoice_context(invoice, db_items, customer_info)
            pdf_path = generate_invoice_pdf(invoice_context, customer_info, db_items, settings)
            conn.execute(
                "UPDATE invoices SET pdf_path = ? WHERE id = ?", (pdf_path, invoice_id)
            )

        return redirect(url_for("admin_invoice_view", invoice_id=invoice_id))

    return render_template(
        "admin_invoice_form.html",
        customers=customers,
        services=services,
        settings=settings,
        default_date=default_date,
    )


@app.route("/admin/invoices/<int:invoice_id>")
@login_required
def admin_invoice_view(invoice_id):
    with get_db() as conn:
        invoice, items, customer = fetch_invoice_data(conn, invoice_id)
    if not invoice:
        return redirect(url_for("admin_invoices"))
    settings = get_settings()
    invoice_context = prepare_invoice_context(invoice, items, customer)
    return render_template(
        "admin_invoice_view.html",
        invoice=invoice_context,
        items=items,
        customer=customer,
        settings=settings,
    )


@app.route("/admin/invoices/<int:invoice_id>/print")
@login_required
def admin_invoice_print(invoice_id):
    with get_db() as conn:
        invoice, items, customer = fetch_invoice_data(conn, invoice_id)
    if not invoice:
        return redirect(url_for("admin_invoices"))
    settings = get_settings()
    invoice_context = prepare_invoice_context(invoice, items, customer)
    return render_template(
        "invoice_print.html",
        invoice=invoice_context,
        items=items,
        customer=customer,
        settings=settings,
    )


@app.route("/admin/invoices/<int:invoice_id>/pdf")
@login_required
def admin_invoice_pdf(invoice_id):
    with get_db() as conn:
        invoice, items, customer = fetch_invoice_data(conn, invoice_id)
    if not invoice:
        return redirect(url_for("admin_invoices"))
    settings = get_settings()
    invoice_context = prepare_invoice_context(invoice, items, customer)
    pdf_path = invoice_context.get("pdf_path") or generate_invoice_pdf(
        invoice_context, customer, items, settings
    )
    return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))


@app.route("/admin/invoices/<int:invoice_id>/payment", methods=["POST"])
@login_required
def admin_invoice_payment(invoice_id):
    amount_paid = request.form.get("amount_paid", "0")
    payment_method = request.form.get("payment_method", "Cash")
    with get_db() as conn:
        invoice = conn.execute("SELECT total FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not invoice:
            return redirect(url_for("admin_invoices"))
        status = determine_payment_status(invoice["total"], amount_paid)
        conn.execute(
            "UPDATE invoices SET amount_paid = ?, payment_method = ?, payment_status = ? WHERE id = ?",
            (float(normalize_amount(amount_paid)), payment_method, status, invoice_id),
        )
    return redirect(url_for("admin_invoice_view", invoice_id=invoice_id))


@app.route("/admin/invoices/<int:invoice_id>/whatsapp")
@login_required
def admin_invoice_whatsapp(invoice_id):
    with get_db() as conn:
        invoice, items, customer = fetch_invoice_data(conn, invoice_id)
    if not invoice:
        return redirect(url_for("admin_invoices"))
    settings = get_settings()
    template = settings.get("whatsapp_template", DEFAULT_SETTINGS["whatsapp_template"])
    message = template.replace("{{Customer Name}}", customer.get("name", "")).replace(
        "{{Invoice Number}}", invoice["invoice_number"]
    )
    pdf_url = url_for("admin_invoice_pdf", invoice_id=invoice_id, _external=True)
    message_with_link = f"{message}\n{pdf_url}"
    whatsapp_url = "https://wa.me/?text=" + request.args.get("text", "")
    whatsapp_url = f"https://wa.me/?text={message_with_link}".replace(" ", "%20").replace("\n", "%0A")
    return redirect(whatsapp_url)


@app.route("/admin/customers", methods=["GET", "POST"])
@login_required
def admin_customers():
    if request.method == "POST":
        with get_db() as conn:
            conn.execute(
                "INSERT INTO customers (name, phone, vehicle, vehicle_number, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("vehicle", "").strip(),
                    request.form.get("vehicle_number", "").strip(),
                    datetime.now().isoformat(),
                ),
            )
        return redirect(url_for("admin_customers"))
    with get_db() as conn:
        customers = conn.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall()
    return render_template("admin_customers.html", customers=customers)


@app.route("/admin/services", methods=["GET", "POST"])
@login_required
def admin_services():
    if request.method == "POST":
        with get_db() as conn:
            conn.execute(
                "INSERT INTO services (description, price) VALUES (?, ?)",
                (
                    request.form.get("description", "").strip(),
                    float(normalize_amount(request.form.get("price", "0"))),
                ),
            )
        return redirect(url_for("admin_services"))
    with get_db() as conn:
        services = conn.execute("SELECT * FROM services ORDER BY description").fetchall()
    return render_template("admin_services.html", services=services)


@app.route("/admin/services/<int:service_id>/update", methods=["POST"])
@login_required
def admin_service_update(service_id):
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "0")
    with get_db() as conn:
        conn.execute(
            "UPDATE services SET description = ?, price = ? WHERE id = ?",
            (description, float(normalize_amount(price)), service_id),
        )
    return redirect(url_for("admin_services"))


@app.route("/admin/gst-settings", methods=["GET", "POST"])
@login_required
def admin_gst_settings():
    settings = get_settings()
    if request.method == "POST":
        update_settings(
            {
                "gst_cgst_rate": request.form.get("gst_cgst_rate", settings.get("gst_cgst_rate")),
                "gst_sgst_rate": request.form.get("gst_sgst_rate", settings.get("gst_sgst_rate")),
                "gst_igst_rate": request.form.get("gst_igst_rate", settings.get("gst_igst_rate")),
                "gst_default_type": request.form.get("gst_default_type", settings.get("gst_default_type")),
            }
        )
        return redirect(url_for("admin_gst_settings"))
    return render_template("admin_gst_settings.html", settings=settings)


@app.route("/admin/company-profile", methods=["GET", "POST"])
@login_required
def admin_company_profile():
    settings = get_settings()
    if request.method == "POST":
        update_settings(
            {
                "company_name": request.form.get("company_name", "").strip(),
                "company_address_line1": request.form.get("company_address_line1", "").strip(),
                "company_address_line2": request.form.get("company_address_line2", "").strip(),
                "company_phone": request.form.get("company_phone", "").strip(),
                "company_email": request.form.get("company_email", "").strip(),
                "company_website": request.form.get("company_website", "").strip(),
            }
        )
        return redirect(url_for("admin_company_profile"))
    return render_template("admin_company_profile.html", settings=settings)


@app.route("/admin/whatsapp-settings", methods=["GET", "POST"])
@login_required
def admin_whatsapp_settings():
    settings = get_settings()
    if request.method == "POST":
        update_settings({"whatsapp_template": request.form.get("whatsapp_template", "").strip()})
        return redirect(url_for("admin_whatsapp_settings"))
    return render_template("admin_whatsapp_settings.html", settings=settings)


def build_report(month_value):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT subtotal, gst_enabled, gst_type, cgst_rate, sgst_rate, igst_rate
            FROM invoices
            WHERE strftime('%Y-%m', date) = ?
            """,
            (month_value,),
        ).fetchall()
    taxable_value = Decimal("0")
    cgst_total = Decimal("0")
    sgst_total = Decimal("0")
    igst_total = Decimal("0")
    revenue = Decimal("0")
    for row in rows:
        subtotal = normalize_amount(row["subtotal"])
        taxable_value += subtotal
        gst_details = calculate_gst(
            subtotal,
            row["gst_enabled"],
            row["gst_type"],
            row["cgst_rate"],
            row["sgst_rate"],
            row["igst_rate"],
        )
        cgst_total += gst_details["cgst"]
        sgst_total += gst_details["sgst"]
        igst_total += gst_details["igst"]
        revenue += gst_details["total"]
    total_gst = cgst_total + sgst_total + igst_total
    return {
        "month": month_value,
        "taxable_value": taxable_value,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "igst_total": igst_total,
        "total_gst": total_gst,
        "revenue": revenue,
    }


@app.route("/admin/reports", methods=["GET", "POST"])
@login_required
def admin_reports():
    month_value = request.form.get("month") or request.args.get("month")
    report = None
    if month_value:
        report = build_report(month_value)
    return render_template("admin_reports.html", report=report, month_value=month_value)


@app.route("/admin/reports/export/pdf")
@login_required
def admin_report_pdf():
    month_value = request.args.get("month")
    if not month_value:
        return redirect(url_for("admin_reports"))
    report = build_report(month_value)
    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(margin, height - margin, "Monthly GST Report")
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawString(margin, height - margin - 16, f"Month: {month_value}")
    start_y = height - margin - 40
    entries = [
        ("Taxable Value", report["taxable_value"]),
        ("CGST Total", report["cgst_total"]),
        ("SGST Total", report["sgst_total"]),
        ("IGST Total", report["igst_total"]),
        ("Total GST", report["total_gst"]),
        ("Revenue", report["revenue"]),
    ]
    for label, value in entries:
        canvas_obj.drawString(margin, start_y, label)
        canvas_obj.drawRightString(width - margin, start_y, f"₹{format_number(value)}")
        start_y -= 14
    canvas_obj.showPage()
    canvas_obj.save()
    buffer.seek(0)
    filename = f"gst-report-{month_value}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename)


@app.route("/admin/reports/export/excel")
@login_required
def admin_report_excel():
    month_value = request.args.get("month")
    if not month_value:
        return redirect(url_for("admin_reports"))
    report = build_report(month_value)
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("GST Report")
    worksheet.write(0, 0, "Month")
    worksheet.write(0, 1, month_value)
    data_rows = [
        ("Taxable Value", report["taxable_value"]),
        ("CGST Total", report["cgst_total"]),
        ("SGST Total", report["sgst_total"]),
        ("IGST Total", report["igst_total"]),
        ("Total GST", report["total_gst"]),
        ("Revenue", report["revenue"]),
    ]
    row = 2
    for label, value in data_rows:
        worksheet.write(row, 0, label)
        worksheet.write(row, 1, float(value))
        row += 1
    workbook.close()
    output.seek(0)
    filename = f"gst-report-{month_value}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename)


@app.route("/admin/backup-export")
@login_required
def admin_backup_export():
    return render_template("admin_backup_export.html")


@app.route("/admin/exports/invoices.xlsx")
@login_required
def export_invoices_excel():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT invoices.invoice_number, invoices.date, invoices.total, invoices.payment_status,
                   customers.name as customer_name
            FROM invoices
            LEFT JOIN customers ON invoices.customer_id = customers.id
            ORDER BY invoices.date DESC
            """
        ).fetchall()
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Invoices")
    headers = ["Invoice नंबर", "Date", "Customer", "Total", "Status"]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    row_index = 1
    for row in rows:
        worksheet.write(row_index, 0, row["invoice_number"])
        worksheet.write(row_index, 1, row["date"])
        worksheet.write(row_index, 2, row["customer_name"] or "")
        worksheet.write(row_index, 3, float(row["total"]))
        worksheet.write(row_index, 4, row["payment_status"])
        row_index += 1
    workbook.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="invoices.xlsx")


@app.route("/admin/exports/invoices.pdf")
@login_required
def export_invoices_pdf():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT invoices.invoice_number, invoices.date, invoices.total, invoices.payment_status,
                   customers.name as customer_name
            FROM invoices
            LEFT JOIN customers ON invoices.customer_id = customers.id
            ORDER BY invoices.date DESC
            """
        ).fetchall()
    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    canvas_obj.setFont("Helvetica-Bold", 12)
    canvas_obj.drawString(margin, height - margin, "Invoice Export")
    y = height - margin - 20
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawString(margin, y, "Invoice #")
    canvas_obj.drawString(margin + 90, y, "Date")
    canvas_obj.drawString(margin + 170, y, "Customer")
    canvas_obj.drawRightString(width - margin, y, "Total")
    y -= 12
    canvas_obj.line(margin, y, width - margin, y)
    y -= 12
    for row in rows:
        canvas_obj.drawString(margin, y, row["invoice_number"])
        canvas_obj.drawString(margin + 90, y, row["date"])
        canvas_obj.drawString(margin + 170, y, row["customer_name"] or "")
        canvas_obj.drawRightString(width - margin, y, f"₹{format_number(row['total'])}")
        y -= 12
        if y < 60:
            canvas_obj.showPage()
            y = height - margin
    canvas_obj.showPage()
    canvas_obj.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="invoices.pdf")


if __name__ == "__main__":
    app.run(debug=True, port=5500)
