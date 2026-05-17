import os
from datetime import datetime
import textwrap
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
FONT_METRIC = ("Helvetica Neue", 18, "bold")


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


def format_money(value):
    return f"LKR {float(value):,.2f}"


def load_dashboard_metrics(user_id=None):
    if user_id:
        query = f"""
            SELECT
                COUNT(*) AS ExpenseCount,
                COALESCE(SUM(Amount), 0) AS TotalSpent,
                COALESCE(AVG(Amount), 0) AS AvgSpent
            FROM Expenses
            WHERE UserID = {user_id}
        """
    else:
        query = """
            SELECT
                COUNT(*) AS ExpenseCount,
                COALESCE(SUM(Amount), 0) AS TotalSpent,
                COALESCE(AVG(Amount), 0) AS AvgSpent
            FROM Expenses
        """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()

    return {
        "count": int(row.ExpenseCount or 0),
        "total": float(row.TotalSpent or 0),
        "average": float(row.AvgSpent or 0),
    }


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
        refresh_dashboard_metrics()

    except pyodbc.Error as exc:
        messagebox.showerror("Database Error", f"Could not add the expense:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")

def manage_users():
    try:
        def refresh_list():
            listbox.delete(0, tk.END)
            try:
                rows = get_lookup_rows("SELECT UserID, Name FROM Users ORDER BY Name")
            except Exception as exc:
                messagebox.showerror("Database Error", f"Could not load users:\n{exc}")
                return
            for r in rows:
                listbox.insert(tk.END, f"{r.UserID} - {r.Name}")

        def on_add():
            add_user()
            refresh_list()

        def on_edit():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Select User", "Please select a user to edit.")
                return
            item = listbox.get(sel[0])
            uid = int(item.split(" - ")[0])
            edit_user(uid)
            refresh_list()

        def on_delete():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Select User", "Please select a user to delete.")
                return
            item = listbox.get(sel[0])
            uid = int(item.split(" - ")[0])
            name = item.split(" - ", 1)[1]
            if not messagebox.askyesno("Confirm Delete", f"Delete user '{name}'? This may fail if expenses reference this user."):
                return
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM Users WHERE UserID = ?", uid)
                    conn.commit()
                messagebox.showinfo("Deleted", f"User '{name}' deleted.")
            except pyodbc.Error as exc:
                messagebox.showerror("Database Error", f"Could not delete user:\n{exc}")
            except Exception as exc:
                messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")
            refresh_list()

        def on_refresh():
            refresh_list()

        win = tk.Toplevel(window)
        win.title("Manage Users")
        win.geometry("480x520")
        win.configure(bg=APP_BG)

        header = tk.Frame(win, bg=APP_BG)
        header.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(header, text="Manage Users", bg=APP_BG, fg=TEXT_PRIMARY, font=("Helvetica Neue", 16, "bold")).pack(anchor="w")

        frame = tk.Frame(win, bg=CARD_BG, highlightthickness=1, highlightbackground=MUTED_BORDER)
        frame.pack(fill="both", expand=True, padx=16, pady=12)

        listbox = tk.Listbox(frame, font=FONT_BODY, activestyle="none")
        listbox.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y", padx=(0,8), pady=8)
        listbox.config(yscrollcommand=scrollbar.set)

        btn_frame = tk.Frame(win, bg=APP_BG)
        btn_frame.pack(fill="x", padx=16, pady=(0,12))
        ttk.Button(btn_frame, text="Add", command=on_add, style="Secondary.TButton").grid(row=0, column=0, padx=(0,8))
        ttk.Button(btn_frame, text="Edit", command=on_edit, style="Secondary.TButton").grid(row=0, column=1, padx=(0,8))
        ttk.Button(btn_frame, text="Delete", command=on_delete, style="Secondary.TButton").grid(row=0, column=2, padx=(0,8))
        ttk.Button(btn_frame, text="Refresh", command=on_refresh, style="Secondary.TButton").grid(row=0, column=3)

        refresh_list()

    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")


