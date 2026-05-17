import os
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd
import pyodbc


# Update these settings to match your SQL Server.
SQL_SERVER = os.getenv("EXPENSE_DB_SERVER", "localhost")
SQL_DATABASE = os.getenv("EXPENSE_DB_NAME", "ExpenseTrackerDB")
SQL_USERNAME = os.getenv("EXPENSE_DB_USER", "sa")
SQL_PASSWORD = os.getenv("EXPENSE_DB_PASSWORD", "Password123!")
SQL_DRIVER = os.getenv("EXPENSE_DB_DRIVER", "ODBC Driver 18 for SQL Server")

APP_BG = "#F4F7FA"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#102A43"
TEXT_SECONDARY = "#52606D"
ACCENT = "#1F6FEB"
ACCENT_DARK = "#174EA6"
SUCCESS = "#1B7F5A"
ERROR = "#B42318"
MUTED_BORDER = "#D9E2EC"
FONT_TITLE = ("Helvetica Neue", 22, "bold")
FONT_SUBTITLE = ("Helvetica Neue", 10)
FONT_SECTION = ("Helvetica Neue", 12, "bold")
FONT_BODY = ("Helvetica Neue", 10)
FONT_SMALL = ("Helvetica Neue", 9)


def get_connection():
    connection_string = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Encrypt=yes;"
    )
    return pyodbc.connect(connection_string)


def get_lookup_rows(query):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()


def load_combobox_values():
    users = get_lookup_rows("SELECT UserID, Name FROM Users ORDER BY Name")
    categories = get_lookup_rows("SELECT CategoryID, CategoryName FROM Categories ORDER BY CategoryName")
    payment_methods = get_lookup_rows("SELECT PaymentMethodID, MethodName FROM PaymentMethods ORDER BY MethodName")

    user_map = {f"{row.UserID} - {row.Name}": int(row.UserID) for row in users}
    category_map = {f"{row.CategoryID} - {row.CategoryName}": int(row.CategoryID) for row in categories}
    payment_map = {f"{row.PaymentMethodID} - {row.MethodName}": int(row.PaymentMethodID) for row in payment_methods}

    return user_map, category_map, payment_map


def set_combobox_values():
    global user_map, category_map, payment_map
    try:
        user_map, category_map, payment_map = load_combobox_values()
    except pyodbc.Error as exc:
        user_map, category_map, payment_map = {}, {}, {}
        messagebox.showerror("Database Error", f"Could not load dropdown lists:\n{exc}")
        return

    user_combo["values"] = list(user_map.keys())
    category_combo["values"] = list(category_map.keys())
    payment_combo["values"] = list(payment_map.keys())

    if user_combo["values"]:
        user_combo.current(0)
    if category_combo["values"]:
        category_combo.current(0)
    if payment_combo["values"]:
        payment_combo.current(0)


def add_expense():
    try:
        user_text = user_var.get().strip()
        category_text = category_var.get().strip()
        payment_text = payment_var.get().strip()
        amount_text = amount_entry.get().strip()
        date_text = date_entry.get().strip()
        description_text = description_entry.get().strip()

        if not user_text or not category_text or not payment_text or not amount_text or not date_text:
            messagebox.showerror("Error", "Please fill in all required fields.")
            return

        try:
            amount_value = float(amount_text)
            if amount_value <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Amount must be a positive number.")
            return

        try:
            expense_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Error", "Expense Date must be in YYYY-MM-DD format.")
            return

        user_id = user_map[user_text]
        category_id = category_map[category_text]
        payment_method_id = payment_map[payment_text]

        query = """
            INSERT INTO Expenses (UserID, CategoryID, PaymentMethodID, Amount, ExpenseDate, Description)
            VALUES (?, ?, ?, ?, ?, ?)
        """

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                user_id,
                category_id,
                payment_method_id,
                amount_value,
                expense_date,
                description_text or None,
            )
            conn.commit()

        messagebox.showinfo("Success", "Expense added successfully.")
        amount_entry.delete(0, tk.END)
        date_entry.delete(0, tk.END)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        description_entry.delete(0, tk.END)

    except pyodbc.Error as exc:
        messagebox.showerror("Database Error", f"Could not add the expense:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")


