import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ==========================================================
# PAGE SETTINGS
# ==========================================================
st.set_page_config(
    page_title="Supermarket Billing System",
    page_icon="🛒",
    layout="wide",
)

SHOP_NAME = "FreshLane Supermarket"
SHOP_ADDRESS = "Bengaluru, Karnataka"
SHOP_PHONE = "9865473210"
DATABASE = "supermarket.db"
st.write("DATABASE TEST:", DATABASE)

RECEIPT_WIDTH = 48


# ==========================================================
# DATABASE
# ==========================================================
def get_connection():
    return sqlite3.connect(DATABASE)


def add_column_if_missing(conn, table, column, definition):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_database():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT,
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            product TEXT,
            price REAL,
            purchase_price REAL DEFAULT 0,
            quantity INTEGER,
            total REAL,
            date TEXT,
            payment_method TEXT DEFAULT 'Cash'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT UNIQUE,
            purchase_price REAL DEFAULT 0,
            price REAL,
            stock INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            quantity INTEGER,
            purchase_price REAL,
            total REAL,
            supplier TEXT DEFAULT '',
            date TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            amount REAL,
            description TEXT DEFAULT '',
            date TEXT
        )
    """)

    # Upgrade older databases safely
    add_column_if_missing(conn, "sales", "purchase_price", "REAL DEFAULT 0")
    add_column_if_missing(conn, "sales", "customer_name", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "sales", "customer_phone", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "sales", "payment_method", "TEXT DEFAULT 'Cash'")
    add_column_if_missing(conn, "inventory", "purchase_price", "REAL DEFAULT 0")
    add_column_if_missing(conn, "purchases", "supplier", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "purchases", "date", "TEXT")

    conn.commit()
    conn.close()


create_database()


# ==========================================================
# HELPERS
# ==========================================================
def flash(message, kind="success"):
    """Store a message that survives st.rerun()."""
    st.session_state["_flash"] = (kind, message)


def show_flash():
    if "_flash" in st.session_state:
        kind, message = st.session_state.pop("_flash")
        if kind == "success":
            st.success(message)
        elif kind == "error":
            st.error(message)
        elif kind == "warning":
            st.warning(message)
        else:
            st.info(message)


def load_sales(order="id DESC"):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM sales ORDER BY {order}", conn)
    conn.close()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["purchase_price"] = df["purchase_price"].fillna(0)
        df["customer_name"] = df["customer_name"].fillna("")
        df["customer_phone"] = df["customer_phone"].fillna("")
        df["profit"] = (df["price"] - df["purchase_price"]) * df["quantity"]

    return df


def load_inventory():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory ORDER BY product", conn)
    conn.close()

    if not df.empty:
        df["purchase_price"] = df["purchase_price"].fillna(0)

    return df


def add_inventory_values(inventory):
    inventory["Purchase Value"] = inventory["purchase_price"] * inventory["stock"]
    inventory["Selling Value"] = inventory["price"] * inventory["stock"]
    inventory["Potential Profit"] = inventory["Selling Value"] - inventory["Purchase Value"]
    return inventory


def daily_chart(sales, column, label):
    valid_sales = sales.dropna(subset=["date"]).copy()

    if valid_sales.empty:
        st.info("No data available for this chart.")
        return

    valid_sales["Date"] = valid_sales["date"].dt.date

    daily = valid_sales.groupby("Date")[column].sum().reset_index()
    daily.columns = ["Date", label]

    st.bar_chart(daily, x="Date", y=label)


def build_receipt(bill_id, date_text, customer, phone, payment, items, grand_total):
    """items = list of (product_name, quantity, line_total)."""
    W = RECEIPT_WIDTH
    line = "=" * W
    dash = "-" * W

    text = f"""{line}
{SHOP_NAME.upper().center(W)}
{SHOP_ADDRESS.center(W)}
{("Phone: " + SHOP_PHONE).center(W)}
{line}
{"INVOICE".center(W)}
{dash}
Bill No  : {bill_id}
Date     : {date_text}
Customer : {customer}
Phone    : {phone}
Payment  : {payment}
{dash}
{"ITEM":<24}{"QTY":>6}{"AMOUNT":>18}
{dash}
"""

    total_items = 0
    for name, qty, amount in items:
        total_items += int(qty)
        text += f"{str(name)[:22]:<24}{int(qty):>6}{('₹' + format(float(amount), '.2f')):>18}\n"

    text += f"""{dash}
{"TOTAL ITEMS":<16}: {total_items}
{"GRAND TOTAL":<16}: ₹{grand_total:.2f}
{line}
{"THANK YOU! VISIT AGAIN".center(W)}
{line}
"""
    return text


def show_html(html, height=700):
    """st.components.v1.html is deprecated in newer Streamlit; prefer st.iframe."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height, scrolling=True)


def printable_html(receipt_text):
    safe = (
        receipt_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; background: white; color: black; margin: 0; padding: 20px; }}
.receipt {{ width: 440px; max-width: 100%; box-sizing: border-box; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
pre {{ font-family: "Courier New", monospace; font-size: 13px; white-space: pre; overflow-x: auto; line-height: 1.45; margin: 0; }}
.print-button {{ display: block; margin: 20px auto 0; padding: 10px 25px; font-size: 16px; cursor: pointer; border-radius: 6px; border: none; }}
@media print {{
    .print-button {{ display: none; }}
    body {{ padding: 0; }}
    .receipt {{ border: none; box-shadow: none; }}
}}
</style>
</head>
<body>
<div class="receipt">
<pre>{safe}</pre>
<button class="print-button" onclick="window.print()">🖨️ Print Receipt</button>
</div>
</body>
</html>
"""


# ==========================================================
# CUSTOM STYLE
# ==========================================================
st.markdown("""
<style>
.main { padding-top: 1.5rem; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px; }

h1 { font-size: 42px !important; font-weight: 750 !important; letter-spacing: -0.5px; margin-bottom: 8px !important; }
h2 { font-size: 30px !important; font-weight: 700 !important; }
h3 { font-size: 22px !important; font-weight: 650 !important; }

section[data-testid="stSidebar"] { padding-top: 1.5rem; }
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
section[data-testid="stSidebar"] h1 { font-size: 28px !important; }
section[data-testid="stSidebar"] .stRadio label { font-size: 15px; font-weight: 600; }

[data-testid="stMetric"] {
    padding: 20px 22px;
    border-radius: 16px;
    border: 1px solid rgba(128,128,128,0.20);
    background-color: rgba(128,128,128,0.08);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,0.08); }
[data-testid="stMetricLabel"] { font-weight: 600; }
[data-testid="stMetricValue"] { font-weight: 750; }

.stButton > button { border-radius: 10px; font-weight: 650; min-height: 42px; padding: 8px 20px; transition: all 0.2s ease; }
.stButton > button:hover { transform: translateY(-1px); }

.stTextInput input, .stNumberInput input, .stTextArea textarea { border-radius: 10px; }
div[data-baseweb="select"] > div { border-radius: 10px; }
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
div[data-testid="stAlert"] { border-radius: 12px; }
hr { margin-top: 28px; margin-bottom: 28px; }
[data-testid="stExpander"] { border-radius: 12px; }
.stCaption { opacity: 0.75; }

.dashboard-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 22px 26px; margin-bottom: 25px; border-radius: 18px;
    border: 1px solid rgba(128,128,128,0.20);
    background: rgba(128,128,128,0.06);
}
.dashboard-header h1 { margin: 0 !important; padding: 0 !important; }
.dashboard-header p { margin: 6px 0 0 2px; font-size: 15px; opacity: 0.7; }
.dashboard-badge {
    padding: 9px 16px; border-radius: 20px; font-size: 14px; font-weight: 650;
    border: 1px solid rgba(128,128,128,0.25);
    background: rgba(128,128,128,0.08);
}