def edit_user(user_id):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM Users WHERE UserID = ?", user_id)
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Not Found", "User not found.")
                return
            current_name = row.Name

        def save_edit():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Please enter a user name.")
                return
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE Users SET Name = ? WHERE UserID = ?", new_name, user_id)
                    conn.commit()
                set_combobox_values()
                edit_win.destroy()
            except pyodbc.Error as exc:
                messagebox.showerror("Database Error", f"Could not update user:\n{exc}")
            except Exception as exc:
                messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")

        edit_win = tk.Toplevel(window)
        edit_win.title("Edit User")
        edit_win.geometry("420x160")
        edit_win.configure(bg=APP_BG)

        frame = tk.Frame(edit_win, bg=CARD_BG, padx=16, pady=16)
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(frame, text="User Name", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY).grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(frame, textvariable=name_var, width=40)
        name_entry.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.grid(row=2, column=0, sticky="e")
        ttk.Button(btn_frame, text="Save", command=save_edit, style="Primary.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=edit_win.destroy, style="Secondary.TButton").grid(row=0, column=1)
        name_entry.focus()

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
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    df = pd.DataFrame(columns=["CategoryName", "TotalExpense"])
                else:
                    df = pd.DataFrame.from_records(rows, columns=[column[0] for column in cursor.description])

        if df.empty:
            messagebox.showwarning("No Data", "No expenses found to chart yet.")
            return
        open_summary_chart(df)

    except pyodbc.Error as exc:
        messagebox.showerror("Database Error", f"Could not generate the chart:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")


def show_all_expenses():
    try:
        selected_user = filter_user_var.get().strip() if filter_user_var.get() else None
        user_id = user_map.get(selected_user) if selected_user else None
        
        if user_id:
            query = """
                SELECT u.Name AS [User], c.CategoryName AS Category, e.Amount, e.ExpenseDate AS [Date], e.Description, p.MethodName AS PaymentMethod
                FROM Expenses e
                JOIN Users u ON e.UserID = u.UserID
                JOIN Categories c ON e.CategoryID = c.CategoryID
                JOIN PaymentMethods p ON e.PaymentMethodID = p.PaymentMethodID
                WHERE e.UserID = ?
                ORDER BY e.ExpenseDate DESC
            """
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, user_id)
                rows = cursor.fetchall()
        else:
            query = """
                SELECT u.Name AS [User], c.CategoryName AS Category, e.Amount, e.ExpenseDate AS [Date], e.Description, p.MethodName AS PaymentMethod
                FROM Expenses e
                JOIN Users u ON e.UserID = u.UserID
                JOIN Categories c ON e.CategoryID = c.CategoryID
                JOIN PaymentMethods p ON e.PaymentMethodID = p.PaymentMethodID
                ORDER BY e.ExpenseDate DESC
            """
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
        
        if not rows:
            messagebox.showinfo("No Data", "No expenses found for the selected user.")
            return
        
        # Create new window
        expenses_window = tk.Toplevel(window)
        expenses_window.title("All Expenses")
        expenses_window.geometry("1200x600")
        expenses_window.configure(bg=APP_BG)
        
        # Header
        header = tk.Frame(expenses_window, bg=APP_BG)
        header.pack(fill="x", padx=24, pady=(24, 14))
        tk.Label(header, text="All Expenses", bg=APP_BG, fg=TEXT_PRIMARY, font=("Helvetica Neue", 20, "bold")).pack(anchor="w")
        user_filter_text = f"Filter: {selected_user}" if selected_user else "Filter: All Users"
        tk.Label(header, text=user_filter_text, bg=APP_BG, fg=TEXT_SECONDARY, font=FONT_BODY).pack(anchor="w", pady=(4, 0))
        
        # Table frame
        table_frame = tk.Frame(expenses_window, bg=CARD_BG, highlightthickness=1, highlightbackground=MUTED_BORDER)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        
        # Headers
        headers = ["User", "Category", "Amount", "Date", "Description", "Payment Method"]
        header_frame = tk.Frame(table_frame, bg="#E8EEF5")
        header_frame.pack(fill="x")
        
        col_widths = [150, 150, 120, 120, 300, 150]
        for i, (header_text, width) in enumerate(zip(headers, col_widths)):
            tk.Label(
                header_frame,
                text=header_text,
                bg="#E8EEF5",
                fg=TEXT_PRIMARY,
                font=FONT_SECTION,
                width=width // 8,
                anchor="w",
                padx=10,
                pady=12
            ).grid(row=0, column=i, sticky="w")
        
        # Scrollable content
        canvas = tk.Canvas(table_frame, bg=CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=CARD_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add rows
        for idx, row in enumerate(rows):
            row_bg = "#FFFFFF" if idx % 2 == 0 else "#F9FAFB"
            row_frame = tk.Frame(scrollable_frame, bg=row_bg)
            row_frame.pack(fill="x")
            
            col_values = [
                str(row.User),
                str(row.Category),
                format_money(row.Amount),
                str(row.Date),
                str(row.Description or ""),
                str(row.PaymentMethod)
            ]
            
            for j, (value, width) in enumerate(zip(col_values, col_widths)):
                tk.Label(
                    row_frame,
                    text=value,
                    bg=row_bg,
                    fg=TEXT_PRIMARY,
                    font=FONT_BODY,
                    width=width // 8,
                    anchor="w",
                    padx=10,
                    pady=10
                ).grid(row=0, column=j, sticky="w")
    
    except pyodbc.Error as exc:
        messagebox.showerror("Database Error", f"Could not load expenses:\n{exc}")
    except Exception as exc:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")


def add_user():
    try:
        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a user name.")
                return
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO Users (Name) VALUES (?)", name)
                    cursor.execute("SELECT SCOPE_IDENTITY()")
                    row = cursor.fetchone()
                    new_id = int(row[0]) if row and row[0] is not None else None
                    conn.commit()

                # Refresh dropdown lists and try to select the new user
                set_combobox_values()
                if new_id is not None:
                    display = f"{new_id} - {name}"
                    if display in user_combo["values"]:
                        user_combo.set(display)
                    else:
                        # fallback: select first matching name suffix
                        for v in user_combo["values"]:
                            if v.endswith(f"- {name}"):
                                user_combo.set(v)
                                break

                add_win.destroy()
            except pyodbc.Error as exc:
                messagebox.showerror("Database Error", f"Could not add user:\n{exc}")
            except Exception as exc:
                messagebox.showerror("Error", f"An unexpected error occurred:\n{exc}")

        add_win = tk.Toplevel(window)
        add_win.title("Add New User")
        add_win.geometry("420x160")
        add_win.configure(bg=APP_BG)

        frame = tk.Frame(add_win, bg=CARD_BG, padx=16, pady=16)
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(frame, text="User Name", bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_BODY).grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar()
        name_entry = ttk.Entry(frame, textvariable=name_var, width=40)
        name_entry.grid(row=1, column=0, sticky="ew", pady=(8, 12))

        btn_frame = tk.Frame(frame, bg=CARD_BG)
        btn_frame.grid(row=2, column=0, sticky="e")
        ttk.Button(btn_frame, text="Save", command=save, style="Primary.TButton").grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=add_win.destroy, style="Secondary.TButton").grid(row=0, column=1)
        name_entry.focus()

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