def show_chart():
    try:
        query = """
            SELECT c.CategoryName, SUM(e.Amount) AS TotalExpense
            FROM Expenses e
            JOIN Categories c ON e.CategoryID = c.CategoryID
            GROUP BY c.CategoryName
            ORDER BY TotalExpense DESC
        """

        with get_connection() as conn:
            df = pd.read_sql(query, conn)

        if df.empty:
            messagebox.showwarning("No Data", "No expenses found to chart yet.")
            return

        chart_window = tk.Toplevel(window)
        chart_window.title("Expense Analysis by Category")
        chart_window.geometry("900x600")

        canvas = tk.Canvas(chart_window, bg="white", width=860, height=520)
        canvas.pack(padx=20, pady=20, fill="both", expand=True)

        chart_width = 760
        chart_height = 360
        origin_x = 80
        origin_y = 430
        top_margin = 50
        left_margin = 80

        canvas.create_text(430, 25, text="Expense Analysis by Category", font=("Arial", 16, "bold"))
        canvas.create_line(origin_x, origin_y, origin_x + chart_width, origin_y, width=2)
        canvas.create_line(origin_x, origin_y, origin_x, top_margin, width=2)

        max_value = float(df["TotalExpense"].max())
        bar_count = len(df)
        bar_spacing = chart_width / max(bar_count, 1)
        bar_width = max(24, int(bar_spacing * 0.55))

        for index, row in df.reset_index(drop=True).iterrows():
            value = float(row["TotalExpense"])
            bar_height = 0 if max_value == 0 else int((value / max_value) * chart_height)
            x_center = origin_x + int((index + 0.5) * bar_spacing)
            x0 = x_center - bar_width // 2
            x1 = x_center + bar_width // 2
            y0 = origin_y - bar_height
            y1 = origin_y

            canvas.create_rectangle(x0, y0, x1, y1, fill="#2E86AB", outline="#1B4F72")
            canvas.create_text(x_center, y0 - 12, text=f"{value:.2f}", font=("Arial", 9, "bold"))
            canvas.create_text(x_center, origin_y + 22, text=str(row["CategoryName"]), font=("Arial", 9), angle=0)

    except pyodbc.Error as exc:
        messagebox.showerror("Database Error", f"Could not generate the chart:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")


def check_database_connection():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, "Connected"
    except Exception as exc:
        return False, str(exc)