@media (max-width: 768px) {
    h1 { font-size: 32px !important; }
    h2 { font-size: 25px !important; }
    h3 { font-size: 20px !important; }
    .dashboard-header { flex-direction: column; align-items: flex-start; gap: 15px; }
}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# SIDEBAR NAVIGATION
# ==========================================================
st.sidebar.title("🛒 FreshLane")
st.sidebar.caption("Supermarket Management System")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Dashboard",
        "🧾 New Bill",
        "📊 Accounts",
        "💰 Purchases",
        "💸 Expenses",
        "📦 Inventory",
        "👥 Customers",
        "🧾 Bill History",
        "📈 Reports",
        "ℹ️ About",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Billing • Inventory • Accounts • Reports")


# ==========================================================
# DASHBOARD
# ==========================================================
if page == "🏠 Dashboard":

    # NOTE: no indentation / blank lines inside this HTML, otherwise
    # Streamlit's markdown treats it as a code block.
    st.markdown(
"""
<div class="dashboard-header">
<div>
<div style="font-size:14px; font-weight:600; opacity:0.65; margin-bottom:5px;">FRESHLANE SUPERMARKET</div>
<h1>🏠 Business Dashboard</h1>
<p>Monitor sales, inventory, customers and business performance from one place.</p>
</div>
<div class="dashboard-badge">🟢 System Active</div>
</div>
""",
        unsafe_allow_html=True,
    )

    show_flash()

    sales = load_sales()
    inventory = load_inventory()

    today = datetime.now().date()

    # ------------------------------------------------------
    # TODAY'S DATA
    # ------------------------------------------------------
    if not sales.empty:
        today_sales = sales[sales["date"].dt.date == today]
        today_total = today_sales["total"].sum()
        today_bills = today_sales["bill_id"].nunique()
        today_items = today_sales["quantity"].sum()
        today_profit = today_sales["profit"].sum()
    else:
        today_sales = pd.DataFrame()
        today_total = 0
        today_bills = 0
        today_items = 0
        today_profit = 0

    # Today's expenses (computed either way, so net profit is always defined)
    conn = get_connection()
    today_expense_result = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(date) = ?
        """,
        (today.strftime("%Y-%m-%d"),),
    ).fetchone()
    conn.close()

    today_expenses = float(today_expense_result[0] or 0)
    today_net_profit = today_profit - today_expenses

    # ------------------------------------------------------
    # INVENTORY DATA
    # ------------------------------------------------------
    if not inventory.empty:
        total_products = len(inventory)
        total_stock = inventory["stock"].sum()
        low_stock = inventory[inventory["stock"] <= 5].copy()
        low_stock_count = len(low_stock)
        inventory_purchase_value = (inventory["purchase_price"] * inventory["stock"]).sum()
        inventory_selling_value = (inventory["price"] * inventory["stock"]).sum()
    else:
        total_products = 0
        total_stock = 0
        low_stock = pd.DataFrame()
        low_stock_count = 0
        inventory_purchase_value = 0
        inventory_selling_value = 0

    # ------------------------------------------------------
    # SALES DATE FILTER
    # ------------------------------------------------------
    st.subheader("📅 Sales Date Filter")

    filter_type = st.selectbox(
        "Select Date Range",
        ["Today", "Yesterday", "This Week", "This Month", "Custom Range"],
        key="dashboard_filter_type",
    )

    if filter_type == "Today":
        start_date = today
        end_date = today

    elif filter_type == "Yesterday":
        start_date = today - timedelta(days=1)
        end_date = start_date

    elif filter_type == "This Week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today

    elif filter_type == "This Month":
        start_date = today.replace(day=1)
        end_date = today

    else:
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            start_date = st.date_input("From Date", value=today, key="dashboard_custom_start")
        with fcol2:
            end_date = st.date_input("To Date", value=today, key="dashboard_custom_end")

    if start_date > end_date:
        st.error("❌ From Date cannot be after To Date.")
        st.stop()

    if not sales.empty:
        filtered_sales = sales[
            (sales["date"].dt.date >= start_date)
            & (sales["date"].dt.date <= end_date)
        ].copy()
    else:
        filtered_sales = pd.DataFrame()

    if not filtered_sales.empty:
        filtered_total = filtered_sales["total"].sum()
        filtered_bills = filtered_sales["bill_id"].nunique()
        filtered_items = filtered_sales["quantity"].sum()
        filtered_profit = filtered_sales["profit"].sum()
    else:
        filtered_total = 0
        filtered_bills = 0
        filtered_items = 0
        filtered_profit = 0

    st.divider()

    st.subheader(
        f"📊 Sales Overview ({start_date.strftime('%d-%m-%Y')} → "
        f"{end_date.strftime('%d-%m-%Y')})"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Sales", f"₹{filtered_total:,.2f}")
    c2.metric("🧾 Bills", filtered_bills)
    c3.metric("📦 Items Sold", int(filtered_items))
    c4.metric("📈 Profit", f"₹{filtered_profit:,.2f}")

    st.divider()

    st.subheader("📅 Today's Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Today's Sales", f"₹{today_total:,.2f}")
    c2.metric("🧾 Bills", today_bills)
    c3.metric("📦 Items Sold", int(today_items))
    c4.metric("💵 Net Profit", f"₹{today_net_profit:,.2f}")

    st.divider()

    st.subheader("🏪 Business Snapshot")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛒 Products", total_products)
    c2.metric("📦 Total Stock", int(total_stock))
    c3.metric("⚠️ Low Stock", low_stock_count)
    c4.metric("💵 Stock Value", f"₹{inventory_selling_value:,.2f}")

    st.divider()

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("⚠️ Stock Alerts")

        if not low_stock.empty:
            st.warning(f"{low_stock_count} product(s) have low stock.")

            display = low_stock[["product", "stock", "price"]].copy()
            display.columns = ["Product", "Stock", "Selling Price"]

            st.dataframe(display, width="stretch", hide_index=True)

        elif not inventory.empty:
            st.success("✅ All products have sufficient stock.")

        else:
            st.info("No inventory products available.")

    with right_col:
        st.subheader("💳 Today's Payments")

        if not today_sales.empty:
            payment_summary = (
                today_sales.groupby("payment_method")["total"].sum().reset_index()
            )
            payment_summary.columns = ["Payment Method", "Amount"]

            st.bar_chart(payment_summary, x="Payment Method", y="Amount")
        else:
            st.info("No payments recorded today.")

    st.divider()

    st.subheader("🧾 Recent Sales")

    if not sales.empty:
        recent = sales[
            ["bill_id", "product", "quantity", "total", "payment_method", "date"]
        ].head(10).copy()

        recent["date"] = recent["date"].dt.strftime("%d-%m-%Y %H:%M")
        recent.columns = ["Bill ID", "Product", "Quantity", "Amount", "Payment", "Date"]

        st.dataframe(recent, width="stretch", hide_index=True)
    else:
        st.info("📭 No sales have been recorded yet.")

    st.divider()

    st.subheader("📊 Sales Performance (selected range)")

    if not filtered_sales.empty:
        daily_chart(filtered_sales, "total", "Sales")
    else:
        st.info("No sales in the selected date range.")

    st.divider()

    st.subheader("📦 Inventory Value")

    if not inventory.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Purchase Value", f"₹{inventory_purchase_value:,.2f}")
        c2.metric("Selling Value", f"₹{inventory_selling_value:,.2f}")
        c3.metric(
            "Potential Profit",
            f"₹{inventory_selling_value - inventory_purchase_value:,.2f}",
        )
    else:
        st.info("No inventory data available.")

    st.divider()

    st.caption("FreshLane Supermarket • Billing & Business Management System")


# ==========================================================
# NEW BILL
# ==========================================================
elif page == "🧾 New Bill":

    st.header("🧾 Create New Bill")

    st.caption(
        "Create a customer bill, add products, "
        "choose a payment method, and generate a receipt."
    )

    show_flash()

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 👤 Customer Details")
        st.caption("Customer information is optional.")

        customer_name = st.text_input(
            "Customer Name",
            placeholder="Enter customer name",
            key="bill_customer_name",
        )

        customer_phone = st.text_input(
            "Customer Phone",
            placeholder="Enter phone number",
            key="bill_customer_phone",
        )

    with col2:
        st.markdown("### 💳 Payment Details")
        st.caption("Choose how the customer is paying.")

        payment_method = st.selectbox(
            "Payment Method",
            ["Cash", "UPI", "Card"],
            key="bill_payment_method",
        )

    if "cart" not in st.session_state:
        st.session_state.cart = []

    inventory = load_inventory()

    product = "Select a product"
    price = 0.0
    stock = 0

    if not inventory.empty:
        product = st.selectbox(
            "Product",
            ["Select a product"] + inventory["product"].tolist(),
        )

        if product != "Select a product":
            selected = inventory[inventory["product"] == product].iloc[0]
            price = float(selected["price"])
            stock = int(selected["stock"])

            st.write(f"💰 Price: ₹{price:.2f}")
            st.write(f"📦 Available stock: {stock}")
    else:
        st.warning(
            "No products in inventory yet. "
            "Go to 📦 Inventory and add products first."
        )

    quantity = st.number_input("Quantity", min_value=1, value=1, step=1)

    if st.button("➕ Add to Cart"):

        if product == "Select a product":
            st.warning("Please select a product.")

        elif stock <= 0:
            st.error(f"❌ {product} is out of stock!")

        elif quantity > stock:
            st.error(f"❌ Only {stock} units of {product} are available.")

        else:
            existing_item = next(
                (i for i in st.session_state.cart if i["Product"] == product),
                None,
            )

            if existing_item:
                new_quantity = existing_item["Quantity"] + quantity

                if new_quantity > stock:
                    st.error(f"❌ Only {stock} units of {product} are available.")
                else:
                    existing_item["Quantity"] = new_quantity
                    existing_item["Price"] = price
                    existing_item["Total"] = price * new_quantity
                    st.success(f"✅ {product} quantity updated!")

            else:
                st.session_state.cart.append(
                    {
                        "Product": product,
                        "Price": price,
                        "Quantity": int(quantity),
                        "Total": price * quantity,
                    }
                )
                st.success(f"✅ {product} added to cart!")

    if st.button("🗑️ Clear Bill"):
        st.session_state.cart = []
        st.session_state.pop("receipt", None)
        st.rerun()

    # ------------------------------------------------------
    # CURRENT BILL
    # ------------------------------------------------------
    if st.session_state.cart:

        st.divider()

        st.header("🧾 Current Bill")

        df = pd.DataFrame(st.session_state.cart)

        st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("🗑️ Remove Item")

        remove_product = st.selectbox(
            "Select item to remove",
            [i["Product"] for i in st.session_state.cart],
            key="remove_product",
        )

        if st.button("❌ Remove Selected Item"):
            st.session_state.cart = [
                i for i in st.session_state.cart if i["Product"] != remove_product
            ]
            flash(f"✅ {remove_product} removed.")
            st.rerun()

        grand_total = df["Total"].sum()

        st.subheader(f"Grand Total: ₹{grand_total:.2f}")

        # --------------------------------------------------
        # SAVE SALE
        # --------------------------------------------------
        if st.button("💾 Save Sale"):

            conn = get_connection()
            stock_error = None

            # Verify stock again before saving
            for item in st.session_state.cart:
                result = conn.execute(
                    "SELECT stock FROM inventory WHERE product = ?",
                    (item["Product"],),
                ).fetchone()

                if result is None:
                    stock_error = f"{item['Product']} is not in inventory."
                    break

                if item["Quantity"] > int(result[0]):
                    stock_error = (
                        f"Not enough stock for {item['Product']}. "
                        f"Available: {int(result[0])}"
                    )
                    break

            if stock_error:
                conn.close()
                st.error(f"❌ {stock_error}")

            else:
                now = datetime.now()
                bill_id = now.strftime("BILL-%Y%m%d-%H%M%S-%f")
                sale_time = now.strftime("%Y-%m-%d %H:%M:%S")

                cart_for_receipt = [item.copy() for item in st.session_state.cart]

                try:
                    for item in st.session_state.cart:
                        row = conn.execute(
                            "SELECT purchase_price FROM inventory WHERE product = ?",
                            (item["Product"],),
                        ).fetchone()

                        item_purchase_price = (
                            float(row[0]) if row and row[0] is not None else 0.0
                        )

                        conn.execute(
                            """
                            INSERT INTO sales
                            (bill_id, customer_name, customer_phone, product, price,
                             purchase_price, quantity, total, date, payment_method)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                bill_id,
                                customer_name.strip(),
                                customer_phone.strip(),
                                item["Product"],
                                item["Price"],
                                item_purchase_price,
                                item["Quantity"],
                                item["Total"],
                                sale_time,
                                payment_method,
                            ),
                        )

                        conn.execute(
                            "UPDATE inventory SET stock = stock - ? WHERE product = ?",
                            (item["Quantity"], item["Product"]),
                        )

                    conn.commit()

                except Exception as e:
                    conn.rollback()
                    conn.close()
                    st.error(f"❌ Could not save sale: {e}")
                    st.stop()

                conn.close()

                st.session_state.receipt = build_receipt(
                    bill_id=bill_id,
                    date_text=sale_time,
                    customer=customer_name.strip() or "Walk-in Customer",
                    phone=customer_phone.strip() or "N/A",
                    payment=payment_method,
                    items=[
                        (i["Product"], i["Quantity"], i["Total"])
                        for i in cart_for_receipt
                    ],
                    grand_total=grand_total,
                )

                st.session_state.cart = []

                flash(f"✅ Sale saved! {bill_id}")

                st.rerun()

    else:
        st.info("Your bill is empty.")

    # ------------------------------------------------------
    # RECEIPT
    # ------------------------------------------------------
    if "receipt" in st.session_state:

        st.divider()

        st.header("🧾 Receipt")

        st.code(st.session_state.receipt, language="text")

        st.download_button(
            label="📥 Download Receipt",
            data=st.session_state.receipt,
            file_name="receipt.txt",
            mime="text/plain",
        )

        show_html(printable_html(st.session_state.receipt), height=700)