def build_stat_card(parent, title, value_var, accent_color):
    card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1, highlightbackground=MUTED_BORDER)
    title_label = tk.Label(card, text=title, bg=CARD_BG, fg=TEXT_SECONDARY, font=FONT_SMALL)
    title_label.grid(row=0, column=0, sticky="w")
    value_label = tk.Label(card, textvariable=value_var, bg=CARD_BG, fg=TEXT_PRIMARY, font=FONT_METRIC)
    value_label.grid(row=1, column=0, sticky="w", pady=(10, 0))
    accent_strip = tk.Frame(card, bg=accent_color, height=4)
    accent_strip.grid(row=2, column=0, sticky="ew", pady=(16, 0))
    card.columnconfigure(0, weight=1)
    return card


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


def refresh_dashboard_metrics():
    selected_user = filter_user_var.get().strip() if filter_user_var.get() else None
    user_id = user_map.get(selected_user) if selected_user else None
    metrics = load_dashboard_metrics(user_id)
    metric_count_var.set(f"{metrics['count']:,}")
    metric_total_var.set(format_money(metrics['total']))
    metric_average_var.set(format_money(metrics['average']))


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


def open_summary_chart(df):
    chart_window = tk.Toplevel(window)

    chart_window.title("BI Dashboard - Expense Analysis")
    chart_window.geometry("1100x720")
    chart_window.configure(bg=APP_BG)
    chart_window.minsize(980, 640)

    shell = tk.Frame(chart_window, bg=APP_BG)
    shell.pack(fill="both", expand=True, padx=24, pady=24)

    header = tk.Frame(shell, bg=APP_BG)
    header.pack(fill="x", pady=(0, 14))
    tk.Label(header, text="BI Dashboard", bg=APP_BG, fg=TEXT_PRIMARY, font=("Helvetica Neue", 22, "bold")).pack(anchor="w")
    tk.Label(
        header,
        text="Expense distribution by category with a cleaner professional presentation",
        bg=APP_BG,
        fg=TEXT_SECONDARY,
        font=FONT_BODY,
    ).pack(anchor="w", pady=(4, 0))

    body = tk.Frame(shell, bg=CARD_BG, highlightthickness=1, highlightbackground=MUTED_BORDER)
    body.pack(fill="both", expand=True)

    canvas = tk.Canvas(body, bg=CARD_BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=10, pady=10)

    width = 1000
    height = 560
    left = 90
    right = 30
    top = 70
    bottom = 110
    chart_width = width - left - right
    chart_height = height - top - bottom
    origin_x = left
    origin_y = top + chart_height

    max_value = max(float(value) for value in df["TotalExpense"])
    bar_count = len(df)
    spacing = chart_width / max(bar_count, 1)
    bar_width = min(72, max(42, int(spacing * 0.55)))
    palette = ["#1F6FEB", "#2F80ED", "#16A085", "#F2994A", "#9B51E0", "#C0392B", "#34495E"]

    canvas.create_text(left, 28, anchor="w", text="Expense Analysis by Category", fill=TEXT_PRIMARY, font=("Helvetica Neue", 16, "bold"))
    canvas.create_text(width - right, 28, anchor="e", text="Amount in LKR", fill=TEXT_SECONDARY, font=FONT_SMALL)

    for tick in range(6):
        tick_value = max_value * tick / 5 if max_value else 0
        y = origin_y - int(chart_height * tick / 5)
        canvas.create_line(origin_x, y, origin_x + chart_width, y, fill="#EEF2F7")
        canvas.create_text(origin_x - 12, y, text=f"{tick_value:,.0f}", anchor="e", fill=TEXT_SECONDARY, font=FONT_SMALL)

    canvas.create_line(origin_x, origin_y, origin_x + chart_width, origin_y, fill="#8CA0B3", width=2)
    canvas.create_line(origin_x, origin_y, origin_x, top, fill="#8CA0B3", width=2)

    for index, row in df.reset_index(drop=True).iterrows():
        value = float(row["TotalExpense"])
        label = str(row["CategoryName"])
        bar_height = 0 if max_value == 0 else int((value / max_value) * chart_height)
        x_center = origin_x + int((index + 0.5) * spacing)
        x0 = x_center - bar_width // 2
        x1 = x_center + bar_width // 2
        y0 = origin_y - bar_height
        y1 = origin_y
        color = palette[index % len(palette)]

        canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color)
        canvas.create_text(x_center, y0 - 12, text=format_money(value), fill=TEXT_PRIMARY, font=("Helvetica Neue", 9, "bold"))

        wrapped = "\n".join(textwrap.wrap(label, width=14)) or label
        canvas.create_text(x_center, origin_y + 20, text=wrapped, fill=TEXT_PRIMARY, font=FONT_SMALL, justify="center")

    canvas.create_rectangle(left, height - 36, left + 18, height - 18, fill=palette[0], outline=palette[0])
    canvas.create_text(left + 28, height - 27, anchor="w", text="Category total", fill=TEXT_SECONDARY, font=FONT_SMALL)