def configure_styles():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    window.configure(bg=APP_BG)
    style.configure("TFrame", background=APP_BG)
    style.configure("Card.TFrame", background=CARD_BG, relief="flat")
    style.configure("TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=FONT_BODY)
    style.configure("Title.TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=FONT_TITLE)
    style.configure("Subtitle.TLabel", background=APP_BG, foreground=TEXT_SECONDARY, font=FONT_SUBTITLE)
    style.configure("Section.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=FONT_SECTION)
    style.configure("Body.TLabel", background=CARD_BG, foreground=TEXT_SECONDARY, font=FONT_BODY)
    style.configure("Muted.TLabel", background=APP_BG, foreground=TEXT_SECONDARY, font=FONT_SMALL)
    style.configure("Status.TLabel", background=APP_BG, foreground=CARD_BG, font=FONT_SMALL, padding=(10, 4))
    style.configure(
        "TButton",
        font=FONT_BODY,
        padding=(14, 9),
        borderwidth=0,
        focusthickness=0,
    )
    style.configure("Primary.TButton", background=ACCENT, foreground="white")
    style.map("Primary.TButton", background=[("active", ACCENT_DARK)])
    style.configure("Secondary.TButton", background="#E8EEF5", foreground=TEXT_PRIMARY)
    style.map("Secondary.TButton", background=[("active", "#D9E2EC")])
    style.configure("TEntry", fieldbackground="white", padding=8)
    style.configure("TCombobox", padding=6)


def make_card(parent, title, subtitle=None):
    card = ttk.Frame(parent, style="Card.TFrame", padding=20)
    card.columnconfigure(0, weight=1)
    header = ttk.Frame(card, style="Card.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    ttk.Label(header, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
    if subtitle:
        ttk.Label(header, text=subtitle, style="Body.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
    return card


def make_field(parent, label_text, row, widget):
    ttk.Label(parent, text=label_text, style="Body.TLabel").grid(row=row, column=0, sticky="w", pady=(0, 4))
    widget.grid(row=row, column=1, sticky="ew", pady=(0, 14))


window = tk.Tk()
window.title("Daily Expense Tracking System")
window.geometry("980x720")
window.resizable(False, False)
configure_styles()

header_frame = ttk.Frame(window, style="TFrame", padding=(28, 24, 28, 12))
header_frame.pack(fill="x")
header_frame.columnconfigure(0, weight=1)

ttk.Label(header_frame, text="Daily Expense Tracker", style="Title.TLabel").grid(row=0, column=0, sticky="w")
ttk.Label(
    header_frame,
    text="Professional expense entry and reporting for your SQL Server database",
    style="Subtitle.TLabel",
).grid(row=1, column=0, sticky="w", pady=(6, 0))

connection_ok, connection_message = check_database_connection()
status_text = f"Connected to {SQL_DATABASE} on {SQL_SERVER}" if connection_ok else f"Database connection failed: {connection_message}"
status_color = SUCCESS if connection_ok else ERROR
status_label = tk.Label(header_frame, text=status_text, bg=status_color, fg="white", font=FONT_SMALL, padx=12, pady=6)
status_label.grid(row=0, column=1, rowspan=2, sticky="e")

content_frame = ttk.Frame(window, style="TFrame", padding=(28, 12, 28, 20))
content_frame.pack(fill="both", expand=True)

content_frame.columnconfigure(0, weight=1)

form_card = make_card(
    content_frame,
    "Expense Entry",
    "Fill in the details below to create a new expense record.",
)
form_card.grid(row=0, column=0, sticky="nsew")
form_card.columnconfigure(1, weight=1)

user_map = {}
category_map = {}
payment_map = {}

user_var = tk.StringVar()
user_combo = ttk.Combobox(form_card, textvariable=user_var, state="readonly")
make_field(form_card, "User", 0, user_combo)

category_var = tk.StringVar()
category_combo = ttk.Combobox(form_card, textvariable=category_var, state="readonly")
make_field(form_card, "Category", 1, category_combo)

payment_var = tk.StringVar()
payment_combo = ttk.Combobox(form_card, textvariable=payment_var, state="readonly")
make_field(form_card, "Payment Method", 2, payment_combo)

amount_entry = ttk.Entry(form_card)
make_field(form_card, "Amount", 3, amount_entry)

date_entry = ttk.Entry(form_card)
make_field(form_card, "Expense Date (YYYY-MM-DD)", 4, date_entry)
date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

description_entry = ttk.Entry(form_card)
make_field(form_card, "Description", 5, description_entry)

button_card = make_card(content_frame, "Actions", "Use the buttons below to save data, inspect trends, or refresh dropdowns.")
button_card.grid(row=1, column=0, sticky="ew", pady=(18, 0))

button_row = ttk.Frame(button_card, style="Card.TFrame")
button_row.grid(row=2, column=0, sticky="w", pady=(16, 0))

ttk.Button(button_row, text="Add Expense", command=add_expense, style="Primary.TButton").grid(row=0, column=0, padx=(0, 10))
ttk.Button(button_row, text="Show BI Chart", command=show_chart, style="Secondary.TButton").grid(row=0, column=1, padx=(0, 10))
ttk.Button(button_row, text="Refresh Lists", command=set_combobox_values, style="Secondary.TButton").grid(row=0, column=2)

footer_card = ttk.Frame(content_frame, style="TFrame", padding=(4, 18, 4, 0))
footer_card.grid(row=2, column=0, sticky="ew")
hint_text = "The database must contain Users, Categories, and PaymentMethods rows before adding expenses."
ttk.Label(footer_card, text=hint_text, style="Muted.TLabel", justify="center").pack()

if connection_ok:
    set_combobox_values()
else:
    user_combo["values"] = []
    category_combo["values"] = []
    payment_combo["values"] = []

window.mainloop()