# ==========================================================
# ACCOUNTS
# ==========================================================
elif page == "📊 Accounts":

    st.header("📊 Accounts Dashboard")

    show_flash()

    sales = load_sales()

    if not sales.empty:

        today = datetime.now().date()

        today_sales = sales[sales["date"].dt.date == today]

        st.subheader("📅 Today's Overview")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Today's Sales", f"₹{today_sales['total'].sum():,.2f}")
        c2.metric("🧾 Bills", today_sales["bill_id"].nunique())
        c3.metric("📦 Items Sold", int(today_sales["quantity"].sum()))
        c4.metric("📈 Today's Profit", f"₹{today_sales['profit'].sum():,.2f}")

        st.divider()

        st.subheader("📊 Overall Business")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Total Sales", f"₹{sales['total'].sum():,.2f}")
        c2.metric("🧾 Total Bills", sales["bill_id"].nunique())
        c3.metric("📦 Total Items Sold", int(sales["quantity"].sum()))
        c4.metric("📈 Total Profit", f"₹{sales['profit'].sum():,.2f}")

        st.divider()

        st.subheader("💳 Payment Methods")

        payment_summary = (
            sales.groupby("payment_method")
            .agg(Amount=("total", "sum"), Transactions=("bill_id", "nunique"))
            .reset_index()
        )
        payment_summary.columns = ["Payment Method", "Amount", "Bills"]

        st.dataframe(payment_summary, width="stretch", hide_index=True)

        st.divider()

        st.subheader("📋 Sales History")

        st.dataframe(
            sales.drop(columns=["profit"]),
            width="stretch",
            hide_index=True,
        )

        st.divider()

        # --------------------------------------------------
        # SALES RECORD MANAGEMENT
        # --------------------------------------------------
        st.subheader("🛠️ Sales Record Management")

        sale_options = sales[["id", "bill_id", "product", "quantity", "total", "date"]].copy()

        sale_options["display"] = (
            "#" + sale_options["id"].astype(str)
            + " • " + sale_options["bill_id"].astype(str)
            + " • " + sale_options["product"].astype(str)
            + " • Qty: " + sale_options["quantity"].astype(str)
        )

        selected_sale = st.selectbox(
            "Select a sale record",
            sale_options["display"].tolist(),
            key="selected_sale_record",
        )

        sale_id = int(sale_options[sale_options["display"] == selected_sale].iloc[0]["id"])

        st.warning(
            "⚠️ Deleting a sale will restore the sold quantity back to inventory."
        )

        confirm_sale_delete = st.checkbox(
            "Yes, I want to delete this sale record",
            key="confirm_sale_delete",
        )

        if st.button("🗑️ Delete Selected Sale", disabled=not confirm_sale_delete):

            conn = get_connection()

            try:
                sale = conn.execute(
                    "SELECT product, quantity FROM sales WHERE id = ?",
                    (sale_id,),
                ).fetchone()

                if sale:
                    product_name = sale[0]
                    quantity_sold = int(sale[1])

                    conn.execute(
                        "UPDATE inventory SET stock = stock + ? WHERE product = ?",
                        (quantity_sold, product_name),
                    )

                    conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))

                    conn.commit()

                    st.session_state.pop("confirm_sale_delete", None)

                    flash(
                        f"✅ Sale record deleted and {quantity_sold} unit(s) of "
                        f"{product_name} returned to stock."
                    )

                    st.rerun()

                else:
                    st.error("❌ Sale record could not be found.")

            except Exception as e:
                conn.rollback()
                st.error(f"❌ Could not delete sale: {e}")

            finally:
                conn.close()

    else:
        st.info("📭 No sales have been recorded yet.")

    st.divider()

    st.subheader("🔎 Search Previous Bills")

    bill_search = st.text_input(
        "Search by Bill ID, Customer Name or Phone",
        placeholder="Example: BILL-20260928 or customer name",
        key="bill_search",
    )

    if bill_search.strip():

        search_text = bill_search.strip().lower()

        bill_results = sales[
            sales["bill_id"].fillna("").astype(str).str.lower().str.contains(search_text, regex=False)
            | sales["customer_name"].fillna("").astype(str).str.lower().str.contains(search_text, regex=False)
            | sales["customer_phone"].fillna("").astype(str).str.contains(search_text, regex=False)
        ].copy()

        if not bill_results.empty:

            st.success(f"Found {bill_results['bill_id'].nunique()} matching bill(s).")

            bill_display = bill_results[
                [
                    "bill_id",
                    "customer_name",
                    "customer_phone",
                    "product",
                    "quantity",
                    "total",
                    "payment_method",
                    "date",
                ]
            ].copy()

            bill_display["date"] = pd.to_datetime(
                bill_display["date"], errors="coerce"
            ).dt.strftime("%d-%m-%Y %H:%M")

            bill_display.columns = [
                "Bill ID",
                "Customer",
                "Phone",
                "Product",
                "Quantity",
                "Amount",
                "Payment",
                "Date",
            ]

            st.dataframe(bill_display, width="stretch", hide_index=True)

        else:
            st.warning("🔎 No matching bills found.")

    else:
        st.caption("Enter a Bill ID, customer name or phone number to search.")