window = tk.Tk()
window.title("Daily Expense Tracking System")
window.geometry("1080x820")
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

filter_frame = tk.Frame(content_frame, bg=APP_BG)
filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
filter_frame.columnconfigure(1, weight=1)

filter_label = tk.Label(filter_frame, text="Filter by User:", bg=APP_BG, fg=TEXT_PRIMARY, font=FONT_BODY)
filter_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

filter_user_var = tk.StringVar()
filter_combo = ttk.Combobox(filter_frame, textvariable=filter_user_var, state="readonly", width=30)
filter_combo.grid(row=0, column=1, sticky="w")

def on_filter_change(event=None):
    refresh_dashboard_metrics()

filter_combo.bind("<<ComboboxSelected>>", on_filter_change)

metrics_frame = tk.Frame(content_frame, bg=APP_BG)
metrics_frame.grid(row=1, column=0, sticky="ew", pady=(0, 18))
metrics_frame.columnconfigure(0, weight=1)
metrics_frame.columnconfigure(1, weight=1)
metrics_frame.columnconfigure(2, weight=1)

metric_count_var = tk.StringVar(value="-")
metric_total_var = tk.StringVar(value="-")
metric_average_var = tk.StringVar(value="-")

build_stat_card(metrics_frame, "Expenses", metric_count_var, "#1F6FEB").grid(row=0, column=0, sticky="ew", padx=(0, 12))
build_stat_card(metrics_frame, "Total Spent", metric_total_var, "#16A085").grid(row=0, column=1, sticky="ew", padx=12)
build_stat_card(metrics_frame, "Average Expense", metric_average_var, "#F2994A").grid(row=0, column=2, sticky="ew", padx=(12, 0))