# ==========================================================
# PURCHASES
# ==========================================================
elif page == "💰 Purchases":

    st.header("💰 Purchase Management")

    show_flash()

    st.subheader("➕ Record New Purchase")

    with st.form("purchase_form", clear_on_submit=True):

        purchase_product = st.text_input("Product Name")

        purchase_quantity = st.number_input(
            "Quantity Purchased", min_value=1, value=1, step=1
        )

        purchase_price = st.number_input(
            "Purchase Price per Unit (₹)", min_value=0.0, value=0.0, step=0.50
        )

        selling_price = st.number_input(
            "Selling Price per Unit (₹) — used only for NEW products",
            min_value=0.0,
            value=0.0,
            step=0.50,
        )

        supplier = st.text_input("Supplier Name (Optional)")

        submitted = st.form_submit_button("💾 Save Purchase")

    if submitted:

        product_clean = purchase_product.strip()
        purchase_total = purchase_quantity * purchase_price

        if not product_clean:
            st.warning("Please enter the product name.")

        elif purchase_price <= 0:
            st.warning("Purchase price must be greater than zero.")

        else:
            conn = get_connection()

            try:
                purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    """
                    INSERT INTO purchases
                    (product, quantity, purchase_price, total, supplier, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_clean,
                        int(purchase_quantity),
                        purchase_price,
                        purchase_total,
                        supplier.strip(),
                        purchase_date,
                    ),
                )

                existing = conn.execute(
                    "SELECT product FROM inventory WHERE product = ? COLLATE NOCASE",
                    (product_clean,),
                ).fetchone()

                if existing:
                    conn.execute(
                        """
                        UPDATE inventory
                        SET stock = stock + ?, purchase_price = ?
                        WHERE product = ? COLLATE NOCASE
                        """,
                        (int(purchase_quantity), purchase_price, product_clean),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO inventory (product, purchase_price, price, stock)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            product_clean,
                            purchase_price,
                            selling_price if selling_price > 0 else purchase_price,
                            int(purchase_quantity),
                        ),
                    )

                conn.commit()

                st.success(
                    f"✅ Purchase recorded! {int(purchase_quantity)} units added "
                    f"to stock (total cost ₹{purchase_total:,.2f})."
                )

                if not existing and selling_price <= 0:
                    st.info(
                        "ℹ️ Selling price was set equal to purchase price. "
                        "Update it in 📦 Inventory if needed."
                    )

            except Exception as e:
                conn.rollback()
                st.error(f"❌ Could not save purchase: {e}")

            finally:
                conn.close()

    st.divider()

    st.subheader("📋 Purchase History")

    conn = get_connection()
    purchases = pd.read_sql_query(
        "SELECT * FROM purchases ORDER BY id DESC", conn
    )
    conn.close()

    if not purchases.empty:

        st.dataframe(purchases, width="stretch", hide_index=True)

        st.divider()

        st.subheader("📥 Export Purchase Report")

        purchase_csv = purchases.to_csv(index=False)

        st.download_button(
            label="📥 Download Purchase Report (CSV)",
            data=purchase_csv,
            file_name="purchase_report.csv",
            mime="text/csv",
        )

        st.metric("💰 Total Purchases", f"₹{purchases['total'].sum():,.2f}")

        # --------------------------------------------------
        # PURCHASE RECORD MANAGEMENT
        # --------------------------------------------------
        st.divider()

        st.subheader("🛠️ Purchase Record Management")

        purchase_options = purchases[
            ["id", "product", "quantity", "purchase_price", "total", "supplier", "date"]
        ].copy()

        purchase_options["display"] = (
            "#" + purchase_options["id"].astype(str)
            + " • " + purchase_options["product"].astype(str)
            + " • Qty: " + purchase_options["quantity"].astype(str)
            + " • ₹" + purchase_options["total"].map(lambda x: f"{x:.2f}")
        )

        selected_purchase = st.selectbox(
            "Select a purchase record",
            purchase_options["display"].tolist(),
            key="selected_purchase_record",
        )

        purchase_id = int(
            purchase_options[purchase_options["display"] == selected_purchase]
            .iloc[0]["id"]
        )

        st.warning(
            "⚠️ Deleting this purchase will remove the purchased quantity from inventory."
        )

        confirm_purchase_delete = st.checkbox(
            "Yes, I want to delete this purchase record",
            key="confirm_purchase_delete",
        )

        if st.button("🗑️ Delete Selected Purchase", disabled=not confirm_purchase_delete):

            conn = get_connection()

            try:
                purchase = conn.execute(
                    "SELECT product, quantity FROM purchases WHERE id = ?",
                    (purchase_id,),
                ).fetchone()

                if purchase:
                    product_name = purchase[0]
                    quantity_purchased = int(purchase[1])

                    inventory_row = conn.execute(
                        "SELECT stock FROM inventory WHERE product = ? COLLATE NOCASE",
                        (product_name,),
                    ).fetchone()

                    if inventory_row is None:
                        st.error("❌ Product was not found in inventory.")

                    elif int(inventory_row[0]) < quantity_purchased:
                        st.error(
                            "❌ This purchase cannot be deleted because some of "
                            "its stock has already been sold or removed."
                        )

                    else:
                        conn.execute(
                            """
                            UPDATE inventory
                            SET stock = stock - ?
                            WHERE product = ? COLLATE NOCASE
                            """,
                            (quantity_purchased, product_name),
                        )

                        conn.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))

                        conn.commit()

                        st.session_state.pop("confirm_purchase_delete", None)

                        flash(
                            f"✅ Purchase deleted and {quantity_purchased} unit(s) "
                            f"of {product_name} removed from stock."
                        )

                        st.rerun()

                else:
                    st.error("❌ Purchase record could not be found.")

            except Exception as e:
                conn.rollback()
                st.error(f"❌ Could not delete purchase: {e}")

            finally:
                conn.close()

    else:
        st.info("No purchases have been recorded yet.")


# ==========================================================
# EXPENSES
# ==========================================================
elif page == "💸 Expenses":

    st.header("💸 Expense Management")

    show_flash()

    st.caption(
        "Record and manage business expenses such as rent, electricity, "
        "salaries, transport and maintenance."
    )

    st.divider()

    # ------------------------------------------------------
    # ADD EXPENSE
    # ------------------------------------------------------
    st.subheader("➕ Record New Expense")

    expense_categories = [
        "Rent",
        "Electricity",
        "Salaries",
        "Transport",
        "Internet",
        "Maintenance",
        "Other",
    ]

    with st.form("expense_form", clear_on_submit=True):

        expense_category = st.selectbox("Expense Category", expense_categories)

        expense_amount = st.number_input(
            "Amount (₹)", min_value=0.0, value=0.0, step=100.0
        )

        expense_description = st.text_input(
            "Description", placeholder="Example: September electricity bill"
        )

        expense_date = st.date_input("Expense Date", value=datetime.now().date())

        save_expense = st.form_submit_button("💾 Save Expense")

    if save_expense:

        if expense_amount <= 0:
            st.warning("⚠️ Expense amount must be greater than zero.")

        else:
            conn = get_connection()

            try:
                expense_datetime = (
                    expense_date.strftime("%Y-%m-%d")
                    + " "
                    + datetime.now().strftime("%H:%M:%S")
                )

                conn.execute(
                    """
                    INSERT INTO expenses (category, amount, description, date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        expense_category,
                        expense_amount,
                        expense_description.strip(),
                        expense_datetime,
                    ),
                )

                conn.commit()

                flash(f"✅ Expense recorded: ₹{expense_amount:,.2f}")

                st.rerun()

            except Exception as e:
                conn.rollback()
                st.error(f"❌ Could not save expense: {e}")

            finally:
                conn.close()

    st.divider()

    # ------------------------------------------------------
    # EXPENSE SUMMARY
    # ------------------------------------------------------
    st.subheader("📊 Expense Summary")

    conn = get_connection()
    expenses = pd.read_sql_query(
        "SELECT * FROM expenses ORDER BY date DESC", conn
    )
    conn.close()

    if not expenses.empty:

        expenses["date"] = pd.to_datetime(expenses["date"], errors="coerce")

        total_expenses = expenses["amount"].sum()

        today = datetime.now().date()
        today_expenses_df = expenses[expenses["date"].dt.date == today]
        today_total = today_expenses_df["amount"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("💸 Total Expenses", f"₹{total_expenses:,.2f}")
        c2.metric("📅 Today's Expenses", f"₹{today_total:,.2f}")
        c3.metric("🧾 Expense Records", len(expenses))

        st.divider()

        # --------------------------------------------------
        # CATEGORY SUMMARY
        # --------------------------------------------------
        st.subheader("📊 Expenses by Category")

        category_summary = (
            expenses.groupby("category")["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )
        category_summary.columns = ["Category", "Amount"]

        st.bar_chart(category_summary, x="Category", y="Amount")
        st.dataframe(category_summary, width="stretch", hide_index=True)

        st.divider()

        # --------------------------------------------------
        # EXPENSE HISTORY
        # --------------------------------------------------
        st.subheader("📋 Expense History")

        expense_display = expenses.copy()
        expense_display["date"] = expense_display["date"].dt.strftime("%d-%m-%Y %H:%M")
        expense_display.columns = ["ID", "Category", "Amount", "Description", "Date"]

        st.dataframe(expense_display, width="stretch", hide_index=True)

        st.divider()

        # --------------------------------------------------
        # EXPORT
        # --------------------------------------------------
        st.subheader("📥 Export Expense Report")

        expense_csv = expense_display.to_csv(index=False)

        st.download_button(
            label="📥 Download Expense Report (CSV)",
            data=expense_csv,
            file_name="expense_report.csv",
            mime="text/csv",
        )

    else:
        st.info("📭 No expenses recorded yet. Add your first business expense above.")


# ==========================================================
# INVENTORY
# ==========================================================
elif page == "📦 Inventory":

    st.header("📦 Inventory Management")

    show_flash()

    st.subheader("➕ Add New Product")

    with st.form("add_product_form", clear_on_submit=True):

        product_name = st.text_input("Product name")

        inventory_purchase_price = st.number_input(
            "Purchase Price (₹)", min_value=0.0, value=0.0, step=1.0
        )

        product_price = st.number_input(
            "Selling Price (₹)", min_value=0.0, value=0.0, step=1.0
        )

        product_stock = st.number_input(
            "Stock quantity", min_value=0, value=0, step=1
        )

        add_clicked = st.form_submit_button("➕ Add Product")

    if add_clicked:

        product_clean = product_name.strip()

        if not product_clean:
            st.warning("Please enter a product name.")

        elif inventory_purchase_price <= 0:
            st.warning("Purchase price must be greater than zero.")

        elif product_price <= 0:
            st.warning("Selling price must be greater than zero.")

        elif inventory_purchase_price > product_price:
            st.warning("⚠️ Purchase price is higher than selling price.")

        else:
            conn = get_connection()

            try:
                duplicate = conn.execute(
                    "SELECT 1 FROM inventory WHERE product = ? COLLATE NOCASE",
                    (product_clean,),
                ).fetchone()

                if duplicate:
                    st.error("❌ This product already exists.")
                else:
                    conn.execute(
                        """
                        INSERT INTO inventory (product, purchase_price, price, stock)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            product_clean,
                            inventory_purchase_price,
                            product_price,
                            int(product_stock),
                        ),
                    )
                    conn.commit()
                    st.success(f"✅ {product_clean} added to inventory!")

            except sqlite3.IntegrityError:
                st.error("❌ This product already exists.")

            except Exception as e:
                st.error(f"❌ Could not add product: {e}")

            finally:
                conn.close()

    st.divider()

    st.subheader("📋 Current Inventory")

    inventory = load_inventory()

    if not inventory.empty:

        # --------------------------------------------------
        # SEARCH AND FILTER
        # --------------------------------------------------
        fcol1, fcol2 = st.columns(2)

        with fcol1:
            inventory_search = st.text_input(
                "🔍 Search Product",
                placeholder="Enter product name",
                key="inventory_search",
            )

        with fcol2:
            inventory_filter = st.selectbox(
                "📦 Stock Filter",
                ["All Products", "Low Stock (≤ 5)", "Out of Stock"],
                key="inventory_filter",
            )

        filtered_inventory = inventory.copy()

        if inventory_search.strip():
            filtered_inventory = filtered_inventory[
                filtered_inventory["product"]
                .fillna("")
                .str.lower()
                .str.contains(inventory_search.strip().lower(), regex=False)
            ]

        if inventory_filter == "Low Stock (≤ 5)":
            filtered_inventory = filtered_inventory[filtered_inventory["stock"] <= 5]
        elif inventory_filter == "Out of Stock":
            filtered_inventory = filtered_inventory[filtered_inventory["stock"] <= 0]

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------
        c1, c2, c3 = st.columns(3)

        c1.metric("📦 Products", len(filtered_inventory))
        c2.metric("📊 Units in Stock", int(filtered_inventory["stock"].sum()))

        stock_value = (filtered_inventory["price"] * filtered_inventory["stock"]).sum()
        c3.metric("💰 Stock Selling Value", f"₹{stock_value:,.2f}")

        st.divider()

        # --------------------------------------------------
        # TABLE + EXPORT  (columns picked by NAME so labels are
        # always correct even in databases upgraded from older versions)
        # --------------------------------------------------
        if not filtered_inventory.empty:

            display_inventory = filtered_inventory[
                ["id", "product", "purchase_price", "price", "stock"]
            ].copy()

            display_inventory.columns = [
                "ID",
                "Product",
                "Purchase Price",
                "Selling Price",
                "Stock",
            ]

            st.dataframe(display_inventory, width="stretch", hide_index=True)

            st.divider()

            st.subheader("📥 Export Inventory Report")

            inventory_export = display_inventory.copy()

            inventory_csv = inventory_export.to_csv(index=False)

            st.download_button(
                label="📥 Download Inventory Report (CSV)",
                data=inventory_csv,
                file_name="inventory_report.csv",
                mime="text/csv",
            )

        else:
            st.info("🔎 No products match your search/filter.")

        st.divider()

        # --------------------------------------------------
        # UPDATE PRODUCT
        # --------------------------------------------------
        st.subheader("✏️ Update Product")

        update_product = st.selectbox(
            "Select product",
            inventory["product"].tolist(),
            key="update_product",
        )

        row = inventory[inventory["product"] == update_product].iloc[0]

        current_stock = int(row["stock"])
        current_price = float(row["price"])
        current_purchase_price = float(row["purchase_price"])

        st.write(
            f"Current stock: **{current_stock}**  |  "
            f"Purchase price: **₹{current_purchase_price:.2f}**  |  "
            f"Selling price: **₹{current_price:.2f}**"
        )

        ucol1, ucol2, ucol3 = st.columns(3)

        with ucol1:
            new_stock = st.number_input(
                "New stock quantity",
                min_value=0,
                value=current_stock,
                step=1,
                key=f"update_stock_{update_product}",
            )

        with ucol2:
            new_purchase_price = st.number_input(
                "New purchase price (₹)",
                min_value=0.0,
                value=current_purchase_price,
                step=1.0,
                key=f"update_purchase_price_{update_product}",
            )

        with ucol3:
            new_price = st.number_input(
                "New selling price (₹)",
                min_value=0.0,
                value=current_price,
                step=1.0,
                key=f"update_price_{update_product}",
            )

        if st.button("💾 Update Product"):

            if new_price <= 0:
                st.warning("Selling price must be greater than zero.")

            else:
                conn = get_connection()

                try:
                    conn.execute(
                        """
                        UPDATE inventory
                        SET stock = ?, purchase_price = ?, price = ?
                        WHERE product = ?
                        """,
                        (
                            int(new_stock),
                            new_purchase_price,
                            new_price,
                            update_product,
                        ),
                    )
                    conn.commit()

                    flash(f"✅ {update_product} updated!")

                    st.rerun()

                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Could not update product: {e}")

                finally:
                    conn.close()

        # --------------------------------------------------
        # DELETE PRODUCT
        # --------------------------------------------------
        st.divider()

        st.subheader("🗑️ Delete Product")

        st.warning(
            "⚠️ Deleting a product removes it from current inventory. "
            "Past sales and purchase records will remain unchanged."
        )

        delete_product = st.selectbox(
            "Select product to delete",
            inventory["product"].tolist(),
            key="delete_inventory_product",
        )

        confirm_product_delete = st.checkbox(
            "Yes, I want to delete this product",
            key="confirm_product_delete",
        )

        if st.button("🗑️ Delete Selected Product", disabled=not confirm_product_delete):

            conn = get_connection()

            try:
                conn.execute(
                    "DELETE FROM inventory WHERE product = ?",
                    (delete_product,),
                )
                conn.commit()

                st.session_state.pop("confirm_product_delete", None)

                flash(f"✅ {delete_product} was removed from inventory.")

                st.rerun()

            except Exception as e:
                conn.rollback()
                st.error(f"❌ Could not delete product: {e}")

            finally:
                conn.close()

        # --------------------------------------------------
        # INVENTORY VALUE ANALYSIS
        # --------------------------------------------------
        st.divider()

        st.subheader("💰 Inventory Value Analysis")

        analysis_inventory = add_inventory_values(inventory.copy())

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "📦 Total Purchase Value",
            f"₹{analysis_inventory['Purchase Value'].sum():,.2f}",
        )
        c2.metric(
            "💰 Total Selling Value",
            f"₹{analysis_inventory['Selling Value'].sum():,.2f}",
        )
        c3.metric(
            "📈 Potential Profit",
            f"₹{analysis_inventory['Potential Profit'].sum():,.2f}",
        )

        st.subheader("📊 Product Value Details")

        value_display = analysis_inventory[
            [
                "product",
                "stock",
                "purchase_price",
                "price",
                "Purchase Value",
                "Selling Value",
                "Potential Profit",
            ]
        ].copy()

        value_display.columns = [
            "Product",
            "Stock",
            "Purchase Price",
            "Selling Price",
            "Purchase Value",
            "Selling Value",
            "Potential Profit",
        ]

        st.dataframe(value_display, width="stretch", hide_index=True)

    else:
        st.info("No products added yet. Add your first product above.")


# ==========================================================
# CUSTOMERS
# ==========================================================
elif page == "👥 Customers":

    st.header("👥 Customer Management")

    show_flash()

    conn = get_connection()

    customer_sales = pd.read_sql_query(
        """
        SELECT customer_name, customer_phone, bill_id, product, quantity, total, date
        FROM sales
        WHERE customer_phone != '' OR customer_name != ''
        ORDER BY date DESC
        """,
        conn,
    )

    conn.close()

    if customer_sales.empty:
        st.info(
            "No customer records available yet. Customer details will appear "
            "here after creating bills with customer information."
        )

    else:
        customer_summary = (
            customer_sales
            .groupby(["customer_name", "customer_phone"], dropna=False)
            .agg(
                Bills=("bill_id", "nunique"),
                Items=("quantity", "sum"),
                Total_Spent=("total", "sum"),
            )
            .reset_index()
        )

        customer_summary.columns = [
            "Customer Name",
            "Phone",
            "Bills",
            "Items Purchased",
            "Total Spent",
        ]

        st.subheader("📋 Customers")

        st.dataframe(customer_summary, width="stretch", hide_index=True)

        st.divider()

        st.subheader("📥 Export Customer Report")

        customer_csv = customer_summary.to_csv(index=False)

        st.download_button(
            label="📥 Download Customer Report (CSV)",
            data=customer_csv,
            file_name="customer_report.csv",
            mime="text/csv",
        )

        st.divider()

        # --------------------------------------------------
        # CUSTOMER DETAILS
        # --------------------------------------------------
        st.subheader("👤 Customer Details")

        summary_view = customer_summary.fillna("").copy()

        summary_view["label"] = (
            summary_view["Customer Name"].replace("", "(No name)")
            + " • "
            + summary_view["Phone"].replace("", "(No phone)")
        )

        selected_customer = st.selectbox(
            "Select a customer",
            summary_view["label"].tolist(),
            key="selected_customer",
        )

        selected_row = summary_view[summary_view["label"] == selected_customer].iloc[0]

        d1, d2, d3 = st.columns(3)
        d1.metric("🧾 Total Bills", int(selected_row["Bills"]))
        d2.metric("📦 Items Purchased", int(selected_row["Items Purchased"]))
        d3.metric("💰 Total Spent", f"₹{selected_row['Total Spent']:,.2f}")

        cs = customer_sales.fillna({"customer_name": "", "customer_phone": ""})

        customer_history = cs[
            (cs["customer_name"] == selected_row["Customer Name"])
            & (cs["customer_phone"] == selected_row["Phone"])
        ][["bill_id", "product", "quantity", "total", "date"]].copy()

        customer_history["date"] = pd.to_datetime(
            customer_history["date"], errors="coerce"
        ).dt.strftime("%d-%m-%Y %H:%M")

        customer_history.columns = ["Bill ID", "Product", "Quantity", "Amount", "Date"]

        st.dataframe(customer_history, width="stretch", hide_index=True)

        st.divider()

        st.subheader("🔍 Search Customer")

        search = st.text_input(
            "Enter customer name or phone number",
            placeholder="Example: 9876543210",
        )

        if search.strip():

            search_text = search.strip().lower()

            results = customer_sales[
                customer_sales["customer_name"]
                .fillna("")
                .str.lower()
                .str.contains(search_text, regex=False)
                | customer_sales["customer_phone"]
                .fillna("")
                .str.contains(search_text, regex=False)
            ]

            if not results.empty:

                st.success(f"Found {results['bill_id'].nunique()} bill(s).")

                c1, c2, c3 = st.columns(3)
                c1.metric("🧾 Bills", results["bill_id"].nunique())
                c2.metric("📦 Items Purchased", int(results["quantity"].sum()))
                c3.metric("💰 Total Spent", f"₹{results['total'].sum():,.2f}")

                st.divider()

                st.subheader("🛍️ Purchase History")

                history = results.copy()

                history["date"] = pd.to_datetime(
                    history["date"], errors="coerce"
                ).dt.strftime("%d-%m-%Y %H:%M")

                history.columns = [
                    "Customer",
                    "Phone",
                    "Bill ID",
                    "Product",
                    "Quantity",
                    "Amount",
                    "Date",
                ]

                st.dataframe(history, width="stretch", hide_index=True)

            else:
                st.warning("No customer found matching your search.")

        else:
            st.caption(
                "Enter a name or phone number to view a customer's purchase history."
            )


# ==========================================================
# BILL HISTORY
# ==========================================================
elif page == "🧾 Bill History":

    st.header("🧾 Bill History")

    st.caption(
        "Search and view previous bills, customer details, "
        "products, payments and totals."
    )

    show_flash()

    sales = load_sales(order="date DESC")

    if sales.empty:
        st.info("📭 No bills have been recorded yet.")

    else:
        st.subheader("🔍 Search Bills")

        search_text = st.text_input(
            "Search by Bill ID, Customer Name or Phone",
            placeholder="Example: BILL-20260928 or customer name",
        )

        if search_text.strip():
            search = search_text.strip().lower()

            filtered = sales[
                sales["bill_id"].fillna("").str.lower().str.contains(search, regex=False)
                | sales["customer_name"].str.lower().str.contains(search, regex=False)
                | sales["customer_phone"].str.contains(search, regex=False)
            ].copy()
        else:
            filtered = sales.copy()

        c1, c2, c3 = st.columns(3)
        c1.metric("🧾 Bills Found", filtered["bill_id"].nunique())
        c2.metric("📦 Items", int(filtered["quantity"].sum()))
        c3.metric("💰 Total Amount", f"₹{filtered['total'].sum():,.2f}")

        st.divider()

        st.subheader("📋 Bills")

        if filtered.empty:
            st.warning("❌ No bills found matching your search.")

        else:
            bill_summary = (
                filtered
                .groupby("bill_id")
                .agg(
                    Customer=("customer_name", "first"),
                    Phone=("customer_phone", "first"),
                    Items=("quantity", "sum"),
                    Total=("total", "sum"),
                    Payment=("payment_method", "first"),
                    Date=("date", "first"),
                )
                .reset_index()
                .sort_values("Date", ascending=False)   # newest bill first
            )

            bill_summary["Customer"] = bill_summary["Customer"].replace("", "Walk-in Customer")
            bill_summary["Phone"] = bill_summary["Phone"].replace("", "N/A")
            bill_summary["Date"] = bill_summary["Date"].dt.strftime("%d-%m-%Y %H:%M")

            bill_summary.columns = [
                "Bill ID",
                "Customer",
                "Phone",
                "Items",
                "Total",
                "Payment",
                "Date",
            ]

            st.dataframe(bill_summary, width="stretch", hide_index=True)

            st.divider()

            # --------------------------------------------------
            # VIEW INDIVIDUAL BILL
            # --------------------------------------------------
            st.subheader("🔎 View Bill Details")

            selected_bill = st.selectbox(
                "Select a Bill",
                bill_summary["Bill ID"].tolist(),
                key="history_selected_bill",
            )

            selected_bill_data = filtered[filtered["bill_id"] == selected_bill].copy()

            if not selected_bill_data.empty:

                first_row = selected_bill_data.iloc[0]

                customer = first_row["customer_name"] or "Walk-in Customer"
                phone = first_row["customer_phone"] or "N/A"
                payment = first_row["payment_method"]

                bill_date = first_row["date"]
                date_display = (
                    bill_date.strftime("%d-%m-%Y %H:%M") if pd.notna(bill_date) else "N/A"
                )
                date_full = (
                    bill_date.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(bill_date) else "N/A"
                )

                st.markdown(f"### 🧾 {selected_bill}")

                st.markdown(
                    f"**Customer:** {customer}  \n"
                    f"**Phone:** {phone}  \n"
                    f"**Payment:** {payment}  \n"
                    f"**Date:** {date_display}"
                )

                st.divider()

                bill_items = selected_bill_data[
                    ["product", "price", "quantity", "total"]
                ].copy()

                bill_items.columns = ["Product", "Price", "Quantity", "Amount"]

                st.dataframe(bill_items, width="stretch", hide_index=True)

                bill_total = bill_items["Amount"].sum()

                st.markdown(f"### 💰 Grand Total: ₹{bill_total:,.2f}")

                st.divider()

                old_receipt = build_receipt(
                    bill_id=selected_bill,
                    date_text=date_full,
                    customer=customer,
                    phone=phone,
                    payment=payment,
                    items=[
                        (r["product"], r["quantity"], r["total"])
                        for _, r in selected_bill_data.iterrows()
                    ],
                    grand_total=bill_total,
                )

                st.download_button(
                    label="📥 Download This Bill",
                    data=old_receipt,
                    file_name=f"{selected_bill}.txt",
                    mime="text/plain",
                )

                # --------------------------------------------------
                # PRINT / REPRINT BILL
                # --------------------------------------------------
                st.markdown("### 🖨️ Print Bill")

                show_html(printable_html(old_receipt), height=700)

        st.divider()

        st.caption("FreshLane Supermarket • Business Reports")


# ==========================================================
# REPORTS
# ==========================================================
elif page == "📈 Reports":

    st.header("📈 Business Reports")

    show_flash()

    sales = load_sales(order="date DESC")
    inventory = load_inventory()

    # ------------------------------------------------------
    # REPORT DATE FILTER
    # ------------------------------------------------------
    st.subheader("📅 Report Date Range")

    report_col1, report_col2 = st.columns(2)

    with report_col1:
        report_start = st.date_input(
            "From Date",
            value=datetime.now().date(),
            key="report_start_date",
        )

    with report_col2:
        report_end = st.date_input(
            "To Date",
            value=datetime.now().date(),
            key="report_end_date",
        )

    if report_start > report_end:
        st.error("❌ From Date cannot be after To Date.")
        st.stop()

    if not sales.empty:
        report_sales = sales[
            (sales["date"].dt.date >= report_start)
            & (sales["date"].dt.date <= report_end)
        ].copy()
    else:
        report_sales = pd.DataFrame()

    st.divider()

    st.subheader(
        f"📊 Report Overview "
        f"({report_start.strftime('%d-%m-%Y')} → "
        f"{report_end.strftime('%d-%m-%Y')})"
    )

    if not report_sales.empty:
        report_total = report_sales["total"].sum()
        report_gross_profit = report_sales["profit"].sum()
        report_bills = report_sales["bill_id"].nunique()
        report_items = report_sales["quantity"].sum()
    else:
        report_total = 0
        report_gross_profit = 0
        report_bills = 0
        report_items = 0

    # ------------------------------------------------------
    # EXPENSES FOR SELECTED REPORT DATE RANGE
    # ------------------------------------------------------
    conn = get_connection()

    report_expense_result = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(date) >= ?
          AND date(date) <= ?
        """,
        (
            report_start.strftime("%Y-%m-%d"),
            report_end.strftime("%Y-%m-%d"),
        ),
    ).fetchone()

    conn.close()

    report_expenses = float(report_expense_result[0] or 0)
    report_net_profit = report_gross_profit - report_expenses

    report_net_margin = (
        (report_net_profit / report_total) * 100
        if report_total > 0
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Sales", f"₹{report_total:,.2f}")
    c2.metric("📈 Gross Profit", f"₹{report_gross_profit:,.2f}")
    c3.metric("💸 Expenses", f"₹{report_expenses:,.2f}")
    c4.metric("💵 Net Profit", f"₹{report_net_profit:,.2f}")

    st.caption(f"Net profit margin: {report_net_margin:.1f}%")

    st.divider()

    c1, c2 = st.columns(2)
    c1.metric("🧾 Bills", report_bills)
    c2.metric("📦 Items Sold", int(report_items))

    st.divider()

    def inventory_value_section(inventory, show_table):

        st.subheader("📦 Inventory Value")

        if inventory.empty:
            st.info("No inventory data available.")
            return

        inventory = add_inventory_values(inventory.copy())

        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Stock Purchase Value", f"₹{inventory['Purchase Value'].sum():,.2f}")
        c2.metric("💰 Stock Selling Value", f"₹{inventory['Selling Value'].sum():,.2f}")
        c3.metric("📈 Potential Profit", f"₹{inventory['Potential Profit'].sum():,.2f}")

        if show_table:
            st.dataframe(
                inventory[
                    [
                        "product",
                        "stock",
                        "purchase_price",
                        "price",
                        "Purchase Value",
                        "Selling Value",
                        "Potential Profit",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

    if sales.empty:

        st.info(
            "No sales data available yet. Create some bills to see your reports."
        )

        if not inventory.empty:
            inventory_value_section(inventory, show_table=False)

    else:

        now = datetime.now()
        today = now.date()

        today_sales = sales[sales["date"].dt.date == today]

        month_sales = sales[
            (sales["date"].dt.month == now.month)
            & (sales["date"].dt.year == now.year)
        ]

        today_total = today_sales["total"].sum()
        today_profit = today_sales["profit"].sum()

        month_total = month_sales["total"].sum()
        month_profit = month_sales["profit"].sum()

        today_margin = (today_profit / today_total * 100) if today_total > 0 else 0
        month_margin = (month_profit / month_total * 100) if month_total > 0 else 0

        st.subheader("📅 Today's Performance")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Today's Sales", f"₹{today_total:,.2f}")
        c2.metric("📈 Today's Profit", f"₹{today_profit:,.2f}")
        c3.metric("🧾 Bills Today", today_sales["bill_id"].nunique())
        c4.metric("📦 Items Sold", int(today_sales["quantity"].sum()))

        st.caption(f"Today's profit margin: {today_margin:.1f}%")

        st.divider()

        st.subheader("📆 This Month")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Monthly Sales", f"₹{month_total:,.2f}")
        c2.metric("📈 Monthly Profit", f"₹{month_profit:,.2f}")
        c3.metric("🧾 Monthly Bills", month_sales["bill_id"].nunique())
        c4.metric("📦 Items Sold", int(month_sales["quantity"].sum()))

        st.caption(f"Monthly profit margin: {month_margin:.1f}%")

        st.divider()

        st.subheader("📈 Daily Sales")
        daily_chart(sales, "total", "Sales")

        st.subheader("💹 Daily Profit")
        daily_chart(sales, "profit", "Profit")

        st.divider()

        st.subheader("🏆 Best-Selling Products")

        best_products = (
            sales.groupby("product")["quantity"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        best_products.columns = ["Product", "Quantity Sold"]

        st.bar_chart(best_products, x="Product", y="Quantity Sold")
        st.dataframe(best_products, width="stretch", hide_index=True)

        st.divider()

        st.subheader("💰 Most Profitable Products")

        profitable = (
            sales.groupby("product")
            .agg(
                Quantity_Sold=("quantity", "sum"),
                Revenue=("total", "sum"),
                Profit=("profit", "sum"),
            )
            .sort_values("Profit", ascending=False)
            .reset_index()
        )
        profitable.columns = ["Product", "Quantity Sold", "Revenue", "Profit"]

        st.dataframe(profitable, width="stretch", hide_index=True)

        st.divider()

        inventory_value_section(inventory, show_table=True)

        st.divider()

        st.subheader("⚠️ Low Stock Products")

        if not inventory.empty:
            low_stock = inventory[inventory["stock"] <= 5][["product", "stock", "price"]]

            if not low_stock.empty:
                st.warning("The following products have 5 or fewer units remaining.")
                st.dataframe(low_stock, width="stretch", hide_index=True)
            else:
                st.success("✅ No low-stock products.")
        else:
            st.info("No inventory data available.")

        st.divider()

        # --------------------------------------------------
        # PAYMENT ANALYSIS (follows the report date range)
        # --------------------------------------------------
        st.subheader("💳 Payment Method Analysis")

        if not report_sales.empty:

            payment_report = (
                report_sales
                .groupby("payment_method")
                .agg(Total_Amount=("total", "sum"), Bills=("bill_id", "nunique"))
                .reset_index()
            )

            payment_report.columns = ["Payment Method", "Total Amount", "Bills"]

            st.bar_chart(payment_report, x="Payment Method", y="Total Amount")

            st.dataframe(payment_report, width="stretch", hide_index=True)

        else:
            st.info("No payment data available for the selected date range.")

        # --------------------------------------------------
        # EXPORT REPORT
        # --------------------------------------------------
        st.divider()

        st.subheader("📥 Export Sales Report")

        if not report_sales.empty:

            export_report = report_sales[
                [
                    "bill_id",
                    "customer_name",
                    "customer_phone",
                    "product",
                    "price",
                    "quantity",
                    "total",
                    "payment_method",
                    "date",
                ]
            ].copy()

            export_report["date"] = pd.to_datetime(
                export_report["date"], errors="coerce"
            ).dt.strftime("%d-%m-%Y %H:%M")

            export_report.columns = [
                "Bill ID",
                "Customer Name",
                "Customer Phone",
                "Product",
                "Selling Price",
                "Quantity",
                "Total",
                "Payment Method",
                "Date",
            ]

            csv_data = export_report.to_csv(index=False)

            file_name = (
                f"sales_report_"
                f"{report_start.strftime('%Y%m%d')}_"
                f"{report_end.strftime('%Y%m%d')}.csv"
            )

            st.download_button(
                label="📥 Download Sales Report (CSV)",
                data=csv_data,
                file_name=file_name,
                mime="text/csv",
            )

        else:
            st.info("No sales available to export for the selected date range.")


# ==========================================================
# ABOUT
# ==========================================================
elif page == "ℹ️ About":

    st.header("ℹ️ About the System")

    st.markdown(
        f"""
## 🛒 {SHOP_NAME}

**Billing & Business Management System**

This application helps manage:

- 🧾 Customer billing
- 📦 Inventory
- 💰 Purchases
- 👥 Customer records
- 📊 Sales and profit
- 💳 Payment methods
- 📈 Business reports
- 📥 Data exports

---

### 🏪 Store Information

**Store:** {SHOP_NAME}

**Location:** {SHOP_ADDRESS}

**Phone:** {SHOP_PHONE}

---

### 💾 Data Storage

Your business data is stored locally in `{DATABASE}`.

This database contains your sales, inventory, purchases and
customer-related records.

---

### 🔐 Backup Reminder

Regularly back up both `app.py` and `{DATABASE}`.

Keeping both files backed up lets you restore the application
and its business data if something goes wrong.

---

### ✅ System Status

🟢 Application Active

🟢 Database Connected

🟢 Billing System Available

🟢 Inventory System Available

🟢 Reports Available
"""
    )

    st.divider()

    st.caption(f"{SHOP_NAME} • Billing & Business Management System")