form_card = make_card(
    content_frame,
    "Expense Entry",
    "Fill in the details below to create a new expense record.",
)
form_card.grid(row=2, column=0, sticky="nsew")
form_card.columnconfigure(0, minsize=140)
form_card.columnconfigure(1, weight=1)

user_map = {}
category_map = {}
payment_map = {}

user_var = tk.StringVar()
user_combo = ttk.Combobox(form_card, textvariable=user_var, state="readonly")
make_field(form_card, "User", 1, user_combo)

category_var = tk.StringVar()
category_combo = ttk.Combobox(form_card, textvariable=category_var, state="readonly")
make_field(form_card, "Category", 2, category_combo)

payment_var = tk.StringVar()
payment_combo = ttk.Combobox(form_card, textvariable=payment_var, state="readonly")
make_field(form_card, "Payment Method", 3, payment_combo)

amount_entry = ttk.Entry(form_card)
make_field(form_card, "Amount", 4, amount_entry)

date_entry = ttk.Entry(form_card)
make_field(form_card, "Expense Date (YYYY-MM-DD)", 5, date_entry)
date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

description_entry = ttk.Entry(form_card)
make_field(form_card, "Description", 6, description_entry)

button_card = make_card(content_frame, "Actions", "Use the buttons below to save data, inspect trends, or refresh dropdowns.")
button_card.grid(row=3, column=0, sticky="ew", pady=(18, 0))

button_row = ttk.Frame(button_card, style="Card.TFrame")
button_row.grid(row=1, column=0, sticky="w", pady=(16, 0))

ttk.Button(button_row, text="Add Expense", command=add_expense, style="Primary.TButton").grid(row=0, column=0, padx=(0, 10))
ttk.Button(button_row, text="Show BI Chart", command=show_chart, style="Secondary.TButton").grid(row=0, column=1, padx=(0, 10))
ttk.Button(button_row, text="Show All Expenses", command=show_all_expenses, style="Secondary.TButton").grid(row=0, column=2, padx=(0, 10))
ttk.Button(button_row, text="Add User", command=add_user, style="Secondary.TButton").grid(row=0, column=3, padx=(0, 10))
ttk.Button(button_row, text="Manage Users", command=manage_users, style="Secondary.TButton").grid(row=0, column=4, padx=(0, 10))
ttk.Button(button_row, text="Refresh Lists", command=set_combobox_values, style="Secondary.TButton").grid(row=0, column=5)

footer_card = ttk.Frame(content_frame, style="TFrame", padding=(4, 18, 4, 0))
footer_card.grid(row=4, column=0, sticky="ew")
hint_text = "The database must contain Users, Categories, and PaymentMethods rows before adding expenses."
ttk.Label(footer_card, text=hint_text, style="Muted.TLabel", justify="center").pack()

if connection_ok:
    set_combobox_values()
    filter_combo["values"] = ["All Users"] + list(user_map.keys())
    filter_combo.current(0)
    refresh_dashboard_metrics()
else:
    user_combo["values"] = []
    category_combo["values"] = []
    payment_combo["values"] = []
    filter_combo["values"] = ["All Users"]

window.mainloop()
