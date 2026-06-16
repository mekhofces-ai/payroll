from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from db_adapter import connect, Row, Connection, OperationalError

APP_NAME = "Payroll"
DATABASE_URL = os.environ.get("DATABASE_URL")
CURRENCY = "EGP"

MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

PAYMENT_STATUSES = ["Pending", "Transferred", "Hold", "Cancelled"]
BONUS_PAYMENT_STATUSES = ["Planned", "Approved", "Paid", "Cancelled", "Hold"]
APPROVAL_STATUSES = ["Draft", "Submitted", "Approved", "Rejected"]
PAYROLL_APPROVAL_STATUSES = ["Draft", "Generated", "Submitted", "HR Reviewed", "Finance Reviewed", "Approved", "Transferred", "Closed", "Reopened", "Cancelled"]
LOCK_STATUSES = ["Open", "Locked", "Closed"]
ACCESS_LEVELS = ["No Access", "View Only", "Add", "Edit", "Delete / Disable", "Export", "Approve", "Full Access"]
ACCESS_RANK = {name: index for index, name in enumerate(ACCESS_LEVELS)}
BONUS_CATEGORIES = [
    "Performance Bonus",
    "Project Bonus",
    "Eid Bonus",
    "Annual Bonus",
    "Retention Bonus",
    "Overtime Bonus",
    "Exceptional Bonus",
    "Other",
]
INSURANCE_BASE_SOURCES = [
    "Employee Insurance Salary/Base",
    "Employee Basic Salary",
    "Gross Salary",
    "Gross Salary / 1.3",
    "Fixed Manual Amount",
    "No Insurance",
]
BASIC_SALARY_SOURCES = [
    "Use Employee Basic Salary",
    "Use Gross Salary",
    "Gross Salary Excluding Statutory Allowances",
    "Calculate as % of Gross only if the user chooses it",
]
EGYPT_TAX_175_BRACKETS = [
    (0, 30000, 0.00),
    (30000, 45000, 0.10),
    (45000, 60000, 0.15),
    (60000, 200000, 0.20),
    (200000, 400000, 0.225),
    (400000, 1200000, 0.25),
    (1200000, None, 0.275),
]
EGYPT_CURRENT_BRACKETS = [
    (0, 40000, 0.00),
    (40000, 55000, 0.10),
    (55000, 70000, 0.15),
    (70000, 200000, 0.20),
    (200000, 400000, 0.225),
    (400000, 1200000, 0.25),
    (1200000, None, 0.275),
]
DEFAULT_ROLES = [
    "Super Admin",
    "Admin",
    "Payroll Manager",
    "HR User",
    "Finance User",
    "Project Manager",
    "Viewer",
]
SENSITIVE_SALARY_COLUMNS = {
    "Can View Salary": ["salary", "earning", "transfer", "basic", "net"],
    "Can View Net Salary": ["net_salary", "new_net_salary", "net earning", "net_transfer", "net transfer", "net_bonus", "net bonus"],
    "Can View Gross Salary": ["gross"],
    "Can View Tax": ["tax"],
    "Can View Social Insurance": ["insurance"],
    "Can View Company Cost": ["company_cost", "company cost", "cost_difference", "cost difference", "total_company_cost"],
    "Can View Bonus Amount": ["bonus"],
}
ACTION_PERMISSIONS = [
    "Can Add Employee",
    "Can Edit Employee",
    "Can Disable Employee",
    "Can Add Allowance",
    "Can Edit Allowance",
    "Can Generate Payroll",
    "Can Recalculate Payroll",
    "Can Close Payroll Run",
    "Can Reopen Payroll Run",
    "Can Mark Payroll as Transferred",
    "Can Add Bonus",
    "Can Approve Bonus",
    "Can Mark Bonus as Paid",
    "Can Edit Tax Setup",
    "Can Edit Insurance Setup",
    "Can Import Data",
    "Can Export Data",
    "Can Manage Users",
    "Can View Audit Log",
    "Can View Salary",
    "Can View Net Salary",
    "Can View Gross Salary",
    "Can View Tax",
    "Can View Social Insurance",
    "Can View Company Cost",
    "Can View Bonus Amount",
    "Can Export Salary Data",
]
ALLOWANCE_TYPES = [
    "Housing Allowance",
    "Transportation Allowance",
    "Meal Allowance",
    "Mobile Allowance",
    "Site Allowance",
    "Shift Allowance",
    "Overtime Allowance",
    "Project Allowance",
    "Temporary Allowance",
    "Other Allowance",
    "Bonus",
]

PROJECT_CHARGING_METHODS = [
    "Follow Employee Project Allocation",
    "Charge to Specific Project",
]


EMPLOYEE_SEED_DATA = [
    ("120918", "AFM", "Professional", "حماده عامر جمعه", "Janitor", "Services", "Housekeeping", "Chevron", "30-Nov-22", 7500, 0, 7500),
    ("121009", "AFM", "Professional", "بدريه عبد السلام السيد امام", "Janitor", "Services", "Housekeeping", "Chevron", "26-Dec-21", 7500, 0, 7500),
    ("122874", "AFM", "Professional", "محمد فؤاد محمد سيد", "Office Boy", "Services", "Business Support", "Chevron", "1-Feb-23", 9338.49, 1231.92, 10570.41),
    ("122875", "AFM", "Professional", "رابح ابوبكر شبل عبده", "Office Boy", "Services", "Business Support", "Chevron", "1-Mar-23", 9338.49, 1231.92, 10570.41),
    ("122876", "AFM", "Professional", "وليد إبراهيم عبدالله احمد", "Office Boy", "Services", "Business Support", "Chevron", "1-Mar-23", 9338.49, 615.96, 9954.45),
    ("121915", "AFM", "Professional", "حسام حنفي حسن صالح", "HK Supervisor", "Services", "Housekeeping", "Chevron", "15-Nov-22", 10206.25, 1679.74, 11885.99),
    ("128902", "AFM", "Professional", "عبدالرحيم مصطفى محمد حمد", "Janitor", "Services", "Housekeeping", "Chevron", "23-Nov-25", 7500, 0, 7500),
    ("128903", "AFM", "Professional", "احمد عبدالله عبدالله فتح الله النقيب", "Janitor", "Services", "Housekeeping", "Chevron", "30-Nov-25", 7500, 0, 7500),
    ("128027", "AFM", "Professional", "حازم محمد حلمى محمد عبدالنبى", "Pest Control Technician", "Services", "Pest Control", "Chevron", "9-Apr-26", 5500, 0, 5500),
    ("122731", "AFM", "Professional", "عبدالله عبدالله فتح الله النقيب", "Agriculture Labor", "Landscape Maintenance", "Agriculture", "Chevron", "2-Jan-23", 8579.82, 615.96, 9195.78),
    ("122732", "AFM", "Professional", "محمد السيد محمد موسى الفقى", "Agriculture Labor", "Landscape Maintenance", "Agriculture", "Chevron", "2-Jan-23", 8579.82, 615.96, 9195.78),
    ("11914", "AFM", "AFM", "يسرى محمود عبدالحميد سيد", "Messenger", "Property Operations", "Operations General", "Chevron", "1-Feb-23", 10252.18, 3310.82, 13563),
    ("11916", "AFM", "AFM", "رضا سعيد محمد سالم غنيم الغواص", "Messenger", "Property Operations", "Operations General", "Chevron", "1-Feb-23", 9772.37, 3211.63, 12984),
    ("11918", "AFM", "AFM", "محمود عبد العزيز عبد السلام محمد شرايف", "Site Service Senior Coordinator", "Property Operations", "Operations General", "Chevron", "1-Feb-23", 12296, 13969, 26265),
    ("11965", "AFM", "AFM", "محمد رشاد يوسف صابر", "Driver", "Services", "Fleet", "Chevron", "1-Aug-23", 8481.40, 2956.77, 11438.17),
    ("11966", "AFM", "AFM", "محمد حسن على محمد", "Messenger", "Property Operations", "Operations", "Chevron", "8-Jan-24", 9097.36, 3079.79, 12177.15),
    ("11995", "AFM", "AFM", "أية سعد إبراهيم على جاد", "Admin Assistant", "Facility Projects Management", "FPM General", "Chevron", "1-Dec-24", 18000, 0, 18000),
    ("12019", "AFM", "AFM", "محمد محسن أحمد محمد", "HSE Supervisor", "Health & Safety", "HSE General", "Chevron", "15-Jul-25", 30000, 0, 30000),
    ("12032", "AFM", "AFM", "ساندى هانى إسحاق باباوى", "Assistant Facility Manager", "Facility Projects Management", "FPM General", "Chevron", "1-Sep-25", 24000, 0, 24000),
    ("122341", "AFM", "Professional", "حسن عبدالجابر حسن أحمد", "Electrical Technician", "Maintenance", "Electrical", "Chevron Upstream", "18-Jan-23", 10000, 4417.90, 14417.90),
    ("121960", "AFM", "Professional", "محمد عامر أبو الحسن", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "27-Nov-22", 5539.83, 1642.94, 7182.77),
    ("126383", "AFM", "Professional", "عادل احمد سيد احمد يوسف", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "27-Aug-24", 5539.83, 1642.94, 7182.77),
    ("126384", "AFM", "Professional", "احمد مهدى معوض موسي", "HK Supervisor", "Services", "Housekeeping", "Chevron Upstream", "26-Aug-24", 7709.61, 1668.25, 9377.86),
    ("124139", "AFM", "Professional", "محمد سعيد فتحى احمد هنداوى", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "18-Jul-24", 5539.83, 1642.94, 7182.77),
    ("124624", "AFM", "Professional", "مصطفى كمال محمد احمد", "HK Supervisor", "Services", "Housekeeping", "Chevron Upstream", "6-Aug-24", 7709.61, 1668.25, 9377.86),
    ("126082", "AFM", "Professional", "احمد صلاح محمد احمد", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "6-Aug-24", 5539.83, 1642.94, 7182.77),
    ("126467", "AFM", "Professional", "محمد حلمى عبدالباقى احمد", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "26-Sep-24", 5539.83, 1642.94, 7182.77),
    ("129028", "AFM", "Professional", "معتز محمود محمد محمود اسماعيل", "Janitor", "Services", "Housekeeping", "Chevron Upstream", "4-Jan-26", 5539.83, 1642.94, 7182.77),
    ("10864", "AFM", "AFM", "احمد عيد راغب محمود", "Office Boy", "Services", "Business Support", "Chevron Upstream", "5-Oct-20", 7415, 4318, 11733),
    ("11423", "AFM", "AFM", "محمود إبراهيم محمد رشدى عبد العزيز", "Operations Supervisor", "Property Operations", "Operations General", "Chevron Upstream", "1-Jun-21", 10945.24, 8567.76, 19513),
]


def db() -> Connection:
    return connect()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_seed_date(value: str) -> str:
    return datetime.strptime(value, "%d-%b-%y").date().isoformat()


def month_bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def run_sql(sql: str, params: tuple | dict = ()) -> None:
    with db() as conn:
        conn.execute(sql, params)
        conn.commit()


def fetch_one(sql: str, params: tuple | dict = ()) -> Row | None:
    with db() as conn:
        return conn.execute(sql, params).fetchone()


def fetch_all(sql: str, params: tuple | dict = ()) -> list[Row]:
    with db() as conn:
        return conn.execute(sql, params).fetchall()


def read_df(sql: str, params: tuple | dict = ()) -> pd.DataFrame:
    with db() as conn:
        raw = getattr(conn, "_raw_conn", conn)
        pg = hasattr(conn, "_raw_conn")
        if pg:
            sql = sql.replace("?", "%s")
            if isinstance(params, tuple):
                params = list(params)
        return pd.read_sql_query(sql, raw, params=params)


def money(value: float | int | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0
    return f"{float(value):,.2f} {CURRENCY}"


def secure_money(value: float | int | None, permission_code: str = "Can View Salary") -> str:
    return money(value) if has_action(permission_code) else "Restricted"


def pct(value: float | int | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0
    return f"{float(value):,.2f}%"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value in ("", "-", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_date(value) -> str | None:
    if value in ("", None):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, frame in sheets.items():
            safe_name = sheet_name[:31] or "Sheet1"
            frame.to_excel(writer, index=False, sheet_name=safe_name)
            workbook = writer.book
            worksheet = writer.sheets[safe_name]
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#1f4e78", "font_color": "white", "border": 1})
            currency_fmt = workbook.add_format({"num_format": '#,##0.00 "EGP"'})
            for col_num, column_name in enumerate(frame.columns):
                worksheet.write(0, col_num, column_name, header_fmt)
                width = min(max(12, int(frame[column_name].astype(str).str.len().quantile(0.90)) + 2), 42) if not frame.empty else 18
                worksheet.set_column(col_num, col_num, width)
                if any(token in column_name.lower() for token in ["salary", "allowance", "gross", "tax", "insurance", "cost", "amount", "earning", "transfer"]):
                    worksheet.set_column(col_num, col_num, width, currency_fmt)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(frame), 1), max(len(frame.columns) - 1, 0))
    return output.getvalue()


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def audit(action: str, entity: str, entity_id: str | int | None = None, details: str = "") -> None:
    user = st.session_state.get("username", "system")
    role = st.session_state.get("role", "system")
    with db() as conn:
        columns = table_columns(conn, "audit_log")
        if {"user_role", "module", "table_name"}.issubset(columns):
            conn.execute(
                """
                INSERT INTO audit_log
                (event_time, username, user_role, action, module, table_name, entity, entity_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now_text(), user, role, action, entity, entity, entity, str(entity_id or ""), details),
            )
        else:
            conn.execute(
                """
                INSERT INTO audit_log (event_time, username, action, entity, entity_id, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now_text(), user, action, entity, str(entity_id or ""), details),
            )
        conn.commit()


def create_schema() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_code TEXT NOT NULL UNIQUE,
        project_name TEXT NOT NULL,
        client_name TEXT,
        organization TEXT,
        location TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        start_date TEXT,
        end_date TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS employees (
        employee_code TEXT PRIMARY KEY,
        organization TEXT,
        sponsor TEXT,
        arabic_name TEXT NOT NULL,
        position TEXT,
        department TEXT,
        section TEXT,
        default_project_id INTEGER,
        hiring_date TEXT,
        basic_salary REAL NOT NULL DEFAULT 0,
        net_salary REAL NOT NULL DEFAULT 0,
        gross_salary REAL NOT NULL DEFAULT 0,
        new_net_salary REAL NOT NULL DEFAULT 0,
        new_allowance REAL NOT NULL DEFAULT 0,
        new_net_earning REAL NOT NULL DEFAULT 0,
        insurance_salary_base REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Active',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (default_project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS employee_project_allocations (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT NOT NULL,
        project_id INTEGER NOT NULL,
        allocation_type TEXT NOT NULL CHECK (allocation_type IN ('Percentage', 'Fixed Amount')),
        allocation_percentage REAL NOT NULL DEFAULT 0,
        fixed_allocation_amount REAL NOT NULL DEFAULT 0,
        effective_from TEXT,
        effective_to TEXT,
        is_primary_project INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Active',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS allowance_types (
        allowance_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        allowance_type TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS employee_allowances (
        allowance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT NOT NULL,
        allowance_type TEXT NOT NULL,
        allowance_name TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        calculation_type TEXT NOT NULL DEFAULT 'Fixed Amount',
        payment_type TEXT NOT NULL DEFAULT 'Net Allowance',
        taxable INTEGER NOT NULL DEFAULT 1,
        social_insurance_applicable INTEGER NOT NULL DEFAULT 0,
        recurring TEXT NOT NULL DEFAULT 'Monthly',
        project_charging_method TEXT NOT NULL DEFAULT 'Follow Employee Project Allocation',
        specific_project_id INTEGER,
        effective_from TEXT,
        effective_to TEXT,
        department TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        paid_year INTEGER,
        paid_month INTEGER,
        saved_from_bonus_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
        FOREIGN KEY (specific_project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS payroll_runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        project_id INTEGER,
        department TEXT,
        status TEXT NOT NULL DEFAULT 'Open',
        generated_at TEXT NOT NULL,
        generated_by TEXT,
        closed_at TEXT,
        notes TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS payroll_transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        employee_code TEXT NOT NULL,
        arabic_name TEXT,
        organization TEXT,
        sponsor TEXT,
        position TEXT,
        department TEXT,
        section TEXT,
        default_project_id INTEGER,
        project_allocation_summary TEXT,
        base_net_salary REAL NOT NULL DEFAULT 0,
        recurring_net_allowances REAL NOT NULL DEFAULT 0,
        recurring_gross_allowances REAL NOT NULL DEFAULT 0,
        one_time_net_allowances REAL NOT NULL DEFAULT 0,
        one_time_gross_allowances REAL NOT NULL DEFAULT 0,
        total_allowances REAL NOT NULL DEFAULT 0,
        net_earning REAL NOT NULL DEFAULT 0,
        estimated_gross REAL NOT NULL DEFAULT 0,
        basic_salary REAL NOT NULL DEFAULT 0,
        insurance_base REAL NOT NULL DEFAULT 0,
        employee_insurance REAL NOT NULL DEFAULT 0,
        company_insurance REAL NOT NULL DEFAULT 0,
        taxable_amount REAL NOT NULL DEFAULT 0,
        monthly_tax REAL NOT NULL DEFAULT 0,
        annual_tax REAL NOT NULL DEFAULT 0,
        total_deductions REAL NOT NULL DEFAULT 0,
        net_transfer_amount REAL NOT NULL DEFAULT 0,
        total_company_cost REAL NOT NULL DEFAULT 0,
        transfer_date TEXT,
        transfer_reference TEXT,
        payment_status TEXT NOT NULL DEFAULT 'Pending',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        UNIQUE (employee_code, year, month),
        FOREIGN KEY (run_id) REFERENCES payroll_runs(run_id),
        FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
        FOREIGN KEY (default_project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS payroll_project_allocations (
        payroll_project_allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        employee_code TEXT NOT NULL,
        arabic_name TEXT,
        department TEXT,
        section TEXT,
        project_id INTEGER NOT NULL,
        allocation_percentage REAL NOT NULL DEFAULT 0,
        allocated_net_salary REAL NOT NULL DEFAULT 0,
        allocated_allowances REAL NOT NULL DEFAULT 0,
        allocated_gross REAL NOT NULL DEFAULT 0,
        allocated_tax REAL NOT NULL DEFAULT 0,
        allocated_employee_insurance REAL NOT NULL DEFAULT 0,
        allocated_company_insurance REAL NOT NULL DEFAULT 0,
        allocated_total_company_cost REAL NOT NULL DEFAULT 0,
        payment_status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES payroll_transactions(transaction_id),
        FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
        FOREIGN KEY (project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS bonus_simulations (
        bonus_simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT NOT NULL,
        employee_name TEXT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        bonus_type TEXT NOT NULL,
        bonus_amount REAL NOT NULL DEFAULT 0,
        bonus_reason TEXT,
        project_charging_method TEXT NOT NULL DEFAULT 'Follow Employee Project Allocation',
        specific_project_id INTEGER,
        project_allocation_summary TEXT,
        department TEXT,
        sponsor TEXT,
        gross_before REAL NOT NULL DEFAULT 0,
        gross_after REAL NOT NULL DEFAULT 0,
        gross_difference REAL NOT NULL DEFAULT 0,
        tax_before REAL NOT NULL DEFAULT 0,
        tax_after REAL NOT NULL DEFAULT 0,
        tax_difference REAL NOT NULL DEFAULT 0,
        employee_insurance_before REAL NOT NULL DEFAULT 0,
        employee_insurance_after REAL NOT NULL DEFAULT 0,
        employee_insurance_difference REAL NOT NULL DEFAULT 0,
        company_insurance_before REAL NOT NULL DEFAULT 0,
        company_insurance_after REAL NOT NULL DEFAULT 0,
        company_insurance_difference REAL NOT NULL DEFAULT 0,
        company_cost_before REAL NOT NULL DEFAULT 0,
        company_cost_after REAL NOT NULL DEFAULT 0,
        company_cost_difference REAL NOT NULL DEFAULT 0,
        net_before REAL NOT NULL DEFAULT 0,
        net_after REAL NOT NULL DEFAULT 0,
        net_increase REAL NOT NULL DEFAULT 0,
        saved_as_allowance INTEGER NOT NULL DEFAULT 0,
        created_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
        FOREIGN KEY (specific_project_id) REFERENCES projects(project_id)
    );

    CREATE TABLE IF NOT EXISTS tax_laws (
        tax_law_id INTEGER PRIMARY KEY AUTOINCREMENT,
        law_name TEXT NOT NULL,
        effective_year INTEGER NOT NULL,
        personal_exemption REAL NOT NULL DEFAULT 0,
        additional_exemption REAL NOT NULL DEFAULT 0,
        employee_insurance_share REAL NOT NULL DEFAULT 0.11,
        company_insurance_share REAL NOT NULL DEFAULT 0.1875,
        minimum_insurance_base REAL NOT NULL DEFAULT 0,
        maximum_insurance_base REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Active',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS tax_brackets (
        bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tax_law_id INTEGER NOT NULL,
        bracket_order INTEGER NOT NULL,
        min_amount REAL NOT NULL DEFAULT 0,
        max_amount REAL,
        tax_rate REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (tax_law_id) REFERENCES tax_laws(tax_law_id)
    );

    CREATE TABLE IF NOT EXISTS social_insurance_setup (
        setup_id INTEGER PRIMARY KEY AUTOINCREMENT,
        effective_year INTEGER NOT NULL UNIQUE,
        employee_share REAL NOT NULL DEFAULT 0.11,
        company_share REAL NOT NULL DEFAULT 0.1875,
        minimum_insurance_base REAL NOT NULL DEFAULT 0,
        maximum_insurance_base REAL NOT NULL DEFAULT 0,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS salary_calculation_setup (
        setting_name TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS payment_statuses (
        payment_status TEXT PRIMARY KEY,
        color TEXT
    );

    CREATE TABLE IF NOT EXISTS organizations (
        organization TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS sponsors (
        sponsor TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS departments (
        department TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS sections (
        section TEXT PRIMARY KEY,
        department TEXT,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS positions (
        position TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Active'
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        username TEXT NOT NULL UNIQUE,
        email TEXT,
        mobile TEXT,
        password_hash TEXT NOT NULL,
        role_id INTEGER,
        role TEXT,
        status TEXT NOT NULL DEFAULT 'Active',
        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
        last_login TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        username TEXT,
        user_role TEXT,
        action TEXT NOT NULL,
        module TEXT,
        table_name TEXT,
        entity TEXT NOT NULL,
        entity_id TEXT,
        old_values TEXT,
        new_values TEXT,
        changed_fields TEXT,
        ip_address TEXT,
        reason TEXT,
        approval_reference TEXT,
        details TEXT
    );
    """
    with db() as conn:
        conn.executescript(schema)
        conn.commit()


def seed_database() -> None:
    if fetch_one("SELECT COUNT(*) AS c FROM projects")["c"]:
        return

    created_at = now_text()
    with db() as conn:
        conn.executemany(
            """
            INSERT INTO projects (project_code, project_name, client_name, organization, location, status, start_date, notes, created_at)
            VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?)
            """,
            [
                ("CHEVRON", "Chevron", "Chevron", "AFM", "Egypt", "2020-01-01", "Seeded from employee default project", created_at),
                ("CHEVRON-UP", "Chevron Upstream", "Chevron Upstream", "AFM", "Egypt", "2020-01-01", "Seeded from employee default project", created_at),
            ],
        )

        conn.executemany("INSERT INTO allowance_types (allowance_type, status) VALUES (?, 'Active')", [(x,) for x in ALLOWANCE_TYPES])
        conn.executemany(
            "INSERT INTO payment_statuses (payment_status, color) VALUES (?, ?)",
            [("Pending", "#f59e0b"), ("Transferred", "#16a34a"), ("Hold", "#dc2626"), ("Cancelled", "#6b7280")],
        )
        conn.executemany(
            """
            INSERT INTO users (full_name, username, email, mobile, password_hash, role, status, created_by, created_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Active', 'system', ?, ?)
            """,
            [
                ("Super Administrator", "superadmin", "superadmin@example.local", "", hash_password("superadmin123"), "Super Admin", created_at, "Seeded default user"),
                ("Payroll Admin", "admin", "admin@example.local", "", hash_password("admin123"), "Admin", created_at, "Seeded default user"),
                ("Payroll Manager", "payroll", "payroll@example.local", "", hash_password("payroll123"), "Payroll Manager", created_at, "Seeded default user"),
                ("HR User", "hr", "hr@example.local", "", hash_password("hr123"), "HR User", created_at, "Seeded default user"),
                ("Finance User", "finance", "finance@example.local", "", hash_password("finance123"), "Finance User", created_at, "Seeded default user"),
                ("Viewer", "viewer", "viewer@example.local", "", hash_password("viewer123"), "Viewer", created_at, "Seeded default user"),
            ],
        )

        tax_defaults = [
            ("Egypt Law No. 175 of 2023", 2023, 15000, 0, 0.11, 0.1875, 1700, 10900, "Seeded law setup. Review with payroll/tax advisor before production use."),
            ("Egypt Salary Tax 2024+ Setup", 2024, 20000, 0, 0.11, 0.1875, 2000, 12600, "Seeded editable setup aligned to post-2024 published brackets; update for current company policy."),
        ]
        conn.executemany(
            """
            INSERT INTO tax_laws
            (law_name, effective_year, personal_exemption, additional_exemption, employee_insurance_share,
             company_insurance_share, minimum_insurance_base, maximum_insurance_base, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            [row + (created_at,) for row in tax_defaults],
        )
        law_2023 = conn.execute("SELECT tax_law_id FROM tax_laws WHERE effective_year = 2023").fetchone()[0]
        law_2024 = conn.execute("SELECT tax_law_id FROM tax_laws WHERE effective_year = 2024").fetchone()[0]
        bracket_2023 = [
            (law_2023, 1, 0, 30000, 0.00),
            (law_2023, 2, 30000, 45000, 0.10),
            (law_2023, 3, 45000, 60000, 0.15),
            (law_2023, 4, 60000, 200000, 0.20),
            (law_2023, 5, 200000, 400000, 0.225),
            (law_2023, 6, 400000, 1200000, 0.25),
            (law_2023, 7, 1200000, None, 0.275),
        ]
        bracket_2024 = [
            (law_2024, 1, 0, 40000, 0.00),
            (law_2024, 2, 40000, 55000, 0.10),
            (law_2024, 3, 55000, 70000, 0.15),
            (law_2024, 4, 70000, 200000, 0.20),
            (law_2024, 5, 200000, 400000, 0.225),
            (law_2024, 6, 400000, 1200000, 0.25),
            (law_2024, 7, 1200000, None, 0.275),
        ]
        conn.executemany(
            "INSERT INTO tax_brackets (tax_law_id, bracket_order, min_amount, max_amount, tax_rate) VALUES (?, ?, ?, ?, ?)",
            bracket_2023 + bracket_2024,
        )
        conn.executemany(
            """
            INSERT INTO social_insurance_setup
            (effective_year, employee_share, company_share, minimum_insurance_base, maximum_insurance_base, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (2023, 0.11, 0.1875, 1700, 10900, "Editable seed values"),
                (2024, 0.11, 0.1875, 2000, 12600, "Editable seed values"),
                (2026, 0.11, 0.1875, 2300, 14500, "Editable seed values"),
            ],
        )
        conn.executemany(
            "INSERT INTO salary_calculation_setup (setting_name, setting_value, notes) VALUES (?, ?, ?)",
            [
                ("basic_salary_source", "Use Employee Basic Salary", "Default: do not assume 30% of gross."),
                ("insurance_base_source", "Use Employee Basic Salary", "Can be changed to manual, gross, or percent of gross."),
                ("gross_basic_percentage", "30", "Used only when selected."),
                ("default_tax_law_id", str(law_2024), "Default tax law for calculations."),
            ],
        )

        lookup_values = {
            "organizations": sorted({r[1] for r in EMPLOYEE_SEED_DATA}),
            "sponsors": sorted({r[2] for r in EMPLOYEE_SEED_DATA}),
            "departments": sorted({r[5] for r in EMPLOYEE_SEED_DATA}),
            "positions": sorted({r[4] for r in EMPLOYEE_SEED_DATA}),
        }
        for table, values in lookup_values.items():
            col = table[:-1] if table != "positions" else "position"
            conn.executemany(f"INSERT INTO {table} ({col}, status) VALUES (?, 'Active')", [(x,) for x in values])
        sections = sorted({(r[6], r[5]) for r in EMPLOYEE_SEED_DATA})
        conn.executemany("INSERT INTO sections (section, department, status) VALUES (?, ?, 'Active')", sections)

        project_ids = {row["project_name"]: row["project_id"] for row in conn.execute("SELECT project_id, project_name FROM projects")}
        employees = []
        allocations = []
        allowances = []
        for row in EMPLOYEE_SEED_DATA:
            (
                employee_code,
                organization,
                sponsor,
                arabic_name,
                position,
                department,
                section,
                project,
                hiring_date,
                new_net_salary,
                new_allowance,
                new_net_earning,
            ) = row
            project_id = project_ids[project]
            basic_salary = float(new_net_salary)
            insurance_base = float(new_net_salary)
            employees.append(
                (
                    employee_code,
                    organization,
                    sponsor,
                    arabic_name,
                    position,
                    department,
                    section,
                    project_id,
                    parse_seed_date(hiring_date),
                    basic_salary,
                    float(new_net_salary),
                    0,
                    float(new_net_salary),
                    float(new_allowance),
                    float(new_net_earning),
                    insurance_base,
                    "Active",
                    "Seeded current employee",
                    created_at,
                )
            )
            allocations.append(
                (
                    employee_code,
                    project_id,
                    "Percentage",
                    100,
                    0,
                    parse_seed_date(hiring_date),
                    None,
                    1,
                    "Active",
                    "Seeded 100% default project allocation",
                    created_at,
                )
            )
            if float(new_allowance) > 0:
                allowances.append(
                    (
                        employee_code,
                        "Project Allowance",
                        "Seeded Current Allowance",
                        float(new_allowance),
                        "Fixed Amount",
                        "Net Allowance",
                        1,
                        0,
                        "Monthly",
                        "Follow Employee Project Allocation",
                        None,
                        parse_seed_date(hiring_date),
                        None,
                        department,
                        "Active",
                        "Seeded from New Allowance",
                        created_at,
                    )
                )
        conn.executemany(
            """
            INSERT INTO employees
            (employee_code, organization, sponsor, arabic_name, position, department, section, default_project_id,
             hiring_date, basic_salary, net_salary, gross_salary, new_net_salary, new_allowance, new_net_earning,
             insurance_salary_base, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            employees,
        )
        conn.executemany(
            """
            INSERT INTO employee_project_allocations
            (employee_code, project_id, allocation_type, allocation_percentage, fixed_allocation_amount,
             effective_from, effective_to, is_primary_project, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            allocations,
        )
        conn.executemany(
            """
            INSERT INTO employee_allowances
            (employee_code, allowance_type, allowance_name, amount, calculation_type, payment_type, taxable,
             social_insurance_applicable, recurring, project_charging_method, specific_project_id, effective_from,
             effective_to, department, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            allowances,
        )
        conn.execute(
            """
            INSERT INTO audit_log (event_time, username, action, entity, entity_id, details)
            VALUES (?, 'system', 'Seed database', 'database', 'initial', ?)
            """,
            (created_at, f"Seeded {len(employees)} employees, {len(allowances)} allowance rows, and default project allocations."),
        )
        conn.commit()


def table_columns(conn: Connection, table: str) -> set[str]:
    try:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except OperationalError:
        return set()


def add_column_if_missing(conn: Connection, table: str, column_name: str, definition: str) -> None:
    if column_name not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def create_extended_schema(conn: Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_code TEXT NOT NULL UNIQUE,
            permission_name TEXT NOT NULL,
            module_name TEXT,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_code TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'No Access',
            UNIQUE (role_id, permission_code),
            FOREIGN KEY (role_id) REFERENCES roles(id)
        );

        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission_code TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'No Access',
            override_type TEXT NOT NULL DEFAULT 'Allow',
            UNIQUE (user_id, permission_code),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_project_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project TEXT,
            access_type TEXT NOT NULL DEFAULT 'All',
            UNIQUE (user_id, project, access_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_department_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department TEXT,
            access_type TEXT NOT NULL DEFAULT 'All',
            UNIQUE (user_id, department, access_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            login_time TEXT,
            logout_time TEXT,
            session_status TEXT,
            ip_address TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            requested_by TEXT,
            requested_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            approved_by TEXT,
            approved_at TEXT,
            rejection_reason TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS approval_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER,
            request_type TEXT,
            record_id TEXT,
            action TEXT NOT NULL,
            action_by TEXT,
            action_at TEXT NOT NULL,
            comments TEXT,
            old_status TEXT,
            new_status TEXT,
            FOREIGN KEY (approval_request_id) REFERENCES approval_requests(id)
        );

        CREATE TABLE IF NOT EXISTS employee_bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            bonus_date TEXT NOT NULL,
            bonus_type TEXT NOT NULL,
            bonus_category TEXT NOT NULL,
            bonus_amount_entered REAL NOT NULL DEFAULT 0,
            net_bonus_amount REAL NOT NULL DEFAULT 0,
            gross_bonus_amount REAL NOT NULL DEFAULT 0,
            gross_before REAL NOT NULL DEFAULT 0,
            gross_after REAL NOT NULL DEFAULT 0,
            gross_difference REAL NOT NULL DEFAULT 0,
            net_before REAL NOT NULL DEFAULT 0,
            net_after REAL NOT NULL DEFAULT 0,
            net_increase REAL NOT NULL DEFAULT 0,
            tax_before REAL NOT NULL DEFAULT 0,
            tax_after REAL NOT NULL DEFAULT 0,
            tax_difference REAL NOT NULL DEFAULT 0,
            employee_insurance_before REAL NOT NULL DEFAULT 0,
            employee_insurance_after REAL NOT NULL DEFAULT 0,
            employee_insurance_difference REAL NOT NULL DEFAULT 0,
            company_insurance_before REAL NOT NULL DEFAULT 0,
            company_insurance_after REAL NOT NULL DEFAULT 0,
            company_insurance_difference REAL NOT NULL DEFAULT 0,
            company_cost_before REAL NOT NULL DEFAULT 0,
            company_cost_after REAL NOT NULL DEFAULT 0,
            company_cost_difference REAL NOT NULL DEFAULT 0,
            project_charging_method TEXT NOT NULL DEFAULT 'Follow Employee Project Allocation',
            charged_project INTEGER,
            payment_status TEXT NOT NULL DEFAULT 'Planned',
            approval_status TEXT NOT NULL DEFAULT 'Draft',
            approved_by TEXT,
            approved_date TEXT,
            paid_date TEXT,
            payment_reference TEXT,
            bonus_reason TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code),
            FOREIGN KEY (charged_project) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS bonus_project_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonus_id INTEGER NOT NULL,
            employee_code TEXT NOT NULL,
            project TEXT NOT NULL,
            allocation_percentage REAL NOT NULL DEFAULT 0,
            allocated_net_bonus REAL NOT NULL DEFAULT 0,
            allocated_gross_bonus REAL NOT NULL DEFAULT 0,
            allocated_tax_difference REAL NOT NULL DEFAULT 0,
            allocated_employee_insurance_difference REAL NOT NULL DEFAULT 0,
            allocated_company_insurance_difference REAL NOT NULL DEFAULT 0,
            allocated_company_cost_difference REAL NOT NULL DEFAULT 0,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            FOREIGN KEY (bonus_id) REFERENCES employee_bonuses(id)
        );

        CREATE TABLE IF NOT EXISTS salary_revisions (
            revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            old_basic_salary REAL DEFAULT 0,
            new_basic_salary REAL DEFAULT 0,
            old_net_salary REAL DEFAULT 0,
            new_net_salary REAL DEFAULT 0,
            old_allowance REAL DEFAULT 0,
            new_allowance REAL DEFAULT 0,
            old_net_earning REAL DEFAULT 0,
            new_net_earning REAL DEFAULT 0,
            old_gross_salary REAL DEFAULT 0,
            new_gross_salary REAL DEFAULT 0,
            gross_difference REAL DEFAULT 0,
            net_difference REAL DEFAULT 0,
            company_cost_before REAL DEFAULT 0,
            company_cost_after REAL DEFAULT 0,
            company_cost_difference REAL DEFAULT 0,
            effective_from TEXT,
            effective_to TEXT,
            revision_type TEXT,
            reason TEXT,
            approval_status TEXT DEFAULT 'Draft',
            approved_by TEXT,
            approved_date TEXT,
            applied INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
        );

        CREATE TABLE IF NOT EXISTS payroll_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            lock_status TEXT NOT NULL DEFAULT 'Open',
            locked_by TEXT,
            locked_at TEXT,
            closed_by TEXT,
            closed_at TEXT,
            reopened_by TEXT,
            reopened_at TEXT,
            reopen_reason TEXT,
            UNIQUE (year, month)
        );

        CREATE TABLE IF NOT EXISTS bank_transfer_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            english_name TEXT,
            bank_name TEXT,
            bank_branch TEXT,
            bank_account_iban TEXT,
            net_transfer_amount REAL NOT NULL DEFAULT 0,
            payment_month INTEGER NOT NULL,
            payment_year INTEGER NOT NULL,
            transfer_date TEXT,
            transfer_reference TEXT,
            payment_status TEXT NOT NULL DEFAULT 'Pending',
            actual_bank_transfer_amount REAL DEFAULT 0,
            notes TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS bank_reconciliation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT,
            bank_account_iban TEXT,
            transfer_reference TEXT,
            payroll_net_transfer_amount REAL DEFAULT 0,
            actual_bank_transfer_amount REAL DEFAULT 0,
            difference REAL DEFAULT 0,
            transfer_date TEXT,
            bank_reference TEXT,
            status TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT,
            severity TEXT,
            message TEXT NOT NULL,
            module_name TEXT,
            record_id TEXT,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT,
            resolved_by TEXT,
            resolved_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS employee_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT,
            upload_date TEXT,
            expiry_date TEXT,
            uploaded_by TEXT,
            status TEXT NOT NULL DEFAULT 'Valid',
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            working_days REAL DEFAULT 0,
            paid_days REAL DEFAULT 0,
            unpaid_leave_days REAL DEFAULT 0,
            absence_days REAL DEFAULT 0,
            deduction_days REAL DEFAULT 0,
            daily_rate REAL DEFAULT 0,
            deduction_amount REAL DEFAULT 0,
            reason TEXT,
            approval_status TEXT DEFAULT 'Draft',
            notes TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS overtime_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            project INTEGER,
            overtime_date TEXT,
            overtime_hours REAL DEFAULT 0,
            hourly_rate REAL DEFAULT 0,
            overtime_multiplier REAL DEFAULT 1,
            overtime_amount REAL DEFAULT 0,
            payment_type TEXT DEFAULT 'Net',
            taxable INTEGER DEFAULT 1,
            insurance_applicable INTEGER DEFAULT 0,
            approval_status TEXT DEFAULT 'Draft',
            reason TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_name TEXT NOT NULL,
            scenario_type TEXT,
            year INTEGER,
            month INTEGER,
            target_project INTEGER,
            target_department TEXT,
            input_value REAL DEFAULT 0,
            current_payroll_cost REAL DEFAULT 0,
            new_payroll_cost REAL DEFAULT 0,
            cost_difference REAL DEFAULT 0,
            tax_difference REAL DEFAULT 0,
            insurance_difference REAL DEFAULT 0,
            approval_status TEXT DEFAULT 'Draft',
            created_by TEXT,
            created_at TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS scenario_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id INTEGER NOT NULL,
            employee_code TEXT,
            current_cost REAL DEFAULT 0,
            new_cost REAL DEFAULT 0,
            cost_difference REAL DEFAULT 0,
            details TEXT,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
        );

        CREATE TABLE IF NOT EXISTS backup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_name TEXT,
            backup_path TEXT,
            backup_type TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS organization_setup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_code TEXT NOT NULL UNIQUE,
            organization_name TEXT NOT NULL,
            tax_registration_number TEXT,
            social_insurance_number TEXT,
            address TEXT,
            bank_account TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS payroll_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization TEXT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            cutoff_date TEXT,
            payroll_generation_date TEXT,
            hr_review_date TEXT,
            finance_approval_date TEXT,
            bank_transfer_date TEXT,
            payroll_close_date TEXT,
            status TEXT DEFAULT 'Planned',
            notes TEXT,
            UNIQUE (organization, year, month)
        );

        CREATE TABLE IF NOT EXISTS tax_exemptions (
            exemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_law_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            personal_exemption_annual REAL NOT NULL DEFAULT 0,
            additional_exemption_annual REAL NOT NULL DEFAULT 0,
            tax_free_bracket_annual REAL NOT NULL DEFAULT 0,
            total_annual_exemption REAL NOT NULL DEFAULT 0,
            round_taxable_income_down_to_nearest_10 INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'Active',
            notes TEXT,
            UNIQUE (tax_law_id, year),
            FOREIGN KEY (tax_law_id) REFERENCES tax_laws(tax_law_id)
        );
        """
    )


def migrate_users_table(conn: Connection) -> None:
    columns = table_columns(conn, "users")
    if "id" not in columns:
        conn.execute("ALTER TABLE users RENAME TO users_old")
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                mobile TEXT,
                password_hash TEXT NOT NULL,
                role_id INTEGER,
                role TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                last_login TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                notes TEXT
            );
            """
        )
        for row in conn.execute("SELECT * FROM users_old").fetchall():
            row_dict = dict(row)
            username = row_dict.get("username", "")
            conn.execute(
                """
                INSERT INTO users (full_name, username, password_hash, role, status, created_by, created_at, notes)
                VALUES (?, ?, ?, ?, ?, 'system', ?, ?)
                """,
                (
                    username.title(),
                    username,
                    row_dict.get("password_hash", hash_password("changeme")),
                    row_dict.get("role", "Viewer"),
                    row_dict.get("status", "Active"),
                    row_dict.get("created_at", now_text()),
                    "Migrated from initial user table",
                ),
            )
        conn.execute("DROP TABLE users_old")
    else:
        user_columns = table_columns(conn, "users")
        additions = {
            "full_name": "full_name TEXT",
            "email": "email TEXT",
            "mobile": "mobile TEXT",
            "role_id": "role_id INTEGER",
            "role": "role TEXT",
            "failed_login_attempts": "failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "last_login": "last_login TEXT",
            "created_by": "created_by TEXT",
            "updated_at": "updated_at TEXT",
            "notes": "notes TEXT",
        }
        for column_name, definition in additions.items():
            if column_name not in user_columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {definition}")


def permission_catalog() -> list[tuple[str, str, str, str]]:
    pages = globals().get("PAGES", {})
    rows = []
    for page_name in pages:
        code = f"PAGE:{page_name}"
        rows.append((code, page_name, "Page Access", f"Access to {page_name}"))
    for action in ACTION_PERMISSIONS:
        rows.append((action, action, "Action / Salary", action))
    return rows


def seed_permissions(conn: Connection) -> None:
    created_at = now_text()
    for role in DEFAULT_ROLES:
        conn.execute(
            """
            INSERT INTO roles (role_name, description, status, created_at)
            VALUES (?, ?, 'Active', ?)
            ON CONFLICT(role_name) DO UPDATE SET description = excluded.description, status = 'Active'
            """,
            (role, f"Default {role} role", created_at),
        )
    for code, name, module, description in permission_catalog():
        conn.execute(
            """
            INSERT INTO permissions (permission_code, permission_name, module_name, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(permission_code) DO UPDATE SET permission_name = excluded.permission_name,
                module_name = excluded.module_name, description = excluded.description
            """,
            (code, name, module, description),
        )

    page_sets = {
        "Viewer": {"Executive Dashboard", "Reports", "Bonus Reports", "Yearly Summary", "Project Yearly Summary", "Employee Bonus History"},
        "HR User": {"Executive Dashboard", "Employees", "Employee Allowances", "Employee Project Allocation", "Employee Bonus History", "Salary Revision History", "Employee Documents", "Attendance Adjustments", "Overtime", "Reports", "Data Quality Center"},
        "Finance User": {"Executive Dashboard", "Payroll Transactions", "Payroll Project Cost Allocation", "Payroll Run Center", "Bonus Register", "Bonus Reports", "Bank Transfer", "Bank Reconciliation", "Employee Cost Sheet", "Project Payroll Cost Dashboard", "Payroll Variance Report", "Reports", "Yearly Summary", "Project Yearly Summary", "Executive Reports Package"},
        "Payroll Manager": {"Executive Dashboard", "Projects", "Employees", "Employee Project Allocation", "Employee Allowances", "Payroll Run Center", "Payroll Transactions", "Payroll Project Cost Allocation", "Net to Gross Calculator", "Bonus Calculator", "Bonus Register", "Employee Bonus History", "Bonus Reports", "Bonus Simulations", "Salary Revision History", "Payroll Approvals & Locking", "Payroll Variance Report", "Bank Transfer", "Bank Reconciliation", "Employee Cost Sheet", "Project Payroll Cost Dashboard", "Alerts Center", "Employee Documents", "Attendance Adjustments", "Overtime", "Payslips", "Scenario Simulation Center", "Import Templates", "Reports", "Yearly Summary", "Project Yearly Summary", "Import / Export", "Data Quality Center", "Executive Reports Package"},
        "Project Manager": {"Executive Dashboard", "Projects", "Employees", "Payroll Transactions", "Payroll Project Cost Allocation", "Bonus Register", "Employee Bonus History", "Bonus Reports", "Employee Cost Sheet", "Project Payroll Cost Dashboard", "Reports", "Yearly Summary", "Project Yearly Summary", "Alerts Center"},
    }
    salary_roles = {
        "Super Admin": ACTION_PERMISSIONS,
        "Admin": ACTION_PERMISSIONS,
        "Payroll Manager": [p for p in ACTION_PERMISSIONS if p != "Can Manage Users"],
        "Finance User": ["Can View Salary", "Can View Net Salary", "Can View Gross Salary", "Can View Tax", "Can View Social Insurance", "Can View Company Cost", "Can View Bonus Amount", "Can Export Salary Data", "Can Export Data", "Can Mark Payroll as Transferred", "Can Approve Bonus", "Can Mark Bonus as Paid"],
        "HR User": ["Can Add Employee", "Can Edit Employee", "Can Add Allowance", "Can Edit Allowance", "Can View Net Salary", "Can View Bonus Amount", "Can Export Data"],
        "Project Manager": ["Can View Bonus Amount", "Can Export Data", "Can Approve Bonus"],
        "Viewer": ["Can Export Data"],
    }
    for role in DEFAULT_ROLES:
        role_id = conn.execute("SELECT id FROM roles WHERE role_name = ?", (role,)).fetchone()["id"]
        for code, name, module, _ in permission_catalog():
            access = "No Access"
            if role == "Super Admin":
                access = "Full Access"
            elif role == "Admin":
                access = "Full Access" if code != "Can Manage Users" else "Edit"
            elif code.startswith("PAGE:"):
                page_name = code.split(":", 1)[1]
                if page_name in page_sets.get(role, set()):
                    access = "View Only" if role in {"Viewer", "Project Manager"} else "Full Access"
            elif code in salary_roles.get(role, []):
                access = "Full Access"
            conn.execute(
                """
                INSERT INTO role_permissions (role_id, permission_code, access_level)
                VALUES (?, ?, ?)
                ON CONFLICT(role_id, permission_code) DO NOTHING
                """,
                (role_id, code, access),
            )


def seed_default_users(conn: Connection) -> None:
    users = [
        ("Super Administrator", "superadmin", "superadmin@example.local", "", "superadmin123", "Super Admin"),
        ("Payroll Admin", "admin", "admin@example.local", "", "admin123", "Admin"),
        ("Payroll Manager", "payroll", "payroll@example.local", "", "payroll123", "Payroll Manager"),
        ("HR User", "hr", "hr@example.local", "", "hr123", "HR User"),
        ("Finance User", "finance", "finance@example.local", "", "finance123", "Finance User"),
        ("Viewer", "viewer", "viewer@example.local", "", "viewer123", "Viewer"),
    ]
    for full_name, username, email, mobile, password, role in users:
        role_row = conn.execute("SELECT id FROM roles WHERE role_name = ?", (role,)).fetchone()
        role_id = role_row["id"] if role_row else None
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE users
                SET role_id = COALESCE(role_id, ?), role = COALESCE(role, ?), full_name = COALESCE(full_name, ?),
                    email = COALESCE(email, ?), mobile = COALESCE(mobile, ''), status = COALESCE(status, 'Active')
                WHERE username = ?
                """,
                (role_id, role, full_name, email, username),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (full_name, username, email, mobile, password_hash, role_id, role, status, created_by, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', 'system', ?, 'Seeded default user')
                """,
                (full_name, username, email, mobile, hash_password(password), role_id, role, now_text()),
            )

    for user in conn.execute("SELECT id FROM users").fetchall():
        conn.execute(
            """
            INSERT OR IGNORE INTO user_project_access (user_id, project, access_type)
            VALUES (?, 'All Projects', 'All')
            """,
            (user["id"],),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO user_department_access (user_id, department, access_type)
            VALUES (?, 'All Departments', 'All')
            """,
            (user["id"],),
        )


def tax_income_ranges_for_brackets(base_brackets: list[tuple[float, float | None, float]]) -> list[tuple[float, float | None, list[tuple[float, float | None, float]]]]:
    return [
        (0, 600000, base_brackets),
        (600000, 700000, [(0, base_brackets[1][1], base_brackets[1][2])] + base_brackets[2:]),
        (700000, 800000, [(0, base_brackets[2][1], base_brackets[2][2])] + base_brackets[3:]),
        (800000, 900000, [(0, base_brackets[3][1], base_brackets[3][2])] + base_brackets[4:]),
        (900000, 1200000, [(0, base_brackets[4][1], base_brackets[4][2]), base_brackets[5], base_brackets[6]]),
        (1200000, None, [(0, None, 0.275)]),
    ]


def apply_egypt_tax_preset(
    law_name: str,
    law_number: str,
    effective_from: str,
    effective_year: int,
    personal_exemption: float,
    additional_exemptions_by_year: dict[int, float],
    tax_free_bracket: float,
    brackets: list[tuple[float, float | None, float]],
    make_default: bool,
) -> int:
    with db() as conn:
        existing = conn.execute("SELECT tax_law_id FROM tax_laws WHERE law_number = ? OR law_name = ?", (law_number, law_name)).fetchone()
        if make_default:
            conn.execute("UPDATE tax_laws SET is_default = 0")
        if existing:
            tax_law_id = existing["tax_law_id"]
            conn.execute(
                """
                UPDATE tax_laws
                SET law_name = ?, law_number = ?, effective_year = ?, effective_from = ?, status = 'Active',
                    is_default = ?, personal_exemption = ?, additional_exemption = ?, updated_at = ?
                WHERE tax_law_id = ?
                """,
                (law_name, law_number, effective_year, effective_from, 1 if make_default else 0, personal_exemption, additional_exemptions_by_year.get(effective_year, 0), now_text(), tax_law_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO tax_laws
                (law_name, law_number, effective_year, effective_from, is_default, personal_exemption,
                 additional_exemption, employee_insurance_share, company_insurance_share,
                 minimum_insurance_base, maximum_insurance_base, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0.11, 0.1875, 2600, 16700, 'Active', ?, ?)
                """,
                (law_name, law_number, effective_year, effective_from, 1 if make_default else 0, personal_exemption, additional_exemptions_by_year.get(effective_year, 0), "Applied Egyptian tax preset", now_text()),
            )
            tax_law_id = cur.lastrowid

        years = sorted(set(additional_exemptions_by_year.keys()) | {effective_year})
        for year in years:
            additional = additional_exemptions_by_year.get(year, additional_exemptions_by_year.get(effective_year, 0))
            conn.execute(
                """
                INSERT INTO tax_exemptions
                (tax_law_id, year, personal_exemption_annual, additional_exemption_annual,
                 tax_free_bracket_annual, total_annual_exemption, round_taxable_income_down_to_nearest_10,
                 status, notes)
                VALUES (?, ?, ?, ?, ?, ?, 1, 'Active', ?)
                ON CONFLICT(tax_law_id, year) DO UPDATE SET
                    personal_exemption_annual = excluded.personal_exemption_annual,
                    additional_exemption_annual = excluded.additional_exemption_annual,
                    tax_free_bracket_annual = excluded.tax_free_bracket_annual,
                    total_annual_exemption = excluded.total_annual_exemption,
                    round_taxable_income_down_to_nearest_10 = excluded.round_taxable_income_down_to_nearest_10,
                    status = 'Active'
                """,
                (tax_law_id, year, personal_exemption, additional, tax_free_bracket, personal_exemption + additional + tax_free_bracket, "Editable seeded exemption"),
            )
            conn.execute("DELETE FROM tax_brackets WHERE tax_law_id = ? AND year = ?", (tax_law_id, year))
            order = 1
            for income_level_from, income_level_to, bracket_rows in tax_income_ranges_for_brackets(brackets):
                for income_from, income_to, rate in bracket_rows:
                    conn.execute(
                        """
                        INSERT INTO tax_brackets
                        (tax_law_id, year, income_from, income_to, min_amount, max_amount, tax_rate,
                         bracket_order, applies_for_income_level_from, applies_for_income_level_to,
                         is_skipped_for_higher_income, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
                        """,
                        (
                            tax_law_id,
                            year,
                            income_from,
                            income_to,
                            income_from,
                            income_to,
                            rate,
                            order,
                            income_level_from,
                            income_level_to,
                            1 if income_level_to is not None and income_level_to <= 1200000 else 0,
                        ),
                    )
                    order += 1
        if make_default:
            conn.execute(
                """
                INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
                VALUES ('default_tax_law_id', ?, 'Default tax law for calculations.')
                ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value
                """,
                (str(tax_law_id),),
            )
        conn.commit()
        return tax_law_id


def apply_law_175_2023_preset(make_default: bool = False, audit_event: bool = True) -> int:
    tax_law_id = apply_egypt_tax_preset(
        "Egypt Income Tax Law 175/2023",
        "175/2023",
        "2023-10-31",
        2023,
        15000,
        {2023: 0},
        30000,
        EGYPT_TAX_175_BRACKETS,
        make_default,
    )
    if audit_event:
        audit("Setup changes", "tax_laws", tax_law_id, "Applied Egypt Tax Law 175/2023 Preset")
    return tax_law_id


def apply_current_egypt_tax_preset(make_default: bool = True, audit_event: bool = True) -> int:
    tax_law_id = apply_egypt_tax_preset(
        "Egypt Current Income Tax Setup 2024/2026",
        "Law 7/2024 / Current",
        "2024-02-21",
        2024,
        20000,
        {2024: 20000, 2025: 20000, 2026: 20000},
        40000,
        EGYPT_CURRENT_BRACKETS,
        make_default,
    )
    if audit_event:
        audit("Setup changes", "tax_laws", tax_law_id, "Applied Current Egypt Tax Preset 2024/2026")
    return tax_law_id


def seed_current_tax_if_missing(conn: Connection) -> None:
    if not conn.execute("SELECT COUNT(*) AS c FROM tax_exemptions").fetchone()["c"]:
        conn.commit()
        apply_law_175_2023_preset(make_default=False, audit_event=False)
        apply_current_egypt_tax_preset(make_default=True, audit_event=False)


def run_migrations() -> None:
    with db() as conn:
        migrate_users_table(conn)
        create_extended_schema(conn)

        employee_additions = {
            "english_name": "english_name TEXT",
            "bank_name": "bank_name TEXT",
            "bank_branch": "bank_branch TEXT",
            "bank_account_iban": "bank_account_iban TEXT",
        }
        for column_name, definition in employee_additions.items():
            add_column_if_missing(conn, "employees", column_name, definition)

        payroll_run_additions = {
            "approval_status": "approval_status TEXT DEFAULT 'Generated'",
            "updated_at": "updated_at TEXT",
            "submitted_by": "submitted_by TEXT",
            "submitted_at": "submitted_at TEXT",
            "hr_reviewed_by": "hr_reviewed_by TEXT",
            "hr_reviewed_at": "hr_reviewed_at TEXT",
            "finance_reviewed_by": "finance_reviewed_by TEXT",
            "finance_reviewed_at": "finance_reviewed_at TEXT",
            "approved_by": "approved_by TEXT",
            "approved_at": "approved_at TEXT",
            "reopened_by": "reopened_by TEXT",
            "reopened_at": "reopened_at TEXT",
            "approval_comments": "approval_comments TEXT",
        }
        for column_name, definition in payroll_run_additions.items():
            add_column_if_missing(conn, "payroll_runs", column_name, definition)

        payroll_transaction_additions = {
            "bonus_amount": "bonus_amount REAL DEFAULT 0",
            "overtime_amount": "overtime_amount REAL DEFAULT 0",
            "attendance_deduction": "attendance_deduction REAL DEFAULT 0",
            "other_deductions": "other_deductions REAL DEFAULT 0",
            "actual_bank_transfer_amount": "actual_bank_transfer_amount REAL DEFAULT 0",
            "bank_reconciliation_status": "bank_reconciliation_status TEXT",
        }
        for column_name, definition in payroll_transaction_additions.items():
            add_column_if_missing(conn, "payroll_transactions", column_name, definition)

        audit_additions = {
            "user_role": "user_role TEXT",
            "module": "module TEXT",
            "table_name": "table_name TEXT",
            "old_values": "old_values TEXT",
            "new_values": "new_values TEXT",
            "changed_fields": "changed_fields TEXT",
            "ip_address": "ip_address TEXT",
            "reason": "reason TEXT",
            "approval_reference": "approval_reference TEXT",
        }
        for column_name, definition in audit_additions.items():
            add_column_if_missing(conn, "audit_log", column_name, definition)

        tax_law_additions = {
            "law_number": "law_number TEXT",
            "effective_from": "effective_from TEXT",
            "effective_to": "effective_to TEXT",
            "is_default": "is_default INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, definition in tax_law_additions.items():
            add_column_if_missing(conn, "tax_laws", column_name, definition)

        tax_bracket_additions = {
            "year": "year INTEGER",
            "income_from": "income_from REAL",
            "income_to": "income_to REAL",
            "applies_for_income_level_from": "applies_for_income_level_from REAL",
            "applies_for_income_level_to": "applies_for_income_level_to REAL",
            "is_skipped_for_higher_income": "is_skipped_for_higher_income INTEGER NOT NULL DEFAULT 0",
            "status": "status TEXT NOT NULL DEFAULT 'Active'",
        }
        for column_name, definition in tax_bracket_additions.items():
            add_column_if_missing(conn, "tax_brackets", column_name, definition)
        conn.execute("UPDATE tax_brackets SET income_from = COALESCE(income_from, min_amount), income_to = COALESCE(income_to, max_amount), year = COALESCE(year, (SELECT effective_year FROM tax_laws WHERE tax_laws.tax_law_id = tax_brackets.tax_law_id)), status = COALESCE(status, 'Active')")

        insurance_additions = {
            "effective_from": "effective_from TEXT",
            "effective_to": "effective_to TEXT",
            "minimum_insurance_salary": "minimum_insurance_salary REAL",
            "maximum_insurance_salary": "maximum_insurance_salary REAL",
            "employee_share_percent": "employee_share_percent REAL",
            "company_share_percent": "company_share_percent REAL",
            "insurance_base_source": "insurance_base_source TEXT DEFAULT 'Employee Insurance Salary/Base'",
            "status": "status TEXT DEFAULT 'Active'",
        }
        for column_name, definition in insurance_additions.items():
            add_column_if_missing(conn, "social_insurance_setup", column_name, definition)
        conn.execute(
            """
            UPDATE social_insurance_setup
            SET minimum_insurance_salary = COALESCE(minimum_insurance_salary, minimum_insurance_base),
                maximum_insurance_salary = COALESCE(maximum_insurance_salary, maximum_insurance_base),
                employee_share_percent = COALESCE(employee_share_percent, employee_share * 100),
                company_share_percent = COALESCE(company_share_percent, company_share * 100),
                insurance_base_source = COALESCE(insurance_base_source, 'Employee Insurance Salary/Base'),
                status = COALESCE(status, 'Active')
            """
        )
        for insurance_year in (2024, 2025, 2026):
            conn.execute(
                """
                INSERT INTO social_insurance_setup
                (effective_year, effective_from, effective_to, employee_share, company_share,
                 minimum_insurance_base, maximum_insurance_base, minimum_insurance_salary,
                 maximum_insurance_salary, employee_share_percent, company_share_percent,
                 insurance_base_source, status, notes)
                VALUES (?, ?, ?, 0.11, 0.1875, 2600, 16700, 2600, 16700, 11, 18.75,
                        'Employee Insurance Salary/Base', 'Active', 'Editable Egyptian social insurance default')
                ON CONFLICT(effective_year) DO UPDATE SET
                    minimum_insurance_salary = CASE WHEN social_insurance_setup.notes LIKE 'Editable seed%' OR social_insurance_setup.notes IS NULL THEN 2600 ELSE COALESCE(social_insurance_setup.minimum_insurance_salary, 2600) END,
                    maximum_insurance_salary = CASE WHEN social_insurance_setup.notes LIKE 'Editable seed%' OR social_insurance_setup.notes IS NULL THEN 16700 ELSE COALESCE(social_insurance_setup.maximum_insurance_salary, 16700) END,
                    employee_share_percent = CASE WHEN social_insurance_setup.notes LIKE 'Editable seed%' OR social_insurance_setup.notes IS NULL THEN 11 ELSE COALESCE(social_insurance_setup.employee_share_percent, 11) END,
                    company_share_percent = CASE WHEN social_insurance_setup.notes LIKE 'Editable seed%' OR social_insurance_setup.notes IS NULL THEN 18.75 ELSE COALESCE(social_insurance_setup.company_share_percent, 18.75) END,
                    insurance_base_source = COALESCE(social_insurance_setup.insurance_base_source, 'Employee Insurance Salary/Base'),
                    status = COALESCE(social_insurance_setup.status, 'Active')
                """,
                (insurance_year, f"{insurance_year}-01-01", f"{insurance_year}-12-31"),
            )

        seed_permissions(conn)
        seed_default_users(conn)

        conn.execute(
            """
            INSERT INTO organization_setup (organization_code, organization_name, status, created_at)
            VALUES ('AFM', 'AFM', 'Active', ?)
            ON CONFLICT(organization_code) DO UPDATE SET organization_name = excluded.organization_name
            """,
            (now_text(),),
        )
        conn.executemany(
            """
            INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_name) DO NOTHING
            """,
            [
                ("round_taxable_income_down_to_nearest_10", "Yes", "Egypt tax rounding option."),
                ("net_to_gross_tolerance", "0.01", "Tolerance for net-to-gross binary search."),
                ("net_to_gross_max_iterations", "90", "Maximum iterations for net-to-gross binary search."),
                ("gross_up_method", "Binary Search", "Gross-up calculation method."),
                ("fixed_insurance_base_amount", "0", "Used when Insurance Base Source is Fixed Manual Amount."),
                ("statutory_allowance_percentage", "30", "Allowance component percentage used by sheet-style basic salary rule."),
                ("insurance_gross_divisor", "1.3", "Gross divisor used by sheet-style social insurance base rule."),
            ],
        )
        if not conn.execute("SELECT setting_value FROM salary_calculation_setup WHERE setting_name = 'sheet_salary_formula_migration_applied'").fetchone():
            conn.executemany(
                """
                INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value, notes = excluded.notes
                """,
                [
                    ("basic_salary_source", "Gross Salary Excluding Statutory Allowances", "Default updated from Net To Gross Osama.xlsx: basic = gross - statutory allowances."),
                    ("insurance_base_source", "Gross Salary / 1.3", "Default updated from Net To Gross Osama.xlsx: social base = gross / 1.3 with min/max limits."),
                    ("statutory_allowance_percentage", "30", "Sheet formula: allowance component = social insurance base x 30%."),
                    ("insurance_gross_divisor", "1.3", "Sheet formula: social insurance base is derived from gross / 1.3."),
                    ("sheet_salary_formula_migration_applied", now_text(), "Prevents overwriting future user edits to salary formula defaults."),
                ],
            )
            conn.execute(
                """
                UPDATE social_insurance_setup
                SET minimum_insurance_salary = 2700,
                    minimum_insurance_base = 2700,
                    maximum_insurance_salary = 16700,
                    maximum_insurance_base = 16700,
                    employee_share_percent = 11,
                    employee_share = 0.11,
                    company_share_percent = 18.75,
                    company_share = 0.1875,
                    insurance_base_source = 'Gross Salary / 1.3',
                    notes = COALESCE(notes || '; ', '') || 'Updated from Net To Gross Osama.xlsx formula defaults'
                WHERE effective_year = 2026
                """
            )
        conn.commit()
        seed_current_tax_if_missing(conn)


def init_app() -> None:
    create_schema()
    seed_database()
    run_migrations()


def option_rows(table: str, value_col: str, where: str = "status = 'Active'") -> list[str]:
    df = read_df(f"SELECT {value_col} FROM {table} WHERE {where} ORDER BY {value_col}")
    return df[value_col].tolist()


def projects_df(active_only: bool = False) -> pd.DataFrame:
    where = "WHERE status = 'Active'" if active_only else ""
    df = read_df(
        f"""
        SELECT project_id, project_code, project_name, client_name, organization, location, status,
               start_date, end_date, notes
        FROM projects {where}
        ORDER BY project_name
        """
    )
    allowed = allowed_projects()
    if allowed is not None:
        df = df[df["project_name"].isin(allowed)]
    return df


def project_lookup(active_only: bool = True) -> dict[str, int]:
    df = projects_df(active_only)
    return dict(zip(df["project_name"], df["project_id"]))


def project_name(project_id: int | None) -> str:
    if not project_id:
        return ""
    row = fetch_one("SELECT project_name FROM projects WHERE project_id = ?", (project_id,))
    return row["project_name"] if row else ""


def employee_options(active_only: bool = True) -> pd.DataFrame:
    where = "WHERE e.status = 'Active'" if active_only else ""
    df = read_df(
        f"""
        SELECT e.employee_code, e.arabic_name, e.department, e.section, e.position, e.sponsor,
               p.project_name AS default_project
        FROM employees e
        LEFT JOIN projects p ON p.project_id = e.default_project_id
        {where}
        ORDER BY e.employee_code
        """
    )
    return restrict_df_by_access(df, "default_project", "department")


def active_tax_law(year: int | None = None, tax_law_id: int | None = None) -> Row:
    if tax_law_id:
        row = fetch_one("SELECT * FROM tax_laws WHERE tax_law_id = ?", (tax_law_id,))
        if row:
            return row
    row = fetch_one("SELECT * FROM tax_laws WHERE status = 'Active' AND is_default = 1 ORDER BY tax_law_id DESC LIMIT 1")
    if row and not year:
        return row
    if year:
        row = fetch_one(
            """
            SELECT * FROM tax_laws
            WHERE status = 'Active'
              AND (
                    (effective_from IS NOT NULL AND effective_from <= ?)
                    OR (effective_from IS NULL AND effective_year <= ?)
                  )
              AND (effective_to IS NULL OR effective_to >= ?)
            ORDER BY is_default DESC, effective_from DESC, effective_year DESC, tax_law_id DESC
            LIMIT 1
            """,
            (f"{year}-12-31", year, f"{year}-01-01"),
        )
        if row:
            return row
    setting = fetch_one("SELECT setting_value FROM salary_calculation_setup WHERE setting_name = 'default_tax_law_id'")
    if setting:
        row = fetch_one("SELECT * FROM tax_laws WHERE tax_law_id = ?", (safe_float(setting["setting_value"]),))
        if row:
            return row
    return fetch_one("SELECT * FROM tax_laws ORDER BY effective_year DESC LIMIT 1")


def tax_brackets(tax_law_id: int, year: int | None = None, annual_taxable_income: float | None = None) -> list[Row]:
    params: list = [tax_law_id]
    year_filter = ""
    if year:
        bracket_year = fetch_one("SELECT MAX(year) AS y FROM tax_brackets WHERE tax_law_id = ? AND year <= ?", (tax_law_id, year))
        if bracket_year and bracket_year["y"]:
            year_filter = "AND year = ?"
            params.append(bracket_year["y"])
    income_filter = ""
    if annual_taxable_income is not None:
        income_filter = """
        AND (applies_for_income_level_from IS NULL OR applies_for_income_level_from < ? OR applies_for_income_level_from = 0)
        AND (applies_for_income_level_to IS NULL OR ? <= applies_for_income_level_to)
        """
        params.extend([annual_taxable_income, annual_taxable_income])
    rows = fetch_all(
        f"""
        SELECT * FROM tax_brackets
        WHERE tax_law_id = ?
          {year_filter}
          {income_filter}
          AND COALESCE(status, 'Active') = 'Active'
        ORDER BY bracket_order
        """,
        tuple(params),
    )
    if rows:
        return rows
    return fetch_all("SELECT * FROM tax_brackets WHERE tax_law_id = ? AND COALESCE(status, 'Active') = 'Active' ORDER BY bracket_order", (tax_law_id,))


def setting(name: str, default: str = "") -> str:
    row = fetch_one("SELECT setting_value FROM salary_calculation_setup WHERE setting_name = ?", (name,))
    return row["setting_value"] if row else default


def bool_setting(name: str, default: bool = False) -> bool:
    value = setting(name, "Yes" if default else "No")
    return str(value).strip().lower() in {"yes", "true", "1", "on"}


def tax_exemption_for_year(tax_law_id: int, year: int) -> dict[str, float | bool | int]:
    row = fetch_one(
        """
        SELECT *
        FROM tax_exemptions
        WHERE tax_law_id = ? AND year <= ? AND status = 'Active'
        ORDER BY year DESC
        LIMIT 1
        """,
        (tax_law_id, year),
    )
    if row:
        return {
            "year": row["year"],
            "personal_exemption_annual": safe_float(row["personal_exemption_annual"]),
            "additional_exemption_annual": safe_float(row["additional_exemption_annual"]),
            "tax_free_bracket_annual": safe_float(row["tax_free_bracket_annual"]),
            "total_annual_exemption": safe_float(row["total_annual_exemption"]),
            "round_taxable_income_down_to_nearest_10": bool(row["round_taxable_income_down_to_nearest_10"]),
        }
    tax_law = fetch_one("SELECT * FROM tax_laws WHERE tax_law_id = ?", (tax_law_id,))
    return {
        "year": year,
        "personal_exemption_annual": safe_float(tax_law["personal_exemption"] if tax_law else 0),
        "additional_exemption_annual": safe_float(tax_law["additional_exemption"] if tax_law else 0),
        "tax_free_bracket_annual": 0,
        "total_annual_exemption": safe_float(tax_law["personal_exemption"] if tax_law else 0) + safe_float(tax_law["additional_exemption"] if tax_law else 0),
        "round_taxable_income_down_to_nearest_10": bool_setting("round_taxable_income_down_to_nearest_10", True),
    }


def active_social_insurance_setup(year: int) -> Row | None:
    return fetch_one(
        """
        SELECT *
        FROM social_insurance_setup
        WHERE COALESCE(status, 'Active') = 'Active'
          AND (
                (effective_from IS NOT NULL AND effective_from <= ?)
                OR (effective_from IS NULL AND effective_year <= ?)
              )
          AND (effective_to IS NULL OR effective_to >= ?)
        ORDER BY effective_from DESC, effective_year DESC
        LIMIT 1
        """,
        (f"{year}-12-31", year, f"{year}-01-01"),
    )


def resolve_basic_salary(
    gross: float,
    employee: Row | dict,
    override: float | None = None,
    insurance_base: float | None = None,
) -> float:
    if override is not None and override > 0:
        return override
    source = setting("basic_salary_source", "Use Employee Basic Salary")
    if source == "Use Gross Salary":
        return gross
    if source == "Gross Salary Excluding Statutory Allowances":
        allowance_percentage = safe_float(setting("statutory_allowance_percentage", "30"), 30) / 100
        allowance_base = safe_float(insurance_base, 0) or gross
        return max(gross - (allowance_base * allowance_percentage), 0)
    if source == "Calculate as % of Gross only if the user chooses it":
        percentage = safe_float(setting("gross_basic_percentage", "30"), 30) / 100
        return gross * percentage
    return safe_float(employee["basic_salary"], 0)


def resolve_insurance_details(gross: float, employee: Row | dict, basic_salary: float, year: int, override: float | None = None) -> dict[str, float | str]:
    setup = active_social_insurance_setup(year)
    source = setup["insurance_base_source"] if setup and "insurance_base_source" in setup.keys() and setup["insurance_base_source"] else setting("insurance_base_source", "Employee Insurance Salary/Base")
    source_map = {
        "Use Manual Insurance Salary/Base": "Employee Insurance Salary/Base",
        "Use Employee Basic Salary": "Employee Basic Salary",
        "Use Gross Salary": "Gross Salary",
        "Calculate as % of Gross only if the user chooses it": "Gross Salary",
    }
    source = source_map.get(source, source)
    min_base = safe_float(setup["minimum_insurance_salary"] if setup and "minimum_insurance_salary" in setup.keys() else 2600)
    max_base = safe_float(setup["maximum_insurance_salary"] if setup and "maximum_insurance_salary" in setup.keys() else 16700)
    employee_share = safe_float(setup["employee_share_percent"] if setup and "employee_share_percent" in setup.keys() else 11)
    company_share = safe_float(setup["company_share_percent"] if setup and "company_share_percent" in setup.keys() else 18.75)
    if source == "No Insurance":
        return {
            "source": source,
            "base_before_limits": 0,
            "base_after_limits": 0,
            "minimum_insurance_salary": min_base,
            "maximum_insurance_salary": max_base,
            "employee_share_percent": 0,
            "company_share_percent": 0,
            "employee_insurance": 0,
            "company_insurance": 0,
        }
    if override is not None and override > 0:
        base = override
    elif source == "Employee Insurance Salary/Base":
        base = safe_float(employee["insurance_salary_base"], 0) or basic_salary
    elif source == "Gross Salary":
        base = gross
    elif source == "Gross Salary / 1.3":
        divisor = max(safe_float(setting("insurance_gross_divisor", "1.3"), 1.3), 0.0001)
        gross_cap = max_base * divisor if max_base > 0 else 0
        if min_base > 0 and gross <= min_base:
            base = min_base
        elif gross_cap > 0 and gross >= gross_cap:
            base = max_base
        else:
            base = gross / divisor
    elif source == "Fixed Manual Amount":
        base = safe_float(employee["insurance_salary_base"], 0) or safe_float(setting("fixed_insurance_base_amount", "0"), 0)
    else:
        base = basic_salary
    base_before_limits = max(base, 0)
    if min_base > 0:
        base = max(base, min_base)
    if max_base > 0:
        base = min(base, max_base)
    base_after_limits = max(base, 0)
    return {
        "source": source,
        "base_before_limits": base_before_limits,
        "base_after_limits": base_after_limits,
        "minimum_insurance_salary": min_base,
        "maximum_insurance_salary": max_base,
        "employee_share_percent": employee_share,
        "company_share_percent": company_share,
        "gross_divisor": safe_float(setting("insurance_gross_divisor", "1.3"), 1.3),
        "employee_insurance": base_after_limits * employee_share / 100,
        "company_insurance": base_after_limits * company_share / 100,
    }


def resolve_insurance_base(gross: float, employee: Row | dict, basic_salary: float, tax_law: Row, override: float | None = None) -> float:
    year = int(tax_law["effective_year"]) if tax_law and "effective_year" in tax_law.keys() else date.today().year
    return safe_float(resolve_insurance_details(gross, employee, basic_salary, year, override)["base_after_limits"])


def calculate_egypt_income_tax(
    annual_gross_income: float,
    annual_employee_social_insurance: float,
    tax_law_id: int,
    year: int,
    personal_exemption: float | None = None,
    additional_exemption: float | None = None,
    taxable_allowances: float = 0,
    non_taxable_allowances: float = 0,
) -> dict:
    exemption = tax_exemption_for_year(tax_law_id, year)
    personal = safe_float(personal_exemption, safe_float(exemption["personal_exemption_annual"])) if personal_exemption is not None else safe_float(exemption["personal_exemption_annual"])
    additional = safe_float(additional_exemption, safe_float(exemption["additional_exemption_annual"])) if additional_exemption is not None else safe_float(exemption["additional_exemption_annual"])
    taxable_before_exemptions = max(0, annual_gross_income + taxable_allowances - non_taxable_allowances - annual_employee_social_insurance)
    final_taxable = max(0, taxable_before_exemptions - personal - additional)
    if exemption["round_taxable_income_down_to_nearest_10"]:
        final_taxable = math.floor(final_taxable / 10) * 10
    brackets = tax_brackets(tax_law_id, year, final_taxable)
    total_tax = 0.0
    breakdown = []
    tax_free_used = 0.0
    for bracket in brackets:
        min_amount = safe_float(bracket["income_from"] if "income_from" in bracket.keys() and bracket["income_from"] is not None else bracket["min_amount"])
        max_amount = bracket["income_to"] if "income_to" in bracket.keys() and bracket["income_to"] is not None else bracket["max_amount"]
        rate = safe_float(bracket["tax_rate"])
        upper = final_taxable if max_amount is None else min(safe_float(max_amount), final_taxable)
        taxable_in_bracket = max(0, upper - min_amount)
        tax_amount = taxable_in_bracket * rate
        if rate == 0:
            tax_free_used += taxable_in_bracket
        if upper > min_amount:
            total_tax += tax_amount
        breakdown.append(
            {
                "bracket_order": bracket["bracket_order"],
                "income_from": min_amount,
                "income_to": max_amount,
                "tax_rate": rate,
                "taxable_amount": taxable_in_bracket,
                "tax": tax_amount,
                "applies_for_income_level_from": bracket["applies_for_income_level_from"] if "applies_for_income_level_from" in bracket.keys() else None,
                "applies_for_income_level_to": bracket["applies_for_income_level_to"] if "applies_for_income_level_to" in bracket.keys() else None,
            }
        )
    total_tax = max(total_tax, 0)
    return {
        "annual_taxable_income_before_exemptions": taxable_before_exemptions,
        "personal_exemption_used": personal,
        "additional_exemption_used": additional,
        "tax_free_bracket_used": tax_free_used,
        "final_annual_taxable_income": final_taxable,
        "annual_tax": total_tax,
        "monthly_tax": total_tax / 12,
        "effective_tax_rate": total_tax / taxable_before_exemptions if taxable_before_exemptions else 0,
        "bracket_breakdown": breakdown,
        "tax_law_id": tax_law_id,
        "year": year,
    }


def annual_tax_from_taxable(taxable_annual: float, tax_law_id: int) -> float:
    return calculate_egypt_income_tax(taxable_annual, 0, tax_law_id, date.today().year, 0, 0)["annual_tax"]


def calculation_from_gross(
    gross: float,
    employee: Row | dict,
    year: int,
    tax_law_id: int | None = None,
    basic_override: float | None = None,
    insurance_override: float | None = None,
) -> dict[str, float]:
    tax_law = active_tax_law(year, tax_law_id)
    gross = max(float(gross), 0.0)
    basic_source = setting("basic_salary_source", "Use Employee Basic Salary")
    if basic_source == "Gross Salary Excluding Statutory Allowances":
        provisional_basic = safe_float(employee["basic_salary"], 0) or gross
        insurance = resolve_insurance_details(gross, employee, provisional_basic, year, insurance_override)
        basic = resolve_basic_salary(gross, employee, basic_override, safe_float(insurance["base_after_limits"]))
    else:
        basic = resolve_basic_salary(gross, employee, basic_override)
        insurance = resolve_insurance_details(gross, employee, basic, year, insurance_override)
    insurance_base = safe_float(insurance["base_after_limits"])
    employee_insurance = safe_float(insurance["employee_insurance"])
    company_insurance = safe_float(insurance["company_insurance"])
    statutory_allowance = max(gross - basic, 0)
    annual_gross = gross * 12
    annual_employee_insurance = employee_insurance * 12
    tax = calculate_egypt_income_tax(annual_gross, annual_employee_insurance, tax_law["tax_law_id"], year)
    taxable_annual = safe_float(tax["final_annual_taxable_income"])
    annual_tax = safe_float(tax["annual_tax"])
    monthly_tax = safe_float(tax["monthly_tax"])
    total_deductions = employee_insurance + monthly_tax
    net = gross - total_deductions
    company_cost = gross + company_insurance
    return {
        "gross": gross,
        "basic_salary": basic,
        "statutory_allowance_component": statutory_allowance,
        "insurance_base": insurance_base,
        "insurance_base_before_limits": safe_float(insurance["base_before_limits"]),
        "insurance_base_after_limits": insurance_base,
        "employee_insurance": employee_insurance,
        "company_insurance": company_insurance,
        "taxable_amount": taxable_annual / 12,
        "annual_taxable_income_before_exemptions": safe_float(tax["annual_taxable_income_before_exemptions"]),
        "final_annual_taxable_income": taxable_annual,
        "personal_exemption_used": safe_float(tax["personal_exemption_used"]),
        "additional_exemption_used": safe_float(tax["additional_exemption_used"]),
        "tax_free_bracket_used": safe_float(tax["tax_free_bracket_used"]),
        "monthly_tax": monthly_tax,
        "annual_tax": annual_tax,
        "effective_tax_rate": safe_float(tax["effective_tax_rate"]),
        "bracket_breakdown": tax["bracket_breakdown"],
        "total_deductions": total_deductions,
        "net": net,
        "total_company_cost": company_cost,
        "tax_law_id": tax_law["tax_law_id"],
    }


def gross_up_for_net(
    target_net: float,
    employee: Row | dict,
    year: int,
    tax_law_id: int | None = None,
    basic_override: float | None = None,
    insurance_override: float | None = None,
) -> dict[str, float]:
    target_net = max(float(target_net), 0)
    low = 0.0
    high = max(target_net * 2.5 + 5000, 1000)
    max_iterations = int(safe_float(setting("net_to_gross_max_iterations", "90"), 90))
    tolerance = max(safe_float(setting("net_to_gross_tolerance", "0.01"), 0.01), 0.0001)
    for _ in range(80):
        calc = calculation_from_gross(high, employee, year, tax_law_id, basic_override, insurance_override)
        if calc["net"] >= target_net:
            break
        high *= 1.6
    for _ in range(max_iterations):
        mid = (low + high) / 2
        calc = calculation_from_gross(mid, employee, year, tax_law_id, basic_override, insurance_override)
        if abs(calc["net"] - target_net) <= tolerance:
            high = mid
            break
        if calc["net"] < target_net:
            low = mid
        else:
            high = mid
    final = calculation_from_gross(high, employee, year, tax_law_id, basic_override, insurance_override)
    final["target_net"] = target_net
    final["gross_up_difference"] = final["gross"] - target_net
    return final


def is_active_for_month(row: Row | pd.Series | dict, year: int, month: int) -> bool:
    start, end = month_bounds(year, month)
    eff_from = row.get("effective_from") if isinstance(row, dict) else row["effective_from"]
    eff_to = row.get("effective_to") if isinstance(row, dict) else row["effective_to"]
    status = row.get("status") if isinstance(row, dict) else row["status"]
    if status != "Active":
        return False
    if eff_from and eff_from > end:
        return False
    if eff_to and eff_to < start:
        return False
    return True


def allowance_amount(row: Row | dict, employee: Row | dict, gross_estimate: float = 0) -> float:
    base = safe_float(row["amount"])
    calc_type = row["calculation_type"]
    if calc_type == "Percentage of Basic":
        return safe_float(employee["basic_salary"]) * base / 100
    if calc_type == "Percentage of Gross":
        gross = gross_estimate or safe_float(employee["gross_salary"]) or safe_float(employee["new_net_earning"])
        return gross * base / 100
    if calc_type == "Percentage of Net":
        return safe_float(employee["new_net_salary"]) * base / 100
    return base


def row_get(row: Row | pd.Series | dict, key: str, default=None):
    if isinstance(row, dict) or isinstance(row, pd.Series):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def is_bonus_allowance(row: Row | pd.Series | dict) -> bool:
    allowance_type = str(row_get(row, "allowance_type", "") or "").strip().lower()
    allowance_name = str(row_get(row, "allowance_name", "") or "").strip().lower()
    return allowance_type == "bonus" or "bonus" in allowance_name


def active_allowances(employee_code: str, year: int, month: int) -> list[Row]:
    start, end = month_bounds(year, month)
    rows = fetch_all(
        """
        SELECT * FROM employee_allowances
        WHERE employee_code = ?
          AND status = 'Active'
          AND (effective_from IS NULL OR effective_from <= ?)
          AND (effective_to IS NULL OR effective_to >= ?)
          AND (
                recurring IN ('Monthly', 'Temporary')
                OR (recurring = 'One Time' AND (
                    (paid_year IS NULL AND paid_month IS NULL)
                    OR (paid_year = ? AND paid_month = ?)
                    OR (effective_from BETWEEN ? AND ?)
                ))
          )
        ORDER BY allowance_id
        """,
        (employee_code, end, start, year, month, start, end),
    )
    return rows


def approved_attendance_deduction(employee_code: str, year: int, month: int) -> float:
    row = fetch_one(
        """
        SELECT SUM(deduction_amount) AS amount
        FROM attendance_adjustments
        WHERE employee_code = ? AND year = ? AND month = ? AND approval_status = 'Approved'
        """,
        (employee_code, year, month),
    )
    return safe_float(row["amount"] if row else 0)


def approved_overtime_amounts(employee_code: str, year: int, month: int) -> tuple[float, float]:
    df = read_df(
        """
        SELECT payment_type, SUM(overtime_amount) AS amount
        FROM overtime_records
        WHERE employee_code = ? AND year = ? AND month = ? AND approval_status = 'Approved'
        GROUP BY payment_type
        """,
        (employee_code, year, month),
    )
    if df.empty:
        return 0.0, 0.0
    net_amount = df.loc[df["payment_type"].str.lower() == "net", "amount"].sum()
    gross_amount = df.loc[df["payment_type"].str.lower() == "gross", "amount"].sum()
    return safe_float(net_amount), safe_float(gross_amount)


def active_allocations(employee_code: str, year: int, month: int) -> list[Row]:
    start, end = month_bounds(year, month)
    return fetch_all(
        """
        SELECT a.*, p.project_name, p.project_code
        FROM employee_project_allocations a
        JOIN projects p ON p.project_id = a.project_id
        WHERE a.employee_code = ?
          AND a.status = 'Active'
          AND (a.effective_from IS NULL OR a.effective_from <= ?)
          AND (a.effective_to IS NULL OR a.effective_to >= ?)
        ORDER BY a.is_primary_project DESC, a.allocation_type, p.project_name
        """,
        (employee_code, end, start),
    )


def default_project_split(employee: Row | dict) -> list[dict]:
    return [{"project_id": employee["default_project_id"], "project_name": project_name(employee["default_project_id"]), "ratio": 1.0, "allocation_percentage": 100.0}]


def employee_project_splits(employee: Row | dict, year: int, month: int, total_company_cost: float = 0) -> list[dict]:
    allocations = active_allocations(employee["employee_code"], year, month)
    if not allocations:
        return default_project_split(employee)

    percentage_rows = [a for a in allocations if a["allocation_type"] == "Percentage"]
    fixed_rows = [a for a in allocations if a["allocation_type"] == "Fixed Amount"]

    if fixed_rows:
        cost = max(total_company_cost, 0)
        primary = next((a for a in allocations if a["is_primary_project"]), None)
        primary_project_id = primary["project_id"] if primary else employee["default_project_id"]
        assigned = {}
        fixed_total = 0.0
        for row in fixed_rows:
            fixed_value = max(safe_float(row["fixed_allocation_amount"]), 0)
            if cost > 0:
                fixed_value = min(fixed_value, max(cost - fixed_total, 0))
            fixed_total += fixed_value
            assigned[row["project_id"]] = assigned.get(row["project_id"], 0) + fixed_value
        remaining = max(cost - fixed_total, 0)
        assigned[primary_project_id] = assigned.get(primary_project_id, 0) + remaining
        if cost <= 0:
            total_fixed = sum(assigned.values())
            if total_fixed <= 0:
                return default_project_split(employee)
            return [
                {"project_id": pid, "project_name": project_name(pid), "ratio": amount / total_fixed, "allocation_percentage": amount / total_fixed * 100}
                for pid, amount in assigned.items()
                if amount > 0
            ]
        return [
            {"project_id": pid, "project_name": project_name(pid), "ratio": amount / cost if cost else 0, "allocation_percentage": amount / cost * 100 if cost else 0}
            for pid, amount in assigned.items()
            if amount > 0
        ]

    total_pct = sum(safe_float(row["allocation_percentage"]) for row in percentage_rows)
    if total_pct <= 0:
        return default_project_split(employee)
    return [
        {
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "ratio": safe_float(row["allocation_percentage"]) / total_pct,
            "allocation_percentage": safe_float(row["allocation_percentage"]),
        }
        for row in percentage_rows
    ]


def allocation_summary(employee: Row | dict, year: int, month: int, total_company_cost: float = 0) -> str:
    splits = employee_project_splits(employee, year, month, total_company_cost)
    return " | ".join([f"{s['project_name']} {s['allocation_percentage']:.2f}%" for s in splits])


def payroll_calculation(
    employee: Row,
    year: int,
    month: int,
    tax_law_id: int | None = None,
    include_bonus_allowances: bool = True,
) -> tuple[dict, list[Row]]:
    all_allowances = active_allowances(employee["employee_code"], year, month)
    allowances = [row for row in all_allowances if include_bonus_allowances or not is_bonus_allowance(row)]
    recurring_net = recurring_gross = one_time_net = one_time_gross = 0.0
    total_allowances = 0.0
    for row in allowances:
        amount = allowance_amount(row, employee)
        total_allowances += amount
        if row["payment_type"] == "Gross Allowance":
            if row["recurring"] == "One Time":
                one_time_gross += amount
            else:
                recurring_gross += amount
        else:
            if row["recurring"] == "One Time":
                one_time_net += amount
            else:
                recurring_net += amount

    overtime_net, overtime_gross = approved_overtime_amounts(employee["employee_code"], year, month)
    attendance_deduction = approved_attendance_deduction(employee["employee_code"], year, month)
    recurring_net += overtime_net
    recurring_gross += overtime_gross
    total_allowances += overtime_net + overtime_gross

    base_net = safe_float(employee["new_net_salary"])
    target_net = max(0, base_net + recurring_net + one_time_net - attendance_deduction)
    gross_calc = gross_up_for_net(target_net, employee, year, tax_law_id)
    total_gross = gross_calc["gross"] + recurring_gross + one_time_gross
    final_calc = calculation_from_gross(total_gross, employee, year, tax_law_id)
    result = {
        "base_net_salary": base_net,
        "recurring_net_allowances": recurring_net,
        "recurring_gross_allowances": recurring_gross,
        "one_time_net_allowances": one_time_net,
        "one_time_gross_allowances": one_time_gross,
        "total_allowances": total_allowances,
        "net_earning": final_calc["net"],
        "estimated_gross": final_calc["gross"],
        "basic_salary": final_calc["basic_salary"],
        "insurance_base": final_calc["insurance_base"],
        "employee_insurance": final_calc["employee_insurance"],
        "company_insurance": final_calc["company_insurance"],
        "taxable_amount": final_calc["taxable_amount"],
        "monthly_tax": final_calc["monthly_tax"],
        "annual_tax": final_calc["annual_tax"],
        "total_deductions": final_calc["total_deductions"],
        "net_transfer_amount": final_calc["net"],
        "total_company_cost": final_calc["total_company_cost"],
        "overtime_amount": overtime_net + overtime_gross,
        "attendance_deduction": attendance_deduction,
    }
    return result, allowances


def direct_allowance_charges(allowances: list[Row], employee: Row, total_allowances: float) -> dict[int, float]:
    direct = {}
    for row in allowances:
        if row["project_charging_method"] == "Charge to Specific Project" and row["specific_project_id"]:
            amount = allowance_amount(row, employee)
            direct[row["specific_project_id"]] = direct.get(row["specific_project_id"], 0) + amount
    return direct


def create_project_allocations_for_transaction(transaction_id: int, employee: Row, payroll: dict, allowances: list[Row], year: int, month: int) -> None:
    direct = direct_allowance_charges(allowances, employee, payroll["total_allowances"])
    follow_allowances = max(payroll["total_allowances"] - sum(direct.values()), 0)
    total_cost = max(payroll["total_company_cost"], 0)
    remaining_cost = max(total_cost - sum(direct.values()), 0)
    base_splits = employee_project_splits(employee, year, month, remaining_cost)

    project_costs = {}
    allowance_alloc = {}
    for pid, amount in direct.items():
        project_costs[pid] = project_costs.get(pid, 0) + amount
        allowance_alloc[pid] = allowance_alloc.get(pid, 0) + amount
    for split in base_splits:
        pid = split["project_id"]
        project_costs[pid] = project_costs.get(pid, 0) + remaining_cost * split["ratio"]
        allowance_alloc[pid] = allowance_alloc.get(pid, 0) + follow_allowances * split["ratio"]

    rows = []
    for pid, allocated_cost in project_costs.items():
        ratio = allocated_cost / total_cost if total_cost else 0
        rows.append(
            (
                transaction_id,
                year,
                month,
                employee["employee_code"],
                employee["arabic_name"],
                employee["department"],
                employee["section"],
                pid,
                ratio * 100,
                payroll["base_net_salary"] * ratio,
                allowance_alloc.get(pid, 0),
                payroll["estimated_gross"] * ratio,
                payroll["monthly_tax"] * ratio,
                payroll["employee_insurance"] * ratio,
                payroll["company_insurance"] * ratio,
                allocated_cost,
                "Pending",
                now_text(),
            )
        )

    with db() as conn:
        conn.execute("DELETE FROM payroll_project_allocations WHERE transaction_id = ?", (transaction_id,))
        conn.executemany(
            """
            INSERT INTO payroll_project_allocations
            (transaction_id, year, month, employee_code, arabic_name, department, section, project_id,
             allocation_percentage, allocated_net_salary, allocated_allowances, allocated_gross,
             allocated_tax, allocated_employee_insurance, allocated_company_insurance,
             allocated_total_company_cost, payment_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def generate_payroll(year: int, month: int, project_id: int | None = None, department: str | None = None, recalculate: bool = False) -> dict:
    if is_month_locked(year, month):
        raise ValueError(f"Payroll {MONTHS.get(month, month)} {year} is {payroll_lock_status(year, month)}.")
    user = st.session_state.get("username", "system")
    filters = ["e.status = 'Active'"]
    params: list = []
    if project_id:
        filters.append("e.default_project_id = ?")
        params.append(project_id)
    if department and department != "All":
        filters.append("e.department = ?")
        params.append(department)
    where = " AND ".join(filters)
    employees = fetch_all(f"SELECT e.* FROM employees e WHERE {where} ORDER BY e.employee_code", tuple(params))
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO payroll_runs (year, month, project_id, department, status, generated_at, generated_by, notes)
            VALUES (?, ?, ?, ?, 'Open', ?, ?, ?)
            """,
            (year, month, project_id, None if department == "All" else department, now_text(), user, "Generated from Payroll Run Center"),
        )
        run_id = cur.lastrowid
        conn.commit()

    created = skipped = recalculated = 0
    for employee in employees:
        existing = fetch_one(
            "SELECT transaction_id FROM payroll_transactions WHERE employee_code = ? AND year = ? AND month = ?",
            (employee["employee_code"], year, month),
        )
        if existing and not recalculate:
            skipped += 1
            continue
        payroll, allowances = payroll_calculation(employee, year, month)
        summary = allocation_summary(employee, year, month, payroll["total_company_cost"])
        values = (
            run_id,
            year,
            month,
            employee["employee_code"],
            employee["arabic_name"],
            employee["organization"],
            employee["sponsor"],
            employee["position"],
            employee["department"],
            employee["section"],
            employee["default_project_id"],
            summary,
            payroll["base_net_salary"],
            payroll["recurring_net_allowances"],
            payroll["recurring_gross_allowances"],
            payroll["one_time_net_allowances"],
            payroll["one_time_gross_allowances"],
            payroll["total_allowances"],
            payroll["overtime_amount"],
            payroll["attendance_deduction"],
            payroll["net_earning"],
            payroll["estimated_gross"],
            payroll["basic_salary"],
            payroll["insurance_base"],
            payroll["employee_insurance"],
            payroll["company_insurance"],
            payroll["taxable_amount"],
            payroll["monthly_tax"],
            payroll["annual_tax"],
            payroll["total_deductions"],
            payroll["net_transfer_amount"],
            payroll["total_company_cost"],
            "Pending",
            now_text(),
            now_text(),
        )
        if existing and recalculate:
            run_sql(
                """
                UPDATE payroll_transactions
                SET run_id = ?, year = ?, month = ?, employee_code = ?, arabic_name = ?, organization = ?, sponsor = ?,
                    position = ?, department = ?, section = ?, default_project_id = ?, project_allocation_summary = ?,
                    base_net_salary = ?, recurring_net_allowances = ?, recurring_gross_allowances = ?,
                    one_time_net_allowances = ?, one_time_gross_allowances = ?, total_allowances = ?, overtime_amount = ?,
                    attendance_deduction = ?, net_earning = ?,
                    estimated_gross = ?, basic_salary = ?, insurance_base = ?, employee_insurance = ?, company_insurance = ?,
                    taxable_amount = ?, monthly_tax = ?, annual_tax = ?, total_deductions = ?, net_transfer_amount = ?,
                    total_company_cost = ?, payment_status = ?, updated_at = ?
                WHERE transaction_id = ?
                """,
                values[:-1] + (existing["transaction_id"],),
            )
            create_project_allocations_for_transaction(existing["transaction_id"], employee, payroll, allowances, year, month)
            recalculated += 1
        else:
            with db() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO payroll_transactions
                    (run_id, year, month, employee_code, arabic_name, organization, sponsor, position, department,
                     section, default_project_id, project_allocation_summary, base_net_salary, recurring_net_allowances,
                     recurring_gross_allowances, one_time_net_allowances, one_time_gross_allowances, total_allowances,
                     overtime_amount, attendance_deduction, net_earning, estimated_gross, basic_salary, insurance_base, employee_insurance, company_insurance,
                     taxable_amount, monthly_tax, annual_tax, total_deductions, net_transfer_amount, total_company_cost,
                     payment_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                transaction_id = cur.lastrowid
                conn.commit()
            create_project_allocations_for_transaction(transaction_id, employee, payroll, allowances, year, month)
            created += 1
    audit("Payroll generation", "payroll_runs", run_id, f"{year}-{month:02d}; created={created}; recalculated={recalculated}; skipped={skipped}")
    return {"run_id": run_id, "created": created, "recalculated": recalculated, "skipped": skipped, "employees": len(employees)}


def status_badge(value: str) -> str:
    classes = {
        "Transferred": "status-green",
        "Pending": "status-yellow",
        "Planned": "status-yellow",
        "Approved": "status-green",
        "Rejected": "status-red",
        "Paid": "status-green",
        "Hold": "status-red",
        "Cancelled": "status-gray",
        "Draft": "status-blue",
        "Closed": "status-dark",
        "Critical": "status-red",
        "Warning": "status-yellow",
        "Info": "status-blue",
        "Active": "status-green",
        "Inactive": "status-gray",
        "Invalid": "status-red",
    }
    cls = classes.get(value, "status-gray")
    return f"<span class='pill {cls}'>{value}</span>"


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --surface: #ffffff;
            --muted: #64748b;
            --line: #d9e2ec;
            --bg: #f6f8fb;
            --good: #15803d;
            --warn: #b7791f;
            --bad: #b91c1c;
        }
        .stApp { background: var(--bg); }
        section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b1220 0%, #111827 100%); }
        section[data-testid="stSidebar"] * { color: #e5e7eb; }
        section[data-testid="stSidebar"] .stButton button {
            width: 100%;
            justify-content: flex-start;
            border-radius: 6px;
            border: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(255, 255, 255, 0.04);
            color: #e5e7eb !important;
            min-height: 2.25rem;
            font-weight: 650;
        }
        section[data-testid="stSidebar"] .stButton button[kind="primary"] {
            background: #2563eb !important;
            border-color: #60a5fa !important;
            color: white !important;
        }
        section[data-testid="stSidebar"] details {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 8px;
            padding: 0.15rem 0.45rem 0.45rem 0.45rem;
            margin-bottom: 0.45rem;
            background: rgba(255, 255, 255, 0.025);
        }
        .block-container { padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1500px; }
        h1, h2, h3 { color: #102a43; letter-spacing: 0; }
        .hero-title { font-size: 1.9rem; font-weight: 780; color: #102a43; margin-bottom: 0.15rem; }
        .hero-subtitle { color: #52606d; font-size: 0.98rem; margin-bottom: 1rem; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: 0.75rem; margin: 0.5rem 0 1.2rem 0; }
        .kpi-card { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 0.95rem 1rem; box-shadow: 0 1px 2px rgba(16, 42, 67, 0.05); }
        .kpi-label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; font-weight: 720; letter-spacing: 0.03em; }
        .kpi-value { font-size: 1.33rem; font-weight: 780; color: #102a43; margin-top: 0.35rem; line-height: 1.25; }
        .section-card { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
        .pill { display: inline-flex; align-items: center; border-radius: 999px; padding: 0.18rem 0.55rem; font-size: 0.78rem; font-weight: 700; }
        .status-green { color: #166534; background: #dcfce7; border: 1px solid #86efac; }
        .status-yellow { color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; }
        .status-red { color: #991b1b; background: #fee2e2; border: 1px solid #fca5a5; }
        .status-gray { color: #374151; background: #f3f4f6; border: 1px solid #d1d5db; }
        .status-blue { color: #1d4ed8; background: #dbeafe; border: 1px solid #93c5fd; }
        .status-dark { color: #f9fafb; background: #374151; border: 1px solid #111827; }
        .arabic-name { direction: rtl; unicode-bidi: isolate; font-family: "Segoe UI", Tahoma, Arial, sans-serif; font-weight: 650; }
        div[data-testid="stMetric"] { background: white; border: 1px solid var(--line); border-radius: 8px; padding: 0.8rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 0.3rem; }
        .stTabs [data-baseweb="tab"] { background: white; border: 1px solid var(--line); border-radius: 7px 7px 0 0; padding: 0.45rem 0.7rem; }
        button[kind="primary"] { background: var(--primary) !important; border-color: var(--primary) !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='hero-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='hero-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def kpi_cards(cards: list[tuple[str, str]]) -> None:
    html = ["<div class='kpi-grid'>"]
    for label, value in cards:
        html.append(f"<div class='kpi-card'><div class='kpi-label'>{label}</div><div class='kpi-value'>{value}</div></div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def rank(access_level: str | None) -> int:
    return ACCESS_RANK.get(access_level or "No Access", 0)


def current_user_row() -> Row | None:
    username = st.session_state.get("username")
    if not username:
        return None
    return fetch_one(
        """
        SELECT u.*, COALESCE(r.role_name, u.role) AS role_name
        FROM users u
        LEFT JOIN roles r ON r.id = u.role_id
        WHERE u.username = ?
        """,
        (username,),
    )


def permission_access(permission_code: str) -> str:
    user = current_user_row()
    if not user:
        return "No Access"
    role_name = user["role_name"] or user["role"] or "Viewer"
    if role_name == "Super Admin":
        return "Full Access"
    role_row = fetch_one("SELECT id FROM roles WHERE role_name = ?", (role_name,))
    access = "No Access"
    if role_row:
        row = fetch_one(
            "SELECT access_level FROM role_permissions WHERE role_id = ? AND permission_code = ?",
            (role_row["id"], permission_code),
        )
        if row:
            access = row["access_level"]
    override = fetch_one(
        """
        SELECT access_level, override_type
        FROM user_permissions
        WHERE user_id = ? AND permission_code = ?
        """,
        (user["id"], permission_code),
    )
    if override:
        if override["override_type"] == "Deny":
            return "No Access"
        access = override["access_level"]
    return access


def page_permission_code(page_name: str | None = None) -> str:
    return f"PAGE:{page_name or st.session_state.get('current_page', 'Executive Dashboard')}"


def has_page_access(page_name: str, minimum: str = "View Only") -> bool:
    return rank(permission_access(page_permission_code(page_name))) >= rank(minimum)


def has_action(permission_code: str, minimum: str = "View Only") -> bool:
    return rank(permission_access(permission_code)) >= rank(minimum)


def can_write(page_name: str | None = None) -> bool:
    return rank(permission_access(page_permission_code(page_name))) >= rank("Add")


def is_admin() -> bool:
    return st.session_state.get("role") in {"Super Admin", "Admin"}


def require_write(page_name: str | None = None, action_code: str | None = None) -> bool:
    allowed = has_action(action_code) if action_code else can_write(page_name)
    if not allowed:
        st.warning("Your current permissions allow viewing this area, but not changing it.")
        return False
    return True


def user_id_by_username(username: str) -> int | None:
    row = fetch_one("SELECT id FROM users WHERE username = ?", (username,))
    return row["id"] if row else None


def allowed_projects() -> set[str] | None:
    user = current_user_row()
    if not user or (user["role_name"] or user["role"]) in {"Super Admin", "Admin"}:
        return None
    rows = fetch_all("SELECT project, access_type FROM user_project_access WHERE user_id = ?", (user["id"],))
    if not rows or any(row["access_type"] == "All" for row in rows):
        return None
    return {row["project"] for row in rows if row["project"] and row["project"] != "All Projects"}


def allowed_departments() -> set[str] | None:
    user = current_user_row()
    if not user or (user["role_name"] or user["role"]) in {"Super Admin", "Admin"}:
        return None
    rows = fetch_all("SELECT department, access_type FROM user_department_access WHERE user_id = ?", (user["id"],))
    if not rows or any(row["access_type"] == "All" for row in rows):
        return None
    return {row["department"] for row in rows if row["department"] and row["department"] != "All Departments"}


def restrict_df_by_access(df: pd.DataFrame, project_col: str | None = None, department_col: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    view = df.copy()
    projects = allowed_projects()
    departments = allowed_departments()
    if projects is not None and project_col and project_col in view.columns:
        view = view[view[project_col].isin(projects)]
    if departments is not None and department_col and department_col in view.columns:
        view = view[view[department_col].isin(departments)]
    return view


def column_is_sensitive(column_name: str) -> list[str]:
    lower = column_name.lower().replace("_", " ")
    matched = []
    for permission_code, tokens in SENSITIVE_SALARY_COLUMNS.items():
        if any(token.replace("_", " ") in lower for token in tokens):
            matched.append(permission_code)
    return matched


def mask_salary_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    view = df.copy()
    if "Item" in view.columns and "Value" in view.columns:
        for idx, row in view.iterrows():
            permissions = column_is_sensitive(str(row["Item"]))
            if permissions and not all(has_action(permission) for permission in permissions):
                view.at[idx, "Value"] = "Restricted"
    for column in view.columns:
        permissions = column_is_sensitive(str(column))
        if permissions and not all(has_action(permission) for permission in permissions):
            view[column] = "Restricted"
    return view


def has_salary_columns(df: pd.DataFrame) -> bool:
    if "Item" in df.columns and df["Item"].astype(str).map(lambda value: bool(column_is_sensitive(value))).any():
        return True
    return any(column_is_sensitive(str(column)) for column in df.columns)


def protected_download_button(label: str, df: pd.DataFrame, filename: str, file_type: str = "excel") -> None:
    if has_salary_columns(df) and not has_action("Can Export Salary Data"):
        st.warning("Export disabled because this report contains salary or company cost data.")
        return
    if not has_action("Can Export Data") and not has_action("Can Export Salary Data"):
        st.warning("Export disabled for your user.")
        return
    if file_type == "csv":
        st.download_button(label, csv_bytes(df), filename)
    else:
        st.download_button(label, excel_bytes({filename.replace(".xlsx", "")[:31]: df}), filename)
    audit("Export action", "reports", filename, f"Exported {filename}")


def payroll_lock_status(year: int, month: int) -> str:
    row = fetch_one("SELECT lock_status FROM payroll_locks WHERE year = ? AND month = ?", (year, month))
    return row["lock_status"] if row else "Open"


def is_month_locked(year: int, month: int) -> bool:
    return payroll_lock_status(year, month) in {"Locked", "Closed"}


def require_month_open(year: int, month: int) -> bool:
    status = payroll_lock_status(year, month)
    if status in {"Locked", "Closed"}:
        st.error(f"Payroll {MONTHS.get(month, month)} {year} is {status}. Reopen it before changing payroll-impacting data.")
        return False
    return True


def create_approval_request(request_type: str, record_id: int | str, notes: str = "") -> int:
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO approval_requests (request_type, record_id, requested_by, requested_at, status, notes)
            VALUES (?, ?, ?, ?, 'Pending', ?)
            """,
            (request_type, str(record_id), st.session_state.get("username", "system"), now_text(), notes),
        )
        request_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO approval_history (approval_request_id, request_type, record_id, action, action_by, action_at, comments, new_status)
            VALUES (?, ?, ?, 'Submitted', ?, ?, ?, 'Pending')
            """,
            (request_id, request_type, str(record_id), st.session_state.get("username", "system"), now_text(), notes),
        )
        conn.commit()
        return request_id


def approve_record(request_type: str, record_id: int | str, comments: str = "") -> None:
    with db() as conn:
        request = conn.execute(
            """
            SELECT * FROM approval_requests
            WHERE request_type = ? AND record_id = ? AND status = 'Pending'
            ORDER BY id DESC LIMIT 1
            """,
            (request_type, str(record_id)),
        ).fetchone()
        if request:
            conn.execute(
                """
                UPDATE approval_requests
                SET status = 'Approved', approved_by = ?, approved_at = ?, notes = COALESCE(notes, '') || ?
                WHERE id = ?
                """,
                (st.session_state.get("username", "system"), now_text(), f"\n{comments}" if comments else "", request["id"]),
            )
            request_id = request["id"]
        else:
            request_id = None
        conn.execute(
            """
            INSERT INTO approval_history (approval_request_id, request_type, record_id, action, action_by, action_at, comments, old_status, new_status)
            VALUES (?, ?, ?, 'Approved', ?, ?, ?, 'Pending', 'Approved')
            """,
            (request_id, request_type, str(record_id), st.session_state.get("username", "system"), now_text(), comments),
        )
        conn.commit()


def reject_record(request_type: str, record_id: int | str, comments: str = "") -> None:
    with db() as conn:
        request = conn.execute(
            """
            SELECT * FROM approval_requests
            WHERE request_type = ? AND record_id = ? AND status = 'Pending'
            ORDER BY id DESC LIMIT 1
            """,
            (request_type, str(record_id)),
        ).fetchone()
        if request:
            conn.execute(
                """
                UPDATE approval_requests
                SET status = 'Rejected', approved_by = ?, approved_at = ?, rejection_reason = ?
                WHERE id = ?
                """,
                (st.session_state.get("username", "system"), now_text(), comments, request["id"]),
            )
            request_id = request["id"]
        else:
            request_id = None
        conn.execute(
            """
            INSERT INTO approval_history (approval_request_id, request_type, record_id, action, action_by, action_at, comments, old_status, new_status)
            VALUES (?, ?, ?, 'Rejected', ?, ?, ?, 'Pending', 'Rejected')
            """,
            (request_id, request_type, str(record_id), st.session_state.get("username", "system"), now_text(), comments),
        )
        conn.commit()


def login_page() -> None:
    col1, col2, col3 = st.columns([1.2, 1, 1.2])
    with col2:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.title(APP_NAME)
        st.caption("Professional payroll management system")
        with st.form("login"):
            username = st.text_input("Username", value="superadmin")
            password = st.text_input("Password", type="password", value="superadmin123")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
        if submitted:
            user = fetch_one(
                """
                SELECT u.*, COALESCE(r.role_name, u.role) AS role_name
                FROM users u
                LEFT JOIN roles r ON r.id = u.role_id
                WHERE u.username = ?
                """,
                (username.strip(),),
            )
            if not user:
                audit("Login failed", "users", username.strip(), "Unknown user")
                st.error("Invalid username or password.")
            elif user["status"] == "Locked":
                audit("Login failed", "users", username.strip(), "Locked user")
                st.error("This user is locked. Ask an admin to reset access.")
            elif user["status"] != "Active":
                audit("Login failed", "users", username.strip(), f"Inactive status={user['status']}")
                st.error("This user is not active.")
            elif user["password_hash"] == hash_password(password):
                st.session_state["authenticated"] = True
                st.session_state["user_id"] = user["id"]
                st.session_state["username"] = user["username"]
                st.session_state["role"] = user["role_name"]
                run_sql(
                    """
                    UPDATE users
                    SET failed_login_attempts = 0, last_login = ?
                    WHERE id = ?
                    """,
                    (now_text(), user["id"]),
                )
                run_sql(
                    """
                    INSERT INTO user_sessions (user_id, username, login_time, session_status, details)
                    VALUES (?, ?, ?, 'Active', 'Login success')
                    """,
                    (user["id"], user["username"], now_text()),
                )
                audit("Login success", "users", user["username"], f"Role={user['role_name']}")
                st.rerun()
            else:
                failed = safe_float(user["failed_login_attempts"], 0) + 1
                status = "Locked" if failed >= 5 else user["status"]
                run_sql("UPDATE users SET failed_login_attempts = ?, status = ? WHERE id = ?", (failed, status, user["id"]))
                audit("Login failed", "users", username.strip(), f"Failed attempts={failed}")
                st.error("Invalid username or password.")
        st.info("Default users: superadmin/superadmin123, admin/admin123, payroll/payroll123, hr/hr123, finance/finance123, viewer/viewer123")
        st.markdown("</div>", unsafe_allow_html=True)


def dashboard_page() -> None:
    page_header("Executive Dashboard", "Company-wide payroll, project cost, allowance, tax, insurance, bonus, and transfer view.")
    years = list(range(2023, date.today().year + 2))
    filter_cols = st.columns(6)
    year = filter_cols[0].selectbox("Year", years, index=years.index(date.today().year), key="dash_year")
    month = filter_cols[1].selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1, key="dash_month")

    emp = read_df(
        """
        SELECT e.*, p.project_name
        FROM employees e
        LEFT JOIN projects p ON p.project_id = e.default_project_id
        """
    )
    emp = restrict_df_by_access(emp, "project_name", "department")

    organization = filter_cols[2].selectbox("Organization", ["All"] + sorted(emp["organization"].dropna().unique().tolist()), key="dash_org")
    project = filter_cols[3].selectbox("Project", ["All"] + sorted(emp["project_name"].dropna().unique().tolist()), key="dash_project")
    department = filter_cols[4].selectbox("Department", ["All"] + sorted(emp["department"].dropna().unique().tolist()), key="dash_department")
    sponsor = filter_cols[5].selectbox("Sponsor", ["All"] + sorted(emp["sponsor"].dropna().unique().tolist()), key="dash_sponsor")

    def apply_dash_filters(
        frame: pd.DataFrame,
        project_col: str | None = None,
        department_col: str | None = "department",
        organization_col: str | None = "organization",
        sponsor_col: str | None = "sponsor",
    ) -> pd.DataFrame:
        view = frame.copy()
        if view.empty:
            return view
        if organization != "All" and organization_col and organization_col in view.columns:
            view = view[view[organization_col] == organization]
        if project != "All" and project_col and project_col in view.columns:
            view = view[view[project_col] == project]
        if department != "All" and department_col and department_col in view.columns:
            view = view[view[department_col] == department]
        if sponsor != "All" and sponsor_col and sponsor_col in view.columns:
            view = view[view[sponsor_col] == sponsor]
        return view

    emp = apply_dash_filters(emp, "project_name")

    def payroll_tx_for(period_year: int, period_month: int) -> pd.DataFrame:
        frame = read_df(
            """
            SELECT t.*, p.project_name
            FROM payroll_transactions t
            LEFT JOIN projects p ON p.project_id = t.default_project_id
            WHERE t.year = ? AND t.month = ?
            """,
            (period_year, period_month),
        )
        return apply_dash_filters(restrict_df_by_access(frame, "project_name", "department"), "project_name")

    def payroll_alloc_for(period_year: int, period_month: int) -> pd.DataFrame:
        frame = read_df(
            """
            SELECT a.*, p.project_name, t.organization, t.sponsor, t.payment_status
            FROM payroll_project_allocations a
            JOIN payroll_transactions t ON t.transaction_id = a.transaction_id
            JOIN projects p ON p.project_id = a.project_id
            WHERE a.year = ? AND a.month = ?
            """,
            (period_year, period_month),
        )
        return apply_dash_filters(restrict_df_by_access(frame, "project_name", "department"), "project_name")

    tx = read_df(
        """
        SELECT t.*, p.project_name
        FROM payroll_transactions t
        LEFT JOIN projects p ON p.project_id = t.default_project_id
        WHERE t.year = ? AND t.month = ?
        """,
        (year, month),
    )
    alloc = read_df(
        """
        SELECT a.*, p.project_name, t.organization, t.sponsor, t.payment_status
        FROM payroll_project_allocations a
        JOIN payroll_transactions t ON t.transaction_id = a.transaction_id
        JOIN projects p ON p.project_id = a.project_id
        WHERE a.year = ? AND a.month = ?
        """,
        (year, month),
    )
    active_allow = read_df(
        """
        SELECT a.*, e.department, e.organization, e.sponsor,
               COALESCE(p.project_name, dp.project_name) AS project_name
        FROM employee_allowances a
        JOIN employees e ON e.employee_code = a.employee_code
        LEFT JOIN projects p ON p.project_id = a.specific_project_id
        LEFT JOIN projects dp ON dp.project_id = e.default_project_id
        WHERE a.status = 'Active'
        """
    )
    bonus_alloc = read_df(
        """
        SELECT bpa.*, e.department, e.section, e.organization, e.sponsor
        FROM bonus_project_allocations bpa
        JOIN employee_bonuses b ON b.id = bpa.bonus_id
        JOIN employees e ON e.employee_code = b.employee_code
        WHERE bpa.year = ? AND bpa.month = ?
        """,
        (year, month),
    )
    tx = apply_dash_filters(restrict_df_by_access(tx, "project_name", "department"), "project_name")
    alloc = apply_dash_filters(restrict_df_by_access(alloc, "project_name", "department"), "project_name")
    active_allow = apply_dash_filters(restrict_df_by_access(active_allow, "project_name", "department"), "project_name")
    bonus_alloc = apply_dash_filters(restrict_df_by_access(bonus_alloc, "project", "department"), "project")
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_tx = payroll_tx_for(prev_year, prev_month)
    prev_alloc = payroll_alloc_for(prev_year, prev_month)

    allocated_view = project != "All" and not alloc.empty
    current_cost = alloc["allocated_total_company_cost"].sum() if allocated_view else (tx["total_company_cost"].sum() if not tx.empty else 0)
    previous_cost = prev_alloc["allocated_total_company_cost"].sum() if project != "All" and not prev_alloc.empty else (prev_tx["total_company_cost"].sum() if not prev_tx.empty else 0)
    payroll_variance = current_cost - previous_cost
    total_net_payroll = (alloc["allocated_net_salary"].sum() + alloc["allocated_allowances"].sum()) if allocated_view else (tx["net_transfer_amount"].sum() if not tx.empty else 0)
    estimated_gross = alloc["allocated_gross"].sum() if allocated_view else (tx["estimated_gross"].sum() if not tx.empty else 0)
    total_tax = alloc["allocated_tax"].sum() if allocated_view else (tx["monthly_tax"].sum() if not tx.empty else 0)
    employee_insurance = alloc["allocated_employee_insurance"].sum() if allocated_view else (tx["employee_insurance"].sum() if not tx.empty else 0)
    company_insurance = alloc["allocated_company_insurance"].sum() if allocated_view else (tx["company_insurance"].sum() if not tx.empty else 0)

    cards = [
        ("Active Employees", f"{(emp['status'] == 'Active').sum():,}" if not emp.empty else "0"),
        ("Total Net Payroll", secure_money(total_net_payroll, "Can View Net Salary")),
        ("Estimated Gross Payroll", secure_money(estimated_gross, "Can View Gross Salary")),
        ("Total Tax", secure_money(total_tax, "Can View Tax")),
        ("Employee Insurance", secure_money(employee_insurance, "Can View Social Insurance")),
        ("Company Insurance", secure_money(company_insurance, "Can View Social Insurance")),
        ("Total Company Cost", secure_money(current_cost, "Can View Company Cost")),
        ("Total Bonus Cost", secure_money(bonus_alloc["allocated_company_cost_difference"].sum() if not bonus_alloc.empty else 0, "Can View Bonus Amount")),
        ("Pending Transfers", f"{tx['payment_status'].isin(['Pending', 'Hold']).sum() if not tx.empty else 0:,}"),
        ("Payroll Variance", secure_money(payroll_variance, "Can View Company Cost")),
    ]
    kpi_cards(cards)

    if tx.empty:
        st.info("No payroll transactions for the selected month yet. Generate payroll from Payroll Run Center to populate payroll KPIs and charts.")
    st.markdown("### Payroll Overview")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Payroll Cost by Project")
        if not has_action("Can View Company Cost"):
            st.info("Company cost chart restricted.")
        elif not alloc.empty:
            st.bar_chart(alloc.groupby("project_name", as_index=False)["allocated_total_company_cost"].sum(), x="project_name", y="allocated_total_company_cost")
        else:
            st.dataframe(mask_salary_columns(emp.groupby("project_name", as_index=False)["new_net_earning"].sum()), use_container_width=True)
    with col2:
        st.subheader("Payroll Cost by Department")
        if not has_action("Can View Company Cost"):
            st.info("Company cost chart restricted.")
        elif not alloc.empty:
            st.bar_chart(alloc.groupby("department", as_index=False)["allocated_total_company_cost"].sum(), x="department", y="allocated_total_company_cost")
        elif not tx.empty:
            st.bar_chart(tx.groupby("department", as_index=False)["total_company_cost"].sum(), x="department", y="total_company_cost")

    st.markdown("### Cost Breakdown")
    trend = read_df(
        """
        SELECT a.year, a.month, p.project_name, t.department, t.organization, t.sponsor,
               SUM(a.allocated_total_company_cost) AS project_cost
        FROM payroll_project_allocations a
        JOIN payroll_transactions t ON t.transaction_id = a.transaction_id
        JOIN projects p ON p.project_id = a.project_id
        WHERE t.year = ?
        GROUP BY a.year, a.month, p.project_name, t.department, t.organization, t.sponsor
        ORDER BY a.month
        """,
        (year,),
    )
    trend = apply_dash_filters(restrict_df_by_access(trend, "project_name", "department"), "project_name")
    tax_trend = read_df(
        """
        SELECT year, month, organization, sponsor, department,
               SUM(monthly_tax) AS monthly_tax,
               SUM(employee_insurance) AS employee_insurance,
               SUM(company_insurance) AS company_insurance
        FROM payroll_transactions
        WHERE year = ?
        GROUP BY year, month, organization, sponsor, department
        ORDER BY month
        """,
        (year,),
    )
    tax_trend = apply_dash_filters(restrict_df_by_access(tax_trend, None, "department"), None)
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Monthly Payroll Trend")
        if has_action("Can View Company Cost") and not trend.empty:
            trend["period"] = trend["month"].map(MONTHS)
            st.line_chart(trend, x="period", y="project_cost", color="project_name")
        elif trend.empty:
            st.info("Generate payroll for months to see trends.")
        else:
            st.info("Company cost trend restricted.")
    with col4:
        st.subheader("Tax and Insurance Trend")
        if has_action("Can View Tax") and has_action("Can View Social Insurance") and not tax_trend.empty:
            tax_trend = tax_trend.groupby("month", as_index=False)[["monthly_tax", "employee_insurance", "company_insurance"]].sum()
            tax_trend["period"] = tax_trend["month"].map(MONTHS)
            st.line_chart(tax_trend, x="period", y=["monthly_tax", "employee_insurance", "company_insurance"])
        else:
            st.info("Tax and insurance trend restricted or unavailable.")

    st.markdown("### Project Cost Analysis")
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("Employees by Project")
        if not emp.empty:
            st.bar_chart(emp.groupby("project_name", as_index=False)["employee_code"].count(), x="project_name", y="employee_code")
    with col6:
        st.subheader("Employees by Sponsor")
        if not emp.empty:
            st.bar_chart(emp.groupby("sponsor", as_index=False)["employee_code"].count(), x="sponsor", y="employee_code")

    st.markdown("### Bonus Analysis")
    bonus_trend = read_df(
        """
        SELECT bpa.year, bpa.month, bpa.project, e.department, e.organization, e.sponsor,
               SUM(bpa.allocated_company_cost_difference) AS bonus_cost
        FROM bonus_project_allocations bpa
        JOIN employee_bonuses b ON b.id = bpa.bonus_id
        JOIN employees e ON e.employee_code = b.employee_code
        WHERE bpa.year = ?
        GROUP BY bpa.year, bpa.month, bpa.project, e.department, e.organization, e.sponsor
        ORDER BY bpa.month
        """,
        (year,),
    )
    bonus_trend = apply_dash_filters(restrict_df_by_access(bonus_trend, "project", "department"), "project")
    col7, col8 = st.columns(2)
    with col7:
        st.subheader("Bonus Cost by Project")
        if has_action("Can View Bonus Amount") and not bonus_alloc.empty:
            st.bar_chart(bonus_alloc.groupby("project", as_index=False)["allocated_company_cost_difference"].sum(), x="project", y="allocated_company_cost_difference")
        else:
            st.info("No bonus cost available or access is restricted.")
    with col8:
        st.subheader("Monthly Bonus Trend")
        if has_action("Can View Bonus Amount") and not bonus_trend.empty:
            bonus_by_month = bonus_trend.groupby("month", as_index=False)["bonus_cost"].sum()
            bonus_by_month["period"] = bonus_by_month["month"].map(MONTHS)
            st.line_chart(bonus_by_month, x="period", y="bonus_cost")
        else:
            st.info("No saved bonus register costs for this year.")

    st.markdown("### Exceptions & Alerts")
    col9, col10 = st.columns(2)
    with col9:
        st.subheader("Top 10 Employees by Company Cost")
        if has_action("Can View Company Cost") and not tx.empty:
            top_cost = tx.sort_values("total_company_cost", ascending=False).head(10)[["employee_code", "arabic_name", "department", "project_name", "total_company_cost"]]
            st.dataframe(mask_salary_columns(top_cost), use_container_width=True, hide_index=True)
        else:
            st.info("Company cost detail restricted or unavailable.")
    with col10:
        st.subheader("Open Alerts")
        alerts = read_df("SELECT severity, alert_type, message, status FROM alerts WHERE status != 'Resolved' ORDER BY created_at DESC LIMIT 10")
        if alerts.empty:
            st.success("No open alerts.")
        else:
            st.dataframe(alerts, use_container_width=True, hide_index=True)


def filtered_employee_df() -> pd.DataFrame:
    return read_df(
        """
        SELECT e.employee_code, e.organization, e.sponsor, e.arabic_name, e.position, e.department,
               e.section, p.project_name AS default_project, e.hiring_date, e.new_net_earning,
               e.new_net_salary, e.new_allowance, e.basic_salary, e.net_salary, e.gross_salary,
               e.insurance_salary_base, e.status, e.notes
        FROM employees e
        LEFT JOIN projects p ON p.project_id = e.default_project_id
        ORDER BY e.employee_code
        """
    )


def employees_page() -> None:
    page_header("Employees", "Master data, employee profile, allowances, allocations, payroll and bonus history.")
    employees = filtered_employee_df()
    projects = project_lookup(active_only=True)
    organizations = ["All"] + sorted(employees["organization"].dropna().unique().tolist())
    sponsors = ["All"] + sorted(employees["sponsor"].dropna().unique().tolist())
    departments = ["All"] + sorted(employees["department"].dropna().unique().tolist())
    sections = ["All"] + sorted(employees["section"].dropna().unique().tolist())
    project_names = ["All"] + sorted(employees["default_project"].dropna().unique().tolist())

    f1, f2, f3, f4, f5, f6 = st.columns([1.3, 1, 1, 1, 1, 1])
    search = f1.text_input("Search code/name")
    org = f2.selectbox("Organization", organizations)
    sponsor = f3.selectbox("Sponsor", sponsors)
    dept = f4.selectbox("Department", departments)
    section = f5.selectbox("Section", sections)
    project = f6.selectbox("Project", project_names)

    df = employees.copy()
    if search:
        mask = df["employee_code"].astype(str).str.contains(search, case=False, na=False) | df["arabic_name"].astype(str).str.contains(search, case=False, na=False)
        df = df[mask]
    for col, value in [("organization", org), ("sponsor", sponsor), ("department", dept), ("section", section), ("default_project", project)]:
        if value != "All":
            df = df[df[col] == value]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export Employees to Excel", excel_bytes({"Employees": df}), "employees.xlsx", use_container_width=False)

    tab_add, tab_edit, tab_profile = st.tabs(["Add Employee", "Edit / Disable", "Employee Profile"])
    with tab_add:
        if require_write():
            with st.form("add_employee_form"):
                c1, c2, c3 = st.columns(3)
                code = c1.text_input("Employee Code")
                name = c2.text_input("Arabic Name")
                position = c3.text_input("Position")
                c4, c5, c6 = st.columns(3)
                organization = c4.text_input("Organization", "AFM")
                sponsor_value = c5.text_input("Sponsor")
                department = c6.text_input("Department")
                c7, c8, c9 = st.columns(3)
                section_value = c7.text_input("Section")
                project_value = c8.selectbox("Default Project", list(projects.keys()) or [""])
                hiring = c9.date_input("Hiring Date", value=date.today())
                c10, c11, c12 = st.columns(3)
                basic = c10.number_input("Basic Salary", min_value=0.0, step=100.0)
                new_net = c11.number_input("New Net Salary", min_value=0.0, step=100.0)
                new_allowance = c12.number_input("New Allowance", min_value=0.0, step=100.0)
                c13, c14 = st.columns(2)
                insurance_base = c13.number_input("Insurance Salary/Base", min_value=0.0, step=100.0)
                notes = c14.text_area("Notes")
                submitted = st.form_submit_button("Add Employee", type="primary")
            if submitted:
                if not code or not name or not project_value:
                    st.error("Employee Code, Arabic Name and Default Project are required.")
                elif fetch_one("SELECT employee_code FROM employees WHERE employee_code = ?", (code,)):
                    st.error("Employee Code already exists.")
                else:
                    new_net_earning = new_net + new_allowance
                    run_sql(
                        """
                        INSERT INTO employees
                        (employee_code, organization, sponsor, arabic_name, position, department, section, default_project_id,
                         hiring_date, basic_salary, net_salary, gross_salary, new_net_salary, new_allowance, new_net_earning,
                         insurance_salary_base, status, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'Active', ?, ?)
                        """,
                        (
                            code.strip(),
                            organization,
                            sponsor_value,
                            name,
                            position,
                            department,
                            section_value,
                            projects[project_value],
                            hiring.isoformat(),
                            basic,
                            new_net,
                            new_net,
                            new_allowance,
                            new_net_earning,
                            insurance_base or basic,
                            notes,
                            now_text(),
                        ),
                    )
                    run_sql(
                        """
                        INSERT INTO employee_project_allocations
                        (employee_code, project_id, allocation_type, allocation_percentage, fixed_allocation_amount,
                         effective_from, is_primary_project, status, notes, created_at)
                        VALUES (?, ?, 'Percentage', 100, 0, ?, 1, 'Active', 'Default allocation created with employee', ?)
                        """,
                        (code.strip(), projects[project_value], hiring.isoformat(), now_text()),
                    )
                    if new_allowance > 0:
                        run_sql(
                            """
                            INSERT INTO employee_allowances
                            (employee_code, allowance_type, allowance_name, amount, calculation_type, payment_type,
                             taxable, social_insurance_applicable, recurring, project_charging_method, effective_from,
                             department, status, notes, created_at)
                            VALUES (?, 'Project Allowance', 'Current Allowance', ?, 'Fixed Amount', 'Net Allowance',
                                    1, 0, 'Monthly', 'Follow Employee Project Allocation', ?, ?, 'Active', ?, ?)
                            """,
                            (code.strip(), new_allowance, hiring.isoformat(), department, "Created from employee New Allowance", now_text()),
                        )
                    audit("Employee creation", "employees", code, name)
                    st.success("Employee added.")
                    st.rerun()
    with tab_edit:
        if require_write():
            all_codes = employees["employee_code"].tolist()
            selected = st.selectbox("Select Employee", all_codes, key="edit_employee_select")
            row = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (selected,))
            if row:
                project_options = list(projects.keys())
                current_project = project_name(row["default_project_id"])
                with st.form("edit_employee_form"):
                    c1, c2, c3 = st.columns(3)
                    name = c1.text_input("Arabic Name", row["arabic_name"])
                    organization = c2.text_input("Organization", row["organization"] or "")
                    sponsor_value = c3.text_input("Sponsor", row["sponsor"] or "")
                    c4, c5, c6 = st.columns(3)
                    position = c4.text_input("Position", row["position"] or "")
                    department = c5.text_input("Department", row["department"] or "")
                    section_value = c6.text_input("Section", row["section"] or "")
                    c7, c8, c9 = st.columns(3)
                    default_project = c7.selectbox("Default Project", project_options, index=project_options.index(current_project) if current_project in project_options else 0)
                    hiring = c8.date_input("Hiring Date", value=pd.to_datetime(row["hiring_date"]).date() if row["hiring_date"] else date.today())
                    status = c9.selectbox("Status", ["Active", "Inactive"], index=0 if row["status"] == "Active" else 1)
                    c10, c11, c12 = st.columns(3)
                    basic = c10.number_input("Basic Salary", value=float(row["basic_salary"]), min_value=0.0, step=100.0)
                    net_salary = c11.number_input("New Net Salary", value=float(row["new_net_salary"]), min_value=0.0, step=100.0)
                    allowance = c12.number_input("New Allowance", value=float(row["new_allowance"]), min_value=0.0, step=100.0)
                    c13, c14 = st.columns(2)
                    insurance = c13.number_input("Insurance Salary/Base", value=float(row["insurance_salary_base"]), min_value=0.0, step=100.0)
                    notes = c14.text_area("Notes", row["notes"] or "")
                    save = st.form_submit_button("Save Changes", type="primary")
                if save:
                    run_sql(
                        """
                        UPDATE employees
                        SET organization = ?, sponsor = ?, arabic_name = ?, position = ?, department = ?, section = ?,
                            default_project_id = ?, hiring_date = ?, basic_salary = ?, net_salary = ?, new_net_salary = ?,
                            new_allowance = ?, new_net_earning = ?, insurance_salary_base = ?, status = ?, notes = ?, updated_at = ?
                        WHERE employee_code = ?
                        """,
                        (
                            organization,
                            sponsor_value,
                            name,
                            position,
                            department,
                            section_value,
                            projects[default_project],
                            hiring.isoformat(),
                            basic,
                            net_salary,
                            net_salary,
                            allowance,
                            net_salary + allowance,
                            insurance,
                            status,
                            notes,
                            now_text(),
                            selected,
                        ),
                    )
                    audit("Employee update", "employees", selected, name)
                    st.success("Employee updated.")
                    st.rerun()
    with tab_profile:
        all_codes = employees["employee_code"].tolist()
        selected = st.selectbox("Employee Profile", all_codes, key="profile_employee_select")
        profile = fetch_one(
            """
            SELECT e.*, p.project_name
            FROM employees e LEFT JOIN projects p ON p.project_id = e.default_project_id
            WHERE e.employee_code = ?
            """,
            (selected,),
        )
        if profile:
            kpi_cards(
                [
                    ("Employee Code", profile["employee_code"]),
                    ("Arabic Name", f"<span class='arabic-name'>{profile['arabic_name']}</span>"),
                    ("Default Project", profile["project_name"]),
                    ("Net Earning", money(profile["new_net_earning"])),
                ]
            )
            ptab1, ptab2, ptab3, ptab4 = st.tabs(["Project Allocation", "Payroll History", "Allowance History", "Bonus History"])
            with ptab1:
                st.dataframe(read_allocation_report(employee_code=selected), use_container_width=True, hide_index=True)
            with ptab2:
                st.dataframe(payroll_transactions_df(employee_code=selected), use_container_width=True, hide_index=True)
            with ptab3:
                st.dataframe(allowances_report_df(employee_code=selected), use_container_width=True, hide_index=True)
            with ptab4:
                employee_bonus_profile_section(selected)


def projects_page() -> None:
    page_header("Projects", "Manage projects and inspect employees, payroll, allowances, bonus and yearly costs by project.")
    df = projects_df()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export Project List", excel_bytes({"Projects": df}), "projects.xlsx")

    tab_add, tab_edit, tab_view = st.tabs(["Add Project", "Edit / Disable", "Project Dashboard"])
    with tab_add:
        if require_write():
            with st.form("add_project"):
                c1, c2, c3 = st.columns(3)
                code = c1.text_input("Project Code")
                name = c2.text_input("Project Name")
                client = c3.text_input("Client Name")
                c4, c5, c6 = st.columns(3)
                org = c4.text_input("Organization", "AFM")
                location = c5.text_input("Location", "Egypt")
                start = c6.date_input("Start Date", value=date.today())
                end = st.date_input("End Date", value=None)
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Add Project", type="primary")
            if submit:
                if not code or not name:
                    st.error("Project code and name are required.")
                elif fetch_one("SELECT project_id FROM projects WHERE project_code = ?", (code.strip(),)):
                    st.error("Project code already exists.")
                else:
                    run_sql(
                        """
                        INSERT INTO projects (project_code, project_name, client_name, organization, location, status,
                                              start_date, end_date, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?, ?)
                        """,
                        (code.strip(), name.strip(), client, org, location, start.isoformat(), clean_date(end), notes, now_text()),
                    )
                    audit("Project creation", "projects", code, name)
                    st.success("Project added.")
                    st.rerun()
    with tab_edit:
        if require_write():
            options = df["project_name"].tolist()
            selected = st.selectbox("Select Project", options)
            row = fetch_one("SELECT * FROM projects WHERE project_name = ?", (selected,))
            if row:
                with st.form("edit_project"):
                    c1, c2, c3 = st.columns(3)
                    code = c1.text_input("Project Code", row["project_code"])
                    name = c2.text_input("Project Name", row["project_name"])
                    client = c3.text_input("Client Name", row["client_name"] or "")
                    c4, c5, c6 = st.columns(3)
                    org = c4.text_input("Organization", row["organization"] or "")
                    location = c5.text_input("Location", row["location"] or "")
                    status = c6.selectbox("Status", ["Active", "Inactive"], index=0 if row["status"] == "Active" else 1)
                    c7, c8 = st.columns(2)
                    start = c7.date_input("Start Date", value=pd.to_datetime(row["start_date"]).date() if row["start_date"] else date.today())
                    end = c8.date_input("End Date", value=pd.to_datetime(row["end_date"]).date() if row["end_date"] else None)
                    notes = st.text_area("Notes", row["notes"] or "")
                    submit = st.form_submit_button("Save Project", type="primary")
                if submit:
                    run_sql(
                        """
                        UPDATE projects
                        SET project_code = ?, project_name = ?, client_name = ?, organization = ?, location = ?,
                            status = ?, start_date = ?, end_date = ?, notes = ?, updated_at = ?
                        WHERE project_id = ?
                        """,
                        (code, name, client, org, location, status, start.isoformat(), clean_date(end), notes, now_text(), row["project_id"]),
                    )
                    audit("Project update", "projects", row["project_id"], name)
                    st.success("Project saved.")
                    st.rerun()
    with tab_view:
        options = df["project_name"].tolist()
        selected = st.selectbox("Project", options, key="project_dash_select")
        project_id = int(df.loc[df["project_name"] == selected, "project_id"].iloc[0])
        employees = read_df(
            """
            SELECT e.employee_code, e.arabic_name, e.department, e.section, e.position, e.new_net_earning, e.status
            FROM employees e
            WHERE e.default_project_id = ?
            ORDER BY e.employee_code
            """,
            (project_id,),
        )
        payroll = read_df(
            """
            SELECT year, month, SUM(allocated_net_salary) AS net_salary, SUM(allocated_allowances) AS allowances,
                   SUM(allocated_tax) AS tax, SUM(allocated_employee_insurance) AS employee_insurance,
                   SUM(allocated_company_insurance) AS company_insurance,
                   SUM(allocated_total_company_cost) AS total_company_cost
            FROM payroll_project_allocations
            WHERE project_id = ?
            GROUP BY year, month
            ORDER BY year DESC, month DESC
            """,
            (project_id,),
        )
        allowance = read_df(
            """
            SELECT a.allowance_id, a.employee_code, e.arabic_name, a.allowance_type, a.allowance_name, a.amount,
                   a.recurring, a.payment_type, a.status
            FROM employee_allowances a
            JOIN employees e ON e.employee_code = a.employee_code
            WHERE a.specific_project_id = ? OR e.default_project_id = ?
            ORDER BY a.allowance_id DESC
            """,
            (project_id, project_id),
        )
        bonus = read_df(
            """
            SELECT b.*, e.arabic_name, p.project AS allocated_project
            FROM employee_bonuses b
            JOIN employees e ON e.employee_code = b.employee_code
            JOIN bonus_project_allocations p ON p.bonus_id = b.id
            WHERE p.project = ?
            ORDER BY b.created_at DESC
            """,
            (selected,),
        )
        kpi_cards(
            [
                ("Employees", f"{len(employees):,}"),
                ("Allowance Cost", money(allowance["amount"].sum() if not allowance.empty else 0)),
                ("Payroll Cost", money(payroll["total_company_cost"].sum() if not payroll.empty else 0)),
                ("Bonus Cost", money(bonus["company_cost_difference"].sum() if not bonus.empty else 0)),
            ]
        )
        t1, t2, t3, t4 = st.tabs(["Employees", "Payroll History", "Allowance History", "Bonus History"])
        with t1:
            st.dataframe(employees, use_container_width=True, hide_index=True)
        with t2:
            st.dataframe(payroll, use_container_width=True, hide_index=True)
        with t3:
            st.dataframe(allowance, use_container_width=True, hide_index=True)
        with t4:
            st.dataframe(bonus, use_container_width=True, hide_index=True)
        st.download_button(
            "Export Project Payroll Report",
            excel_bytes({"Employees": employees, "Payroll": payroll, "Allowances": allowance, "Bonus": bonus}),
            f"{selected.replace(' ', '_')}_project_report.xlsx",
        )


def read_allocation_report(employee_code: str | None = None) -> pd.DataFrame:
    where = ""
    params: tuple = ()
    if employee_code:
        where = "WHERE a.employee_code = ?"
        params = (employee_code,)
    return read_df(
        f"""
        SELECT a.allocation_id, a.employee_code, e.arabic_name AS employee_name, e.department, e.section, e.position,
               p.project_name AS project, a.allocation_type, a.allocation_percentage, a.fixed_allocation_amount,
               a.effective_from, a.effective_to, a.is_primary_project, a.status, a.notes
        FROM employee_project_allocations a
        JOIN employees e ON e.employee_code = a.employee_code
        JOIN projects p ON p.project_id = a.project_id
        {where}
        ORDER BY a.employee_code, a.status, a.effective_from DESC
        """,
        params,
    )


def allocation_page() -> None:
    page_header("Employee Project Allocation", "Split employee payroll, allowance and bonus cost by percentage or fixed amount.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    df = read_allocation_report()
    c1, c2, c3 = st.columns(3)
    emp_filter = c1.selectbox("Employee", ["All"] + [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
    project_filter = c2.selectbox("Project", ["All"] + list(projects.keys()))
    status_filter = c3.selectbox("Status", ["All", "Active", "Inactive"])
    view = df.copy()
    if emp_filter != "All":
        view = view[view["employee_code"] == emp_filter.split(" - ")[0]]
    if project_filter != "All":
        view = view[view["project"] == project_filter]
    if status_filter != "All":
        view = view[view["status"] == status_filter]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Export Allocation Report", excel_bytes({"Allocations": view}), "project_allocations.xlsx")

    tab_add, tab_validate, tab_edit = st.tabs(["Assign / Split", "Validation", "Edit / Disable"])
    with tab_add:
        if require_write():
            with st.form("add_allocation"):
                employee_label = st.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()], key="allocation_employee")
                c1, c2, c3 = st.columns(3)
                project_value = c1.selectbox("Project", list(projects.keys()), key="allocation_project")
                allocation_type = c2.selectbox("Allocation Type", ["Percentage", "Fixed Amount"])
                is_primary = c3.checkbox("Is Primary Project")
                c4, c5 = st.columns(2)
                allocation_percentage = c4.number_input("Allocation Percentage", min_value=0.0, max_value=100.0, value=100.0 if allocation_type == "Percentage" else 0.0, step=1.0)
                fixed_amount = c5.number_input("Fixed Allocation Amount", min_value=0.0, value=0.0, step=100.0)
                c6, c7, c8 = st.columns(3)
                effective_from = c6.date_input("Effective From", value=date.today())
                effective_to = c7.date_input("Effective To", value=None)
                status = c8.selectbox("Status", ["Active", "Inactive"])
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Save Allocation", type="primary")
            if submitted:
                employee_code = employee_label.split(" - ")[0]
                run_sql(
                    """
                    INSERT INTO employee_project_allocations
                    (employee_code, project_id, allocation_type, allocation_percentage, fixed_allocation_amount,
                     effective_from, effective_to, is_primary_project, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        employee_code,
                        projects[project_value],
                        allocation_type,
                        allocation_percentage if allocation_type == "Percentage" else 0,
                        fixed_amount if allocation_type == "Fixed Amount" else 0,
                        effective_from.isoformat(),
                        clean_date(effective_to),
                        1 if is_primary else 0,
                        status,
                        notes,
                        now_text(),
                    ),
                )
                audit("Employee project allocation creation", "employee_project_allocations", employee_code, project_value)
                st.success("Allocation saved.")
                st.rerun()
    with tab_validate:
        validation = allocation_validation_df()
        st.dataframe(validation, use_container_width=True, hide_index=True)
    with tab_edit:
        if require_write() and not df.empty:
            allocation_id = st.selectbox("Allocation ID", df["allocation_id"].tolist())
            row = fetch_one("SELECT * FROM employee_project_allocations WHERE allocation_id = ?", (int(allocation_id),))
            if row:
                with st.form("edit_allocation"):
                    c1, c2, c3 = st.columns(3)
                    allocation_type = c1.selectbox("Allocation Type", ["Percentage", "Fixed Amount"], index=0 if row["allocation_type"] == "Percentage" else 1)
                    pct_value = c2.number_input("Allocation Percentage", value=float(row["allocation_percentage"]), min_value=0.0, max_value=100.0)
                    fixed_value = c3.number_input("Fixed Allocation Amount", value=float(row["fixed_allocation_amount"]), min_value=0.0)
                    c4, c5, c6 = st.columns(3)
                    is_primary = c4.checkbox("Is Primary Project", value=bool(row["is_primary_project"]))
                    status = c5.selectbox("Status", ["Active", "Inactive"], index=0 if row["status"] == "Active" else 1)
                    effective_from = c6.date_input("Effective From", value=pd.to_datetime(row["effective_from"]).date() if row["effective_from"] else date.today())
                    effective_to = st.date_input("Effective To", value=pd.to_datetime(row["effective_to"]).date() if row["effective_to"] else None)
                    notes = st.text_area("Notes", row["notes"] or "")
                    save = st.form_submit_button("Save Allocation", type="primary")
                if save:
                    run_sql(
                        """
                        UPDATE employee_project_allocations
                        SET allocation_type = ?, allocation_percentage = ?, fixed_allocation_amount = ?, effective_from = ?,
                            effective_to = ?, is_primary_project = ?, status = ?, notes = ?, updated_at = ?
                        WHERE allocation_id = ?
                        """,
                        (
                            allocation_type,
                            pct_value if allocation_type == "Percentage" else 0,
                            fixed_value if allocation_type == "Fixed Amount" else 0,
                            effective_from.isoformat(),
                            clean_date(effective_to),
                            1 if is_primary else 0,
                            status,
                            notes,
                            now_text(),
                            allocation_id,
                        ),
                    )
                    audit("Employee project allocation update", "employee_project_allocations", allocation_id, status)
                    st.success("Allocation updated.")
                    st.rerun()


def allocation_validation_df() -> pd.DataFrame:
    employees = read_df("SELECT employee_code, arabic_name, department, section, position FROM employees WHERE status = 'Active'")
    rows = []
    today = date.today()
    year, month = today.year, today.month
    for emp in employees.itertuples():
        alloc = active_allocations(emp.employee_code, year, month)
        pct_rows = [a for a in alloc if a["allocation_type"] == "Percentage"]
        fixed_rows = [a for a in alloc if a["allocation_type"] == "Fixed Amount"]
        total_pct = sum(safe_float(a["allocation_percentage"]) for a in pct_rows)
        status = "Valid"
        issue = ""
        if not alloc:
            status = "Valid"
            issue = "No explicit allocation; default project will be used at 100%."
            total_pct = 100
        elif pct_rows and not fixed_rows and abs(total_pct - 100) > 0.01:
            status = "Invalid"
            issue = "Active percentage allocation must equal 100%."
        elif fixed_rows and not any(a["is_primary_project"] for a in alloc):
            status = "Invalid"
            issue = "Fixed amount allocation needs a primary/default project for remaining cost."
        rows.append(
            {
                "employee_code": emp.employee_code,
                "employee_name": emp.arabic_name,
                "department": emp.department,
                "section": emp.section,
                "position": emp.position,
                "active_allocation_count": len(alloc),
                "percentage_total": total_pct,
                "status": status,
                "issue": issue,
            }
        )
    return pd.DataFrame(rows)


def allowances_report_df(employee_code: str | None = None) -> pd.DataFrame:
    where = ""
    params: tuple = ()
    if employee_code:
        where = "WHERE a.employee_code = ?"
        params = (employee_code,)
    return read_df(
        f"""
        SELECT a.allowance_id, a.employee_code, e.arabic_name AS employee_name, a.allowance_type, a.allowance_name,
               a.amount, a.calculation_type, a.payment_type,
               CASE WHEN a.taxable = 1 THEN 'Yes' ELSE 'No' END AS taxable,
               CASE WHEN a.social_insurance_applicable = 1 THEN 'Yes' ELSE 'No' END AS social_insurance_applicable,
               a.recurring, a.project_charging_method, p.project_name AS specific_project,
               a.effective_from, a.effective_to, a.department, a.status, a.paid_year, a.paid_month, a.notes
        FROM employee_allowances a
        JOIN employees e ON e.employee_code = a.employee_code
        LEFT JOIN projects p ON p.project_id = a.specific_project_id
        {where}
        ORDER BY a.allowance_id DESC
        """,
        params,
    )


def allowances_page() -> None:
    page_header("Employee Allowances", "Recurring, temporary and one-time allowances with project charging and payroll inclusion.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    df = allowances_report_df()
    f1, f2, f3, f4, f5 = st.columns(5)
    employee_filter = f1.selectbox("Employee", ["All"] + [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
    project_filter = f2.selectbox("Project", ["All"] + list(projects.keys()))
    department_filter = f3.selectbox("Department", ["All"] + sorted(df["department"].dropna().unique().tolist()))
    status_filter = f4.selectbox("Status", ["All", "Active", "Inactive"])
    type_filter = f5.selectbox("Type", ["All"] + sorted(df["allowance_type"].dropna().unique().tolist()))
    view = df.copy()
    if employee_filter != "All":
        view = view[view["employee_code"] == employee_filter.split(" - ")[0]]
    if project_filter != "All":
        view = view[view["specific_project"].fillna("") == project_filter]
    if department_filter != "All":
        view = view[view["department"] == department_filter]
    if status_filter != "All":
        view = view[view["status"] == status_filter]
    if type_filter != "All":
        view = view[view["allowance_type"] == type_filter]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Export Allowances to Excel", excel_bytes({"Allowances": view}), "allowances.xlsx")

    tab_add, tab_edit = st.tabs(["Add Allowance", "Edit / Disable"])
    with tab_add:
        if require_write():
            with st.form("add_allowance"):
                employee_label = st.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
                c1, c2, c3 = st.columns(3)
                allowance_type = c1.selectbox("Allowance Type", option_rows("allowance_types", "allowance_type"))
                allowance_name = c2.text_input("Allowance Name")
                amount = c3.number_input("Amount", min_value=0.0, step=100.0)
                c4, c5, c6 = st.columns(3)
                calc_type = c4.selectbox("Calculation Type", ["Fixed Amount", "Percentage of Basic", "Percentage of Gross", "Percentage of Net"])
                payment_type = c5.selectbox("Payment Type", ["Net Allowance", "Gross Allowance"])
                recurring = c6.selectbox("Recurring", ["Monthly", "One Time", "Temporary"])
                c7, c8, c9 = st.columns(3)
                taxable = c7.selectbox("Taxable", ["Yes", "No"])
                insurance = c8.selectbox("Social Insurance Applicable", ["No", "Yes"])
                charge_method = c9.selectbox("Project Charging Method", PROJECT_CHARGING_METHODS)
                c10, c11, c12 = st.columns(3)
                specific_project = c10.selectbox("Specific Project", [""] + list(projects.keys()), disabled=charge_method != "Charge to Specific Project")
                effective_from = c11.date_input("Effective From", value=date.today())
                effective_to = c12.date_input("Effective To", value=None)
                c13, c14, c15 = st.columns(3)
                paid_year = c13.number_input("One-Time Year", min_value=0, max_value=2100, value=0, help="Optional. Used for one-time payroll selection.")
                paid_month = c14.number_input("One-Time Month", min_value=0, max_value=12, value=0)
                status = c15.selectbox("Status", ["Active", "Inactive"])
                department = st.text_input("Department", value=employees.loc[employees["employee_code"] == employee_label.split(" - ")[0], "department"].iloc[0])
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Save Allowance", type="primary")
            if submitted:
                employee_code = employee_label.split(" - ")[0]
                run_sql(
                    """
                    INSERT INTO employee_allowances
                    (employee_code, allowance_type, allowance_name, amount, calculation_type, payment_type, taxable,
                     social_insurance_applicable, recurring, project_charging_method, specific_project_id, effective_from,
                     effective_to, department, status, paid_year, paid_month, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        employee_code,
                        allowance_type,
                        allowance_name or allowance_type,
                        amount,
                        calc_type,
                        payment_type,
                        1 if taxable == "Yes" else 0,
                        1 if insurance == "Yes" else 0,
                        recurring,
                        charge_method,
                        projects.get(specific_project) if specific_project else None,
                        effective_from.isoformat(),
                        clean_date(effective_to),
                        department,
                        status,
                        int(paid_year) or None,
                        int(paid_month) or None,
                        notes,
                        now_text(),
                    ),
                )
                audit("Employee allowance creation", "employee_allowances", employee_code, allowance_name or allowance_type)
                st.success("Allowance saved.")
                st.rerun()
    with tab_edit:
        if require_write() and not df.empty:
            allowance_id = st.selectbox("Allowance ID", df["allowance_id"].tolist())
            row = fetch_one("SELECT * FROM employee_allowances WHERE allowance_id = ?", (int(allowance_id),))
            if row:
                with st.form("edit_allowance"):
                    c1, c2, c3 = st.columns(3)
                    allowance_name = c1.text_input("Allowance Name", row["allowance_name"])
                    amount = c2.number_input("Amount", value=float(row["amount"]), min_value=0.0)
                    status = c3.selectbox("Status", ["Active", "Inactive"], index=0 if row["status"] == "Active" else 1)
                    c4, c5, c6 = st.columns(3)
                    calc_type = c4.selectbox("Calculation Type", ["Fixed Amount", "Percentage of Basic", "Percentage of Gross", "Percentage of Net"], index=["Fixed Amount", "Percentage of Basic", "Percentage of Gross", "Percentage of Net"].index(row["calculation_type"]))
                    payment_type = c5.selectbox("Payment Type", ["Net Allowance", "Gross Allowance"], index=0 if row["payment_type"] == "Net Allowance" else 1)
                    recurring = c6.selectbox("Recurring", ["Monthly", "One Time", "Temporary"], index=["Monthly", "One Time", "Temporary"].index(row["recurring"]))
                    c7, c8, c9 = st.columns(3)
                    charge_method = c7.selectbox("Project Charging Method", PROJECT_CHARGING_METHODS, index=PROJECT_CHARGING_METHODS.index(row["project_charging_method"]))
                    current_specific = project_name(row["specific_project_id"])
                    specific_project = c8.selectbox("Specific Project", [""] + list(projects.keys()), index=([""] + list(projects.keys())).index(current_specific) if current_specific in projects else 0)
                    department = c9.text_input("Department", row["department"] or "")
                    notes = st.text_area("Notes", row["notes"] or "")
                    save = st.form_submit_button("Save Allowance", type="primary")
                if save:
                    run_sql(
                        """
                        UPDATE employee_allowances
                        SET allowance_name = ?, amount = ?, calculation_type = ?, payment_type = ?, recurring = ?,
                            project_charging_method = ?, specific_project_id = ?, department = ?, status = ?,
                            notes = ?, updated_at = ?
                        WHERE allowance_id = ?
                        """,
                        (allowance_name, amount, calc_type, payment_type, recurring, charge_method, projects.get(specific_project) if specific_project else None, department, status, notes, now_text(), allowance_id),
                    )
                    audit("Employee allowance update", "employee_allowances", allowance_id, status)
                    st.success("Allowance updated.")
                    st.rerun()


def setup_page() -> None:
    page_header("Payroll Setup", "Egyptian tax laws, exemptions, brackets, social insurance, and salary calculation rules.")
    can_tax = has_action("Can Edit Tax Setup") or is_admin()
    can_insurance = has_action("Can Edit Insurance Setup") or is_admin()
    tabs = st.tabs(["Tax Laws", "Tax Brackets", "Exemptions", "Social Insurance", "Salary Calculation Rules"])

    with tabs[0]:
        st.subheader("Tax Laws")
        laws = read_df(
            """
            SELECT tax_law_id, law_name, law_number, effective_year, effective_from, effective_to,
                   is_default, status, notes
            FROM tax_laws
            ORDER BY is_default DESC, effective_from DESC, effective_year DESC
            """
        )
        st.dataframe(laws, use_container_width=True, hide_index=True)
        missing = []
        if laws.empty:
            missing.append("Missing tax law")
        if fetch_one("SELECT COUNT(*) AS c FROM tax_brackets WHERE COALESCE(status, 'Active') = 'Active'")["c"] == 0:
            missing.append("Missing tax brackets")
        if fetch_one("SELECT COUNT(*) AS c FROM tax_exemptions WHERE status = 'Active'")["c"] == 0:
            missing.append("Missing exemption setup")
        for message in missing:
            st.error(message)
        if can_tax:
            c1, c2, c3 = st.columns(3)
            if c1.button("Apply Egypt Tax Law 175/2023 Preset", type="primary"):
                tax_law_id = apply_law_175_2023_preset(make_default=False)
                st.success(f"Applied Law 175/2023 preset to Tax Law ID {tax_law_id}.")
                st.rerun()
            if c2.button("Apply Current Egypt Tax Preset 2024/2026", type="primary"):
                tax_law_id = apply_current_egypt_tax_preset(make_default=True)
                st.success(f"Applied current Egypt tax preset and set it as default: Tax Law ID {tax_law_id}.")
                st.rerun()
            law_labels = [f"{r.tax_law_id} - {r.law_name}" for r in laws.itertuples()]
            if law_labels:
                selected_default = c3.selectbox("Choose Default Tax Law", law_labels)
                if st.button("Set Selected Law as Default"):
                    tax_law_id = int(selected_default.split(" - ")[0])
                    run_sql("UPDATE tax_laws SET is_default = 0")
                    run_sql("UPDATE tax_laws SET is_default = 1 WHERE tax_law_id = ?", (tax_law_id,))
                    run_sql(
                        """
                        INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
                        VALUES ('default_tax_law_id', ?, 'Default tax law for calculations.')
                        ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value
                        """,
                        (str(tax_law_id),),
                    )
                    audit("Setup changes", "tax_laws", tax_law_id, "Default tax law changed")
                    st.success("Default tax law updated.")
                    st.rerun()
            with st.form("tax_law_form_v2"):
                c1, c2, c3 = st.columns(3)
                law_name = c1.text_input("Tax Law Name")
                law_number = c2.text_input("Law Number")
                effective_year = c3.number_input("Effective Year", min_value=2000, max_value=2100, value=date.today().year)
                c4, c5, c6 = st.columns(3)
                effective_from = c4.date_input("Effective From", value=date.today())
                effective_to = c5.date_input("Effective To", value=None)
                status = c6.selectbox("Status", ["Active", "Inactive"])
                is_default_value = st.checkbox("Is Default")
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Save Tax Law", type="primary")
            if submit:
                if not law_name:
                    st.error("Tax Law Name is required.")
                else:
                    with db() as conn:
                        if is_default_value:
                            conn.execute("UPDATE tax_laws SET is_default = 0")
                        cur = conn.execute(
                            """
                            INSERT INTO tax_laws
                            (law_name, law_number, effective_year, effective_from, effective_to, is_default,
                             status, notes, personal_exemption, additional_exemption, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                            """,
                            (law_name, law_number, int(effective_year), effective_from.isoformat(), clean_date(effective_to), 1 if is_default_value else 0, status, notes, now_text()),
                        )
                        conn.commit()
                    audit("Setup changes", "tax_laws", cur.lastrowid, law_name)
                    st.success("Tax law saved.")
                    st.rerun()

    with tabs[1]:
        st.subheader("Tax Brackets")
        laws = read_df("SELECT tax_law_id, law_name FROM tax_laws ORDER BY is_default DESC, effective_year DESC")
        if laws.empty:
            st.error("Missing tax law")
        else:
            law_label = st.selectbox("Tax Law", [f"{r.tax_law_id} - {r.law_name}" for r in laws.itertuples()], key="bracket_law_select")
            law_id = int(law_label.split(" - ")[0])
            year = st.number_input("Bracket Year", min_value=2000, max_value=2100, value=date.today().year)
            brackets = read_df(
                """
                SELECT bracket_id, tax_law_id, year, income_from, income_to, tax_rate, bracket_order,
                       applies_for_income_level_from, applies_for_income_level_to,
                       is_skipped_for_higher_income, status
                FROM tax_brackets
                WHERE tax_law_id = ? AND year = ?
                ORDER BY applies_for_income_level_from, bracket_order
                """,
                (law_id, int(year)),
            )
            invalid = brackets[(brackets["income_to"].notna()) & (brackets["income_to"] <= brackets["income_from"])] if not brackets.empty else pd.DataFrame()
            if not invalid.empty:
                st.error("Invalid bracket range detected: Income To must be greater than Income From.")
            st.dataframe(brackets, use_container_width=True, hide_index=True)
            c1, c2 = st.columns(2)
            c1.download_button("Export Tax Brackets", excel_bytes({"Tax Brackets": brackets}), f"tax_brackets_{law_id}_{int(year)}.xlsx")
            imported = c2.file_uploader("Import Tax Brackets", type=["csv", "xlsx"], key="tax_bracket_import")
            if imported and can_tax:
                incoming = pd.read_csv(imported) if imported.name.lower().endswith(".csv") else pd.read_excel(imported)
                st.dataframe(incoming.head(100), use_container_width=True, hide_index=True)
            if can_tax:
                with st.form("bracket_form_v2"):
                    c1, c2, c3, c4 = st.columns(4)
                    order = c1.number_input("Bracket Order", min_value=1, value=int(brackets["bracket_order"].max() + 1) if not brackets.empty else 1)
                    income_from = c2.number_input("Income From", min_value=0.0)
                    income_to = c3.number_input("Income To (0 for open-ended)", min_value=0.0)
                    rate = c4.number_input("Tax Rate %", min_value=0.0, max_value=100.0, value=0.0)
                    c5, c6, c7 = st.columns(3)
                    level_from = c5.number_input("Applies For Income Level From", min_value=0.0, value=0.0)
                    level_to = c6.number_input("Applies For Income Level To (0 for open-ended)", min_value=0.0, value=0.0)
                    skipped = c7.checkbox("Is Skipped For Higher Income")
                    status = st.selectbox("Status", ["Active", "Inactive"], key="bracket_status")
                    submit = st.form_submit_button("Add Bracket", type="primary")
                if submit:
                    if income_to and income_to <= income_from:
                        st.error("Invalid bracket range.")
                    else:
                        run_sql(
                            """
                            INSERT INTO tax_brackets
                            (tax_law_id, year, income_from, income_to, min_amount, max_amount, tax_rate,
                             bracket_order, applies_for_income_level_from, applies_for_income_level_to,
                             is_skipped_for_higher_income, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (law_id, int(year), income_from, None if income_to == 0 else income_to, income_from, None if income_to == 0 else income_to, rate / 100, order, level_from, None if level_to == 0 else level_to, 1 if skipped else 0, status),
                        )
                        audit("Setup changes", "tax_brackets", law_id, "Tax bracket added")
                        st.success("Tax bracket saved.")
                        st.rerun()

    with tabs[2]:
        st.subheader("Exemptions")
        exemptions = read_df(
            """
            SELECT e.*, l.law_name
            FROM tax_exemptions e
            JOIN tax_laws l ON l.tax_law_id = e.tax_law_id
            ORDER BY e.year DESC, l.law_name
            """
        )
        st.dataframe(exemptions, use_container_width=True, hide_index=True)
        if exemptions.empty:
            st.error("Missing exemption")
        if can_tax:
            laws = read_df("SELECT tax_law_id, law_name FROM tax_laws ORDER BY is_default DESC, effective_year DESC")
            with st.form("exemption_form"):
                law_label = st.selectbox("Tax Law", [f"{r.tax_law_id} - {r.law_name}" for r in laws.itertuples()], key="exemption_law")
                c1, c2, c3, c4 = st.columns(4)
                year = c1.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
                personal = c2.number_input("Personal Exemption Annual", min_value=0.0, value=20000.0)
                additional = c3.number_input("Additional Exemption Annual", min_value=0.0, value=20000.0)
                tax_free = c4.number_input("Tax Free Bracket Annual", min_value=0.0, value=40000.0)
                round_down = st.checkbox("Round taxable income down to nearest 10", value=True)
                status = st.selectbox("Status", ["Active", "Inactive"], key="exemption_status")
                notes = st.text_area("Notes", key="exemption_notes")
                submit = st.form_submit_button("Save Exemption", type="primary")
            if submit:
                law_id = int(law_label.split(" - ")[0])
                total = personal + additional + tax_free
                run_sql(
                    """
                    INSERT INTO tax_exemptions
                    (tax_law_id, year, personal_exemption_annual, additional_exemption_annual,
                     tax_free_bracket_annual, total_annual_exemption, round_taxable_income_down_to_nearest_10,
                     status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tax_law_id, year) DO UPDATE SET
                        personal_exemption_annual = excluded.personal_exemption_annual,
                        additional_exemption_annual = excluded.additional_exemption_annual,
                        tax_free_bracket_annual = excluded.tax_free_bracket_annual,
                        total_annual_exemption = excluded.total_annual_exemption,
                        round_taxable_income_down_to_nearest_10 = excluded.round_taxable_income_down_to_nearest_10,
                        status = excluded.status,
                        notes = excluded.notes
                    """,
                    (law_id, int(year), personal, additional, tax_free, total, 1 if round_down else 0, status, notes),
                )
                run_sql(
                    """
                    INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
                    VALUES ('round_taxable_income_down_to_nearest_10', ?, 'Egypt tax rounding option.')
                    ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value
                    """,
                    ("Yes" if round_down else "No",),
                )
                audit("Setup changes", "tax_exemptions", law_id, f"Year {year}")
                st.success("Exemption saved.")
                st.rerun()

    with tabs[3]:
        st.subheader("Social Insurance")
        ins = read_df("SELECT * FROM social_insurance_setup ORDER BY effective_year DESC")
        st.dataframe(ins, use_container_width=True, hide_index=True)
        invalid = ins[(ins["minimum_insurance_salary"].fillna(0) > ins["maximum_insurance_salary"].fillna(0)) & (ins["maximum_insurance_salary"].fillna(0) > 0)] if not ins.empty and "minimum_insurance_salary" in ins.columns else pd.DataFrame()
        if invalid.empty:
            st.success("Insurance setup validation passed.")
        else:
            st.error("Insurance minimum greater than maximum.")
        if can_insurance:
            with st.form("insurance_form_v2"):
                c1, c2, c3 = st.columns(3)
                year = c1.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
                current_insurance = fetch_one("SELECT * FROM social_insurance_setup WHERE effective_year = ?", (int(year),))
                effective_from = c2.date_input("Effective From", value=date(date.today().year, 1, 1))
                effective_to = c3.date_input("Effective To", value=date(date.today().year, 12, 31))
                c4, c5, c6, c7 = st.columns(4)
                minimum_default = safe_float(current_insurance["minimum_insurance_salary"] if current_insurance and "minimum_insurance_salary" in current_insurance.keys() else 2700)
                maximum_default = safe_float(current_insurance["maximum_insurance_salary"] if current_insurance and "maximum_insurance_salary" in current_insurance.keys() else 16700)
                employee_share_default = safe_float(current_insurance["employee_share_percent"] if current_insurance and "employee_share_percent" in current_insurance.keys() else 11)
                company_share_default = safe_float(current_insurance["company_share_percent"] if current_insurance and "company_share_percent" in current_insurance.keys() else 18.75)
                source_default = current_insurance["insurance_base_source"] if current_insurance and "insurance_base_source" in current_insurance.keys() and current_insurance["insurance_base_source"] in INSURANCE_BASE_SOURCES else "Gross Salary / 1.3"
                minimum = c4.number_input("Minimum Insurance Salary", min_value=0.0, value=minimum_default)
                maximum = c5.number_input("Maximum Insurance Salary", min_value=0.0, value=maximum_default)
                employee_share = c6.number_input("Employee Share %", min_value=0.0, max_value=100.0, value=employee_share_default)
                company_share = c7.number_input("Company Share %", min_value=0.0, max_value=100.0, value=company_share_default)
                source = st.selectbox("Insurance Base Source", INSURANCE_BASE_SOURCES, index=INSURANCE_BASE_SOURCES.index(source_default))
                status = st.selectbox("Status", ["Active", "Inactive"], key="insurance_status")
                notes = st.text_area("Notes", key="insurance_notes_v2")
                submit = st.form_submit_button("Save Social Insurance Setup", type="primary")
            if submit:
                if minimum > maximum:
                    st.error("Insurance minimum cannot be greater than maximum.")
                else:
                    run_sql(
                        """
                        INSERT INTO social_insurance_setup
                        (effective_year, effective_from, effective_to, employee_share, company_share,
                         minimum_insurance_base, maximum_insurance_base, minimum_insurance_salary,
                         maximum_insurance_salary, employee_share_percent, company_share_percent,
                         insurance_base_source, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(effective_year) DO UPDATE SET
                            effective_from = excluded.effective_from,
                            effective_to = excluded.effective_to,
                            employee_share = excluded.employee_share,
                            company_share = excluded.company_share,
                            minimum_insurance_base = excluded.minimum_insurance_base,
                            maximum_insurance_base = excluded.maximum_insurance_base,
                            minimum_insurance_salary = excluded.minimum_insurance_salary,
                            maximum_insurance_salary = excluded.maximum_insurance_salary,
                            employee_share_percent = excluded.employee_share_percent,
                            company_share_percent = excluded.company_share_percent,
                            insurance_base_source = excluded.insurance_base_source,
                            status = excluded.status,
                            notes = excluded.notes
                        """,
                        (int(year), effective_from.isoformat(), effective_to.isoformat(), employee_share / 100, company_share / 100, minimum, maximum, minimum, maximum, employee_share, company_share, source, status, notes),
                    )
                    audit("Setup changes", "social_insurance_setup", int(year), "Insurance setup saved")
                    st.success("Social insurance setup saved.")
                    st.rerun()

    with tabs[4]:
        st.subheader("Salary Calculation Rules")
        setup_df = read_df("SELECT * FROM salary_calculation_setup ORDER BY setting_name")
        st.dataframe(setup_df, use_container_width=True, hide_index=True)
        if can_tax or can_insurance:
            with st.form("salary_rules_form_v2"):
                basic_source_options = BASIC_SALARY_SOURCES
                current_basic = setting("basic_salary_source", "Use Employee Basic Salary")
                if current_basic not in basic_source_options:
                    current_basic = "Use Employee Basic Salary"
                basic_source = st.selectbox("Basic Salary Source", basic_source_options, index=basic_source_options.index(current_basic))
                insurance_source = st.selectbox("Insurance Base Source", INSURANCE_BASE_SOURCES, index=INSURANCE_BASE_SOURCES.index(setting("insurance_base_source", "Employee Insurance Salary/Base")) if setting("insurance_base_source", "Employee Insurance Salary/Base") in INSURANCE_BASE_SOURCES else 0)
                c1, c2, c3, c4, c5 = st.columns(5)
                gross_pct = c1.number_input("Gross Basic Percentage", value=safe_float(setting("gross_basic_percentage", "30")), min_value=0.0, max_value=100.0)
                tolerance = c2.number_input("Net-to-gross tolerance", value=safe_float(setting("net_to_gross_tolerance", "0.01")), min_value=0.0001, format="%.4f")
                max_iterations = c3.number_input("Maximum iterations", min_value=10, max_value=500, value=int(safe_float(setting("net_to_gross_max_iterations", "90"), 90)))
                statutory_allowance_pct = c4.number_input("Statutory Allowance %", value=safe_float(setting("statutory_allowance_percentage", "30"), 30), min_value=0.0, max_value=100.0)
                insurance_divisor = c5.number_input("Insurance Gross Divisor", value=safe_float(setting("insurance_gross_divisor", "1.3"), 1.3), min_value=0.0001, format="%.4f")
                gross_method = st.selectbox("Gross-up method", ["Binary Search"], index=0)
                round_down = st.selectbox("Round taxable income down to nearest 10", ["Yes", "No"], index=0 if bool_setting("round_taxable_income_down_to_nearest_10", True) else 1)
                submit = st.form_submit_button("Save Salary Calculation Rules", type="primary")
            if submit:
                values = {
                    "basic_salary_source": basic_source,
                    "insurance_base_source": insurance_source,
                    "gross_basic_percentage": str(gross_pct),
                    "net_to_gross_tolerance": str(tolerance),
                    "net_to_gross_max_iterations": str(max_iterations),
                    "statutory_allowance_percentage": str(statutory_allowance_pct),
                    "insurance_gross_divisor": str(insurance_divisor),
                    "gross_up_method": gross_method,
                    "round_taxable_income_down_to_nearest_10": round_down,
                }
                for key, value in values.items():
                    run_sql(
                        """
                        INSERT INTO salary_calculation_setup (setting_name, setting_value, notes)
                        VALUES (?, ?, 'Editable salary calculation rule.')
                        ON CONFLICT(setting_name) DO UPDATE SET setting_value = excluded.setting_value
                        """,
                        (key, value),
                    )
                audit("Setup changes", "salary_calculation_setup", "rules", "Salary rules updated")
                st.success("Salary calculation rules saved.")
                st.rerun()


def payroll_transactions_df(year: int | None = None, month: int | None = None, employee_code: str | None = None) -> pd.DataFrame:
    filters = []
    params: list = []
    if year:
        filters.append("t.year = ?")
        params.append(year)
    if month:
        filters.append("t.month = ?")
        params.append(month)
    if employee_code:
        filters.append("t.employee_code = ?")
        params.append(employee_code)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    return read_df(
        f"""
        SELECT t.transaction_id, t.year, t.month, t.employee_code, t.arabic_name, t.organization, t.sponsor,
               t.position, t.department, t.section, p.project_name AS default_project,
               t.project_allocation_summary, t.base_net_salary, t.recurring_net_allowances,
               t.recurring_gross_allowances, t.one_time_net_allowances, t.one_time_gross_allowances,
               t.total_allowances, t.net_earning, t.estimated_gross, t.basic_salary, t.insurance_base,
               t.employee_insurance, t.company_insurance, t.taxable_amount, t.monthly_tax, t.annual_tax,
               t.total_deductions, t.net_transfer_amount, t.total_company_cost, t.transfer_date,
               t.transfer_reference, t.payment_status, t.notes
        FROM payroll_transactions t
        LEFT JOIN projects p ON p.project_id = t.default_project_id
        {where}
        ORDER BY t.year DESC, t.month DESC, t.employee_code
        """,
        tuple(params),
    )


def payroll_run_center_page() -> None:
    page_header("Payroll Run Center", "Generate monthly payroll, include active allowances, apply project allocation, and manage transfers.")
    if not require_write():
        return
    years = list(range(2023, date.today().year + 2))
    c1, c2, c3, c4 = st.columns(4)
    year = c1.selectbox("Year", years, index=years.index(date.today().year))
    month = c2.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
    projects = project_lookup(active_only=True)
    project = c3.selectbox("Project Scope", ["All"] + list(projects.keys()))
    departments = ["All"] + option_rows("departments", "department")
    department = c4.selectbox("Department Scope", departments)
    recalculate = st.checkbox("Recalculate existing payroll transactions for this month", value=False)
    one_time_dupes = one_time_duplicate_df(year, month)
    if not one_time_dupes.empty:
        st.warning("Potential duplicate one-time allowance payments detected for this selected period. Review before generating.")
        st.dataframe(one_time_dupes, use_container_width=True, hide_index=True)
    if st.button("Generate Payroll", type="primary"):
        result = generate_payroll(year, month, projects.get(project), department, recalculate)
        st.success(f"Run #{result['run_id']} complete. Created {result['created']}, recalculated {result['recalculated']}, skipped {result['skipped']} of {result['employees']} employees.")

    st.subheader("Payroll Runs")
    runs = read_df(
        """
        SELECT r.run_id, r.year, r.month, p.project_name, r.department, r.status, r.generated_at, r.generated_by, r.closed_at, r.notes
        FROM payroll_runs r
        LEFT JOIN projects p ON p.project_id = r.project_id
        ORDER BY r.run_id DESC
        """
    )
    st.dataframe(runs, use_container_width=True, hide_index=True)
    c5, c6, c7, c8 = st.columns(4)
    if not runs.empty:
        run_id = c5.selectbox("Run ID", runs["run_id"].tolist())
        if c6.button("Mark Month as Transferred"):
            reference = f"TRF-{year}{month:02d}-{run_id}"
            run_sql(
                """
                UPDATE payroll_transactions
                SET payment_status = 'Transferred', transfer_date = ?, transfer_reference = ?, updated_at = ?
                WHERE year = ? AND month = ?
                """,
                (date.today().isoformat(), reference, now_text(), year, month),
            )
            run_sql(
                """
                UPDATE payroll_project_allocations
                SET payment_status = 'Transferred'
                WHERE year = ? AND month = ?
                """,
                (year, month),
            )
            audit("Payroll transfer status change", "payroll_transactions", f"{year}-{month:02d}", "Marked month as transferred")
            st.success("Monthly payroll marked as transferred.")
            st.rerun()
        if c7.button("Close Payroll Run"):
            run_sql("UPDATE payroll_runs SET status = 'Closed', closed_at = ? WHERE run_id = ?", (now_text(), run_id))
            audit("Payroll generation", "payroll_runs", run_id, "Run closed")
            st.success("Run closed.")
            st.rerun()
        if c8.button("Reopen Payroll Run") and is_admin():
            run_sql("UPDATE payroll_runs SET status = 'Open', closed_at = NULL WHERE run_id = ?", (run_id,))
            audit("Payroll generation", "payroll_runs", run_id, "Run reopened by admin")
            st.success("Run reopened.")
            st.rerun()

    st.subheader("Generated Payroll Preview")
    df = payroll_transactions_df(year, month)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button("Export Monthly Payroll", excel_bytes({"Payroll": df}), f"payroll_{year}_{month:02d}.xlsx")


def one_time_duplicate_df(year: int, month: int) -> pd.DataFrame:
    return read_df(
        """
        SELECT employee_code, allowance_name, amount, paid_year, paid_month, COUNT(*) AS allowance_count
        FROM employee_allowances
        WHERE recurring = 'One Time'
          AND status = 'Active'
          AND ((paid_year = ? AND paid_month = ?) OR (paid_year IS NULL AND paid_month IS NULL))
        GROUP BY employee_code, allowance_name, amount, paid_year, paid_month
        HAVING COUNT(*) > 1
        """,
        (year, month),
    )


def transactions_page() -> None:
    page_header("Payroll Transactions", "Monthly payroll transaction ledger with transfer management.")
    years = ["All"] + sorted(read_df("SELECT DISTINCT year FROM payroll_transactions ORDER BY year DESC")["year"].tolist())
    c1, c2, c3, c4 = st.columns(4)
    year = c1.selectbox("Year", years)
    month = c2.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    status = c3.selectbox("Payment Status", ["All"] + PAYMENT_STATUSES)
    department = c4.selectbox("Department", ["All"] + option_rows("departments", "department"))
    df = payroll_transactions_df(None if year == "All" else int(year), None if month == "All" else int(month))
    if status != "All":
        df = df[df["payment_status"] == status]
    if department != "All":
        df = df[df["department"] == department]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export Payroll Transactions", excel_bytes({"Payroll Transactions": df}), "payroll_transactions.xlsx")
    if can_write() and not df.empty:
        st.subheader("Bulk Update Payment Status")
        c5, c6, c7 = st.columns(3)
        new_status = c5.selectbox("New Status", PAYMENT_STATUSES)
        transfer_date = c6.date_input("Transfer Date", value=date.today())
        reference = c7.text_input("Transfer Reference", value=f"TRF-{date.today().strftime('%Y%m%d')}")
        selected_ids = st.multiselect("Transaction IDs", df["transaction_id"].tolist())
        if st.button("Apply Status Update", type="primary") and selected_ids:
            placeholders = ",".join(["?"] * len(selected_ids))
            with db() as conn:
                conn.execute(
                    f"""
                    UPDATE payroll_transactions
                    SET payment_status = ?, transfer_date = ?, transfer_reference = ?, updated_at = ?
                    WHERE transaction_id IN ({placeholders})
                    """,
                    tuple([new_status, transfer_date.isoformat(), reference, now_text()] + selected_ids),
                )
                conn.execute(
                    f"""
                    UPDATE payroll_project_allocations
                    SET payment_status = ?
                    WHERE transaction_id IN ({placeholders})
                    """,
                    tuple([new_status] + selected_ids),
                )
                conn.commit()
            audit("Payroll transfer status change", "payroll_transactions", ",".join(map(str, selected_ids)), new_status)
            st.success("Payment status updated.")
            st.rerun()


def payroll_project_allocations_df(year: int | None = None, month: int | None = None) -> pd.DataFrame:
    filters = []
    params: list = []
    if year:
        filters.append("a.year = ?")
        params.append(year)
    if month:
        filters.append("a.month = ?")
        params.append(month)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    return read_df(
        f"""
        SELECT a.payroll_project_allocation_id, a.transaction_id, a.year, a.month, a.employee_code,
               a.arabic_name, a.department, a.section, p.project_name AS project,
               a.allocation_percentage, a.allocated_net_salary, a.allocated_allowances, a.allocated_gross,
               a.allocated_tax, a.allocated_employee_insurance, a.allocated_company_insurance,
               a.allocated_total_company_cost, a.payment_status
        FROM payroll_project_allocations a
        JOIN projects p ON p.project_id = a.project_id
        {where}
        ORDER BY a.year DESC, a.month DESC, p.project_name, a.employee_code
        """,
        tuple(params),
    )


def project_cost_allocation_page() -> None:
    page_header("Payroll Project Cost Allocation", "Dedicated split table for every payroll transaction and project.")
    years = ["All"] + sorted(read_df("SELECT DISTINCT year FROM payroll_project_allocations ORDER BY year DESC")["year"].tolist())
    c1, c2, c3 = st.columns(3)
    year = c1.selectbox("Year", years)
    month = c2.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    project = c3.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))
    df = payroll_project_allocations_df(None if year == "All" else int(year), None if month == "All" else int(month))
    if project != "All":
        df = df[df["project"] == project]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export Project Cost Allocation", excel_bytes({"Project Allocation": df}), "payroll_project_cost_allocation.xlsx")


def net_to_gross_page() -> None:
    page_header("Net to Gross Calculator", "Estimate gross salary, deductions, tax, insurance and total company cost from target net.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    c1, c2, c3 = st.columns(3)
    employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
    year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    tax_laws = read_df(
        """
        SELECT tax_law_id, law_name, effective_year, is_default, effective_from
        FROM tax_laws
        WHERE status = 'Active'
        ORDER BY is_default DESC, effective_from DESC, effective_year DESC, tax_law_id DESC
        """
    )
    law_labels = [f"{r.tax_law_id} - {r.law_name} ({r.effective_year})" for r in tax_laws.itertuples()]
    default_law = active_tax_law(int(year))
    law_ids = tax_laws["tax_law_id"].tolist() if not tax_laws.empty else []
    default_index = law_ids.index(default_law["tax_law_id"]) if default_law and default_law["tax_law_id"] in law_ids else 0
    law_label = c3.selectbox("Tax Law", law_labels, index=default_index)
    employee_code = employee_label.split(" - ")[0]
    employee = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
    c4, c5, c6 = st.columns(3)
    target_net_earning = c4.number_input("Target Net Earning", value=float(employee["new_net_earning"]), min_value=0.0, step=100.0)
    allowance = c5.number_input("Allowance Amount", value=float(employee["new_allowance"]), min_value=0.0, step=100.0)
    allowance_type = c6.selectbox("Allowance Payment Type", ["Net Allowance", "Gross Allowance"])
    c7, c8, c9 = st.columns(3)
    basic_override = c7.number_input("Basic Salary Override Optional", min_value=0.0, value=0.0)
    insurance_override = c8.number_input("Insurance Base Override Optional", min_value=0.0, value=0.0)
    project = c9.selectbox("Project Optional", [""] + list(projects.keys()))
    if st.button("Calculate Net to Gross", type="primary"):
        tax_law_id = int(law_label.split(" - ")[0])
        target_net = target_net_earning
        gross_calc = gross_up_for_net(target_net, employee, int(year), tax_law_id, basic_override or None, insurance_override or None)
        if allowance_type == "Gross Allowance":
            gross_calc = calculation_from_gross(gross_calc["gross"] + allowance, employee, int(year), tax_law_id, basic_override or None, insurance_override or None)
        kpi_cards(
            [
                ("Target Net Earning", money(target_net)),
                ("Estimated Gross Salary", money(gross_calc["gross"])),
                ("Basic Salary", money(gross_calc["basic_salary"])),
                ("Statutory Allowance Component", money(gross_calc["statutory_allowance_component"])),
                ("Insurance Base Before Min/Max", money(gross_calc["insurance_base_before_limits"])),
                ("Insurance Base After Min/Max", money(gross_calc["insurance_base_after_limits"])),
                ("Employee Insurance", money(gross_calc["employee_insurance"])),
                ("Company Insurance", money(gross_calc["company_insurance"])),
                ("Annual Taxable Income", money(gross_calc["final_annual_taxable_income"])),
                ("Annual Tax", money(gross_calc["annual_tax"])),
                ("Monthly Tax", money(gross_calc["monthly_tax"])),
                ("Final Net Salary", money(gross_calc["net"])),
                ("Difference from Target", money(gross_calc["net"] - target_net)),
                ("Total Company Cost", money(gross_calc["total_company_cost"])),
            ]
        )
        breakdown_values = {key: value for key, value in gross_calc.items() if key != "bracket_breakdown"}
        breakdown = pd.DataFrame([breakdown_values]).T.reset_index()
        breakdown.columns = ["Calculation Item", "Value"]
        st.dataframe(breakdown, use_container_width=True, hide_index=True)
        st.subheader("Bracket-by-Bracket Tax Breakdown")
        st.dataframe(pd.DataFrame(gross_calc["bracket_breakdown"]), use_container_width=True, hide_index=True)


def bonus_calculation(
    employee: Row,
    year: int,
    month: int,
    bonus_type: str,
    bonus_amount: float,
    project_charging_method: str,
    specific_project_id: int | None,
    tax_law_id: int | None = None,
    taxable: bool = True,
    social_insurance_applicable: bool = False,
    tax_treatment: str = "Monthly Payroll Annualized",
) -> dict:
    tax_law = active_tax_law(year, tax_law_id)
    before_payroll, _ = payroll_calculation(employee, year, month, tax_law["tax_law_id"], include_bonus_allowances=False)
    before = calculation_from_gross(before_payroll["estimated_gross"], employee, year, tax_law["tax_law_id"])
    tax_treatment = tax_treatment or "Monthly Payroll Annualized"
    monthly_annualized = tax_treatment == "Monthly Payroll Annualized"

    def bonus_impact(gross_bonus: float) -> dict:
        gross_bonus = max(safe_float(gross_bonus), 0)
        if social_insurance_applicable:
            after_insurance = calculation_from_gross(before["gross"] + gross_bonus, employee, year, tax_law["tax_law_id"])
            employee_insurance_diff = max(after_insurance["employee_insurance"] - before["employee_insurance"], 0)
            company_insurance_diff = max(after_insurance["company_insurance"] - before["company_insurance"], 0)
        else:
            employee_insurance_diff = 0.0
            company_insurance_diff = 0.0
        taxable_bonus = gross_bonus if taxable else 0.0
        tax_before = calculate_egypt_income_tax(
            before["gross"] * 12,
            before["employee_insurance"] * 12,
                tax_law["tax_law_id"],
                year,
        )
        if monthly_annualized:
            annual_gross_after = before["gross"] * 12 + (taxable_bonus * 12)
            annual_insurance_after = (before["employee_insurance"] + employee_insurance_diff) * 12
        else:
            annual_gross_after = before["gross"] * 12 + taxable_bonus
            annual_insurance_after = before["employee_insurance"] * 12 + employee_insurance_diff
        tax_after = calculate_egypt_income_tax(
            annual_gross_after,
            annual_insurance_after,
            tax_law["tax_law_id"],
            year,
        )
        annual_tax_difference = max(safe_float(tax_after["annual_tax"]) - safe_float(tax_before["annual_tax"]), 0)
        tax_difference = annual_tax_difference / 12 if monthly_annualized else annual_tax_difference
        net_increase = gross_bonus - tax_difference - employee_insurance_diff
        company_diff = gross_bonus + company_insurance_diff
        return {
            "gross_bonus": gross_bonus,
            "tax_before": safe_float(tax_before["annual_tax"]),
            "tax_after": safe_float(tax_after["annual_tax"]),
            "annual_tax_difference": annual_tax_difference,
            "tax_difference": tax_difference,
            "employee_insurance_difference": employee_insurance_diff,
            "company_insurance_difference": company_insurance_diff,
            "net_increase": net_increase,
            "company_cost_difference": company_diff,
        }

    if bonus_type == "Net Bonus":
        target_increase = max(safe_float(bonus_amount), 0)
        low = 0.0
        high = max(target_increase * 2.5 + 1000, 1000)
        for _ in range(80):
            if bonus_impact(high)["net_increase"] >= target_increase:
                break
            high *= 1.6
        for _ in range(int(safe_float(setting("net_to_gross_max_iterations", "90"), 90))):
            mid = (low + high) / 2
            impact = bonus_impact(mid)
            if abs(impact["net_increase"] - target_increase) <= safe_float(setting("net_to_gross_tolerance", "0.01"), 0.01):
                high = mid
                break
            if impact["net_increase"] < target_increase:
                low = mid
            else:
                high = mid
        impact = bonus_impact(high)
    else:
        impact = bonus_impact(bonus_amount)
    company_diff = safe_float(impact["company_cost_difference"])
    gross_bonus = safe_float(impact["gross_bonus"])
    if project_charging_method == "Charge to Specific Project" and specific_project_id:
        summary = f"{project_name(specific_project_id)} 100.00%"
    else:
        fake_total = max(company_diff, 0)
        summary = allocation_summary(employee, year, month, fake_total)
    return {
        "gross_before": before["gross"],
        "gross_after": before["gross"] + gross_bonus,
        "gross_difference": gross_bonus,
        "tax_before": impact["tax_before"],
        "tax_after": impact["tax_after"],
        "tax_difference": impact["tax_difference"],
        "employee_insurance_before": before["employee_insurance"],
        "employee_insurance_after": before["employee_insurance"] + impact["employee_insurance_difference"],
        "employee_insurance_difference": impact["employee_insurance_difference"],
        "company_insurance_before": before["company_insurance"],
        "company_insurance_after": before["company_insurance"] + impact["company_insurance_difference"],
        "company_insurance_difference": impact["company_insurance_difference"],
        "company_cost_before": before["total_company_cost"],
        "company_cost_after": before["total_company_cost"] + company_diff,
        "company_cost_difference": company_diff,
        "net_before": before["net"],
        "net_after": before["net"] + impact["net_increase"],
        "net_increase": impact["net_increase"],
        "project_allocation_summary": summary,
        "taxable": taxable,
        "social_insurance_applicable": social_insurance_applicable,
        "tax_treatment": tax_treatment,
        "annual_tax_difference": impact.get("annual_tax_difference", impact["tax_difference"]),
        "tax_law_id": tax_law["tax_law_id"],
    }


def bonus_calculator_page() -> None:
    page_header("Bonus Calculator", "Compare salary before and after bonus, answer company cost and project charge.")
    if not require_write():
        return
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    with st.form("bonus_calc_form"):
        c1, c2, c3 = st.columns(3)
        employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
        year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
        month = c3.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
        tax_laws = read_df(
            """
            SELECT tax_law_id, law_name, effective_year, is_default, effective_from
            FROM tax_laws
            WHERE status = 'Active'
            ORDER BY is_default DESC, effective_from DESC, effective_year DESC, tax_law_id DESC
            """
        )
        default_law = active_tax_law(int(year))
        law_ids = tax_laws["tax_law_id"].tolist() if not tax_laws.empty else []
        default_index = law_ids.index(default_law["tax_law_id"]) if default_law and default_law["tax_law_id"] in law_ids else 0
        law_labels = [f"{r.tax_law_id} - {r.law_name} ({r.effective_year})" for r in tax_laws.itertuples()]
        c4, c5, c6 = st.columns(3)
        bonus_type = c4.selectbox("Bonus Type", ["Net Bonus", "Gross Bonus"])
        bonus_amount = c5.number_input("Bonus Amount", min_value=0.0, step=100.0)
        bonus_category = c6.selectbox("Bonus Category", BONUS_CATEGORIES)
        c7, c8, c9 = st.columns(3)
        charge_method = c7.selectbox("Project Charging Method", PROJECT_CHARGING_METHODS)
        specific_project = c8.selectbox("Specific Project", [""] + list(projects.keys()), disabled=charge_method != "Charge to Specific Project")
        bonus_date = c9.date_input("Bonus Date", value=date.today())
        c10, c11, c12 = st.columns(3)
        law_label = c10.selectbox("Tax Law", law_labels, index=default_index)
        taxable = c11.checkbox("Taxable", value=True)
        social_insurance_applicable = c12.checkbox("Social Insurance Applicable", value=False)
        tax_treatment = st.selectbox(
            "Bonus Tax Treatment",
            ["Monthly Payroll Annualized", "One-Time Annual Bonus"],
            help=(
                "Monthly Payroll Annualized matches the payroll sheet: calculate annual tax on the month after bonus, "
                "then use the monthly tax difference. One-Time Annual Bonus taxes only the bonus amount once in the year."
            ),
        )
        department = st.text_input("Department")
        reason = st.text_area("Bonus Reason")
        calculate = st.form_submit_button("Calculate Bonus Cost", type="primary")
    if calculate:
        employee_code = employee_label.split(" - ")[0]
        employee = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
        tax_law_id = int(law_label.split(" - ")[0])
        result = bonus_calculation(
            employee,
            int(year),
            int(month),
            bonus_type,
            bonus_amount,
            charge_method,
            projects.get(specific_project),
            tax_law_id,
            taxable,
            social_insurance_applicable,
            tax_treatment,
        )
        result.update(
            {
                "employee_code": employee_code,
                "employee_name": employee["arabic_name"],
                "year": int(year),
                "month": int(month),
                "bonus_type": bonus_type,
                "bonus_category": bonus_category,
                "bonus_amount": bonus_amount,
                "bonus_date": bonus_date.isoformat(),
                "bonus_reason": reason,
                "project_charging_method": charge_method,
                "specific_project_id": projects.get(specific_project),
                "department": department or employee["department"],
                "sponsor": employee["sponsor"],
                "tax_law_id": tax_law_id,
                "taxable": taxable,
                "social_insurance_applicable": social_insurance_applicable,
                "tax_treatment": tax_treatment,
            }
        )
        st.session_state["bonus_result"] = result

    result = st.session_state.get("bonus_result")
    if result:
        net_bonus_amount = result["bonus_amount"] if result["bonus_type"] == "Net Bonus" else result["net_increase"]
        gross_bonus_amount = result["gross_difference"] if result["bonus_type"] == "Net Bonus" else result["bonus_amount"]
        cost_multiplier = result["company_cost_difference"] / net_bonus_amount if net_bonus_amount else 0
        kpi_cards(
            [
                ("Net Bonus Amount", money(net_bonus_amount)),
                ("Gross Bonus Amount", money(gross_bonus_amount)),
                ("Tax Difference", money(result["tax_difference"])),
                ("Tax Treatment", result.get("tax_treatment", "Monthly Payroll Annualized")),
                ("Employee Insurance Difference", money(result["employee_insurance_difference"])),
                ("Company Insurance Difference", money(result["company_insurance_difference"])),
                ("Company Cost Difference", money(result["company_cost_difference"])),
                ("Cost Multiplier", f"{cost_multiplier:,.2f}x"),
                ("Final Net Increase", money(result["net_increase"])),
                ("Gross Difference", money(result["gross_difference"])),
                ("Project Carrying Cost", result["project_allocation_summary"]),
            ]
        )
        before_after = pd.DataFrame(
            [
                ["Current Gross Before Bonus", result["gross_before"]],
                ["Current Net Before Bonus", result["net_before"]],
                ["New Net After Bonus", result["net_after"]],
                ["New Gross After Bonus", result["gross_after"]],
                ["Gross Difference", result["gross_difference"]],
                ["Annual Tax Before Bonus", result["tax_before"]],
                ["Annual Tax After Bonus", result["tax_after"]],
                ["Annual Tax Difference", result.get("annual_tax_difference", result["tax_difference"])],
                ["Tax Difference Charged to Bonus", result["tax_difference"]],
                ["Bonus Tax Treatment", result.get("tax_treatment", "Monthly Payroll Annualized")],
                ["Employee Insurance Before", result["employee_insurance_before"]],
                ["Employee Insurance After", result["employee_insurance_after"]],
                ["Employee Insurance Difference", result["employee_insurance_difference"]],
                ["Company Insurance Before", result["company_insurance_before"]],
                ["Company Insurance After", result["company_insurance_after"]],
                ["Company Insurance Difference", result["company_insurance_difference"]],
                ["Company Cost Before", result["company_cost_before"]],
                ["Company Cost After", result["company_cost_after"]],
                ["Company Cost Difference", result["company_cost_difference"]],
                ["Final Net Increase", result["net_increase"]],
                ["Cost Multiplier", cost_multiplier],
            ],
            columns=["Item", "Amount"],
        )
        st.dataframe(before_after, use_container_width=True, hide_index=True)
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Save Bonus Simulation", type="primary"):
            bonus_id = save_bonus_simulation(result, saved_as_allowance=0)
            audit("Bonus simulation save", "bonus_simulations", bonus_id, result["employee_code"])
            st.success(f"Bonus simulation saved #{bonus_id}.")
        if c2.button("Save to Bonus Register"):
            try:
                bonus_id = save_bonus_register_record(result, result.get("bonus_category", "Other"), "Planned", "Draft")
                st.success(f"Bonus register record saved #{bonus_id}.")
            except ValueError as exc:
                st.error(str(exc))
        if c3.button("Save as One-Time Allowance"):
            try:
                bonus_id = save_bonus_register_record(result, result.get("bonus_category", "Other"), "Planned", "Draft", save_as_allowance=True)
                audit("Bonus saved as allowance", "employee_allowances", bonus_id, result["employee_code"])
                st.success(f"Saved in Bonus Register and as one-time allowance #{bonus_id}.")
            except ValueError as exc:
                st.error(str(exc))
        c4.download_button("Export Bonus Calculation to Excel", excel_bytes({"Bonus Calculation": before_after}), "bonus_calculation.xlsx")


def save_bonus_simulation(result: dict, saved_as_allowance: int) -> int:
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO bonus_simulations
            (employee_code, employee_name, year, month, bonus_type, bonus_amount, bonus_reason,
             project_charging_method, specific_project_id, project_allocation_summary, department, sponsor,
             gross_before, gross_after, gross_difference, tax_before, tax_after, tax_difference,
             employee_insurance_before, employee_insurance_after, employee_insurance_difference,
             company_insurance_before, company_insurance_after, company_insurance_difference,
             company_cost_before, company_cost_after, company_cost_difference, net_before, net_after,
             net_increase, saved_as_allowance, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["employee_code"],
                result["employee_name"],
                result["year"],
                result["month"],
                result["bonus_type"],
                result["bonus_amount"],
                result["bonus_reason"],
                result["project_charging_method"],
                result["specific_project_id"],
                result["project_allocation_summary"],
                result["department"],
                result["sponsor"],
                result["gross_before"],
                result["gross_after"],
                result["gross_difference"],
                result["tax_before"],
                result["tax_after"],
                result["tax_difference"],
                result["employee_insurance_before"],
                result["employee_insurance_after"],
                result["employee_insurance_difference"],
                result["company_insurance_before"],
                result["company_insurance_after"],
                result["company_insurance_difference"],
                result["company_cost_before"],
                result["company_cost_after"],
                result["company_cost_difference"],
                result["net_before"],
                result["net_after"],
                result["net_increase"],
                saved_as_allowance,
                st.session_state.get("username", "system"),
                now_text(),
            ),
        )
        conn.commit()
        return cur.lastrowid


def create_bonus_project_allocations(bonus_id: int, employee: Row, result: dict) -> None:
    if result["project_charging_method"] == "Charge to Specific Project" and result.get("specific_project_id"):
        splits = [{"project_name": project_name(result["specific_project_id"]), "ratio": 1.0, "allocation_percentage": 100.0}]
    else:
        splits = employee_project_splits(employee, int(result["year"]), int(result["month"]), result["company_cost_difference"])
    rows = []
    for split in splits:
        ratio = safe_float(split["ratio"])
        rows.append(
            (
                bonus_id,
                result["employee_code"],
                split["project_name"],
                safe_float(split["allocation_percentage"]),
                result["net_bonus_amount"] * ratio,
                result["gross_bonus_amount"] * ratio,
                result["tax_difference"] * ratio,
                result["employee_insurance_difference"] * ratio,
                result["company_insurance_difference"] * ratio,
                result["company_cost_difference"] * ratio,
                int(result["year"]),
                int(result["month"]),
            )
        )
    with db() as conn:
        conn.execute("DELETE FROM bonus_project_allocations WHERE bonus_id = ?", (bonus_id,))
        conn.executemany(
            """
            INSERT INTO bonus_project_allocations
            (bonus_id, employee_code, project, allocation_percentage, allocated_net_bonus, allocated_gross_bonus,
             allocated_tax_difference, allocated_employee_insurance_difference, allocated_company_insurance_difference,
             allocated_company_cost_difference, year, month)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def save_bonus_register_record(result: dict, bonus_category: str, payment_status: str, approval_status: str, notes: str = "", save_as_allowance: bool = False) -> int:
    if is_month_locked(int(result["year"]), int(result["month"])):
        raise ValueError(f"Payroll month is {payroll_lock_status(int(result['year']), int(result['month']))}; bonus changes are blocked.")
    employee = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (result["employee_code"],))
    net_bonus = result["bonus_amount"] if result["bonus_type"] == "Net Bonus" else result["net_increase"]
    gross_bonus = result["gross_difference"] if result["bonus_type"] == "Net Bonus" else result["bonus_amount"]
    result = dict(result)
    result["net_bonus_amount"] = net_bonus
    result["gross_bonus_amount"] = gross_bonus
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO employee_bonuses
            (employee_code, year, month, bonus_date, bonus_type, bonus_category, bonus_amount_entered,
             net_bonus_amount, gross_bonus_amount, gross_before, gross_after, gross_difference,
             net_before, net_after, net_increase, tax_before, tax_after, tax_difference,
             employee_insurance_before, employee_insurance_after, employee_insurance_difference,
             company_insurance_before, company_insurance_after, company_insurance_difference,
             company_cost_before, company_cost_after, company_cost_difference, project_charging_method,
             charged_project, payment_status, approval_status, approved_by, approved_date, paid_date,
             payment_reference, bonus_reason, notes, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["employee_code"],
                int(result["year"]),
                int(result["month"]),
                result.get("bonus_date") or date.today().isoformat(),
                result["bonus_type"],
                bonus_category,
                result["bonus_amount"],
                net_bonus,
                gross_bonus,
                result["gross_before"],
                result["gross_after"],
                result["gross_difference"],
                result["net_before"],
                result["net_after"],
                result["net_increase"],
                result["tax_before"],
                result["tax_after"],
                result["tax_difference"],
                result["employee_insurance_before"],
                result["employee_insurance_after"],
                result["employee_insurance_difference"],
                result["company_insurance_before"],
                result["company_insurance_after"],
                result["company_insurance_difference"],
                result["company_cost_before"],
                result["company_cost_after"],
                result["company_cost_difference"],
                result["project_charging_method"],
                result.get("specific_project_id"),
                payment_status,
                approval_status,
                st.session_state.get("username") if approval_status == "Approved" else None,
                now_text() if approval_status == "Approved" else None,
                date.today().isoformat() if payment_status == "Paid" else None,
                result.get("payment_reference"),
                result.get("bonus_reason"),
                notes,
                st.session_state.get("username", "system"),
                now_text(),
                now_text(),
            ),
        )
        bonus_id = cur.lastrowid
        conn.commit()
    create_bonus_project_allocations(bonus_id, employee, result)
    if save_as_allowance:
        run_sql(
            """
            INSERT INTO employee_allowances
            (employee_code, allowance_type, allowance_name, amount, calculation_type, payment_type, taxable,
             social_insurance_applicable, recurring, project_charging_method, specific_project_id, effective_from,
             effective_to, department, status, paid_year, paid_month, saved_from_bonus_id, notes, created_at)
            VALUES (?, 'Bonus', ?, ?, 'Fixed Amount', ?, 1, 0, 'One Time', ?, ?, ?, ?, ?, 'Active', ?, ?, ?, ?, ?)
            """,
            (
                result["employee_code"],
                result.get("bonus_reason") or bonus_category,
                result["bonus_amount"],
                "Net Allowance" if result["bonus_type"] == "Net Bonus" else "Gross Allowance",
                result["project_charging_method"],
                result.get("specific_project_id"),
                date(int(result["year"]), int(result["month"]), 1).isoformat(),
                month_bounds(int(result["year"]), int(result["month"]))[1],
                employee["department"],
                int(result["year"]),
                int(result["month"]),
                bonus_id,
                "Created from Bonus Register",
                now_text(),
            ),
        )
    audit("Bonus register save", "employee_bonuses", bonus_id, f"{result['employee_code']} {bonus_category} {money(result['bonus_amount'])}")
    return bonus_id


def bonus_register_df(
    year: int | str | None = None,
    month: int | str | None = None,
    employee_code: str | None = None,
    project: str | None = None,
    department: str | None = None,
    section: str | None = None,
    sponsor: str | None = None,
    bonus_type: str | None = None,
    bonus_category: str | None = None,
    payment_status: str | None = None,
    approval_status: str | None = None,
) -> pd.DataFrame:
    filters = []
    params: list = []
    if year and year != "All":
        filters.append("b.year = ?")
        params.append(int(year))
    if month and month != "All":
        filters.append("b.month = ?")
        params.append(int(month))
    if employee_code and employee_code != "All":
        filters.append("b.employee_code = ?")
        params.append(employee_code)
    if department and department != "All":
        filters.append("e.department = ?")
        params.append(department)
    if section and section != "All":
        filters.append("e.section = ?")
        params.append(section)
    if sponsor and sponsor != "All":
        filters.append("e.sponsor = ?")
        params.append(sponsor)
    if bonus_type and bonus_type != "All":
        filters.append("b.bonus_type = ?")
        params.append(bonus_type)
    if bonus_category and bonus_category != "All":
        filters.append("b.bonus_category = ?")
        params.append(bonus_category)
    if payment_status and payment_status != "All":
        filters.append("b.payment_status = ?")
        params.append(payment_status)
    if approval_status and approval_status != "All":
        filters.append("b.approval_status = ?")
        params.append(approval_status)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    df = read_df(
        f"""
        SELECT b.id AS bonus_id, b.employee_code, e.arabic_name, e.organization, e.sponsor, e.position,
               e.department, e.section, dp.project_name AS default_project, cp.project_name AS charged_project,
               b.year, b.month, b.bonus_date, b.bonus_type, b.bonus_category, b.bonus_amount_entered,
               b.net_bonus_amount, b.gross_bonus_amount, b.tax_before, b.tax_after, b.tax_difference,
               b.employee_insurance_before, b.employee_insurance_after, b.employee_insurance_difference,
               b.company_insurance_before, b.company_insurance_after, b.company_insurance_difference,
               b.gross_before, b.gross_after, b.gross_difference, b.net_before AS net_salary_before_bonus,
               b.net_after AS net_salary_after_bonus, b.net_increase, b.company_cost_before,
               b.company_cost_after, b.company_cost_difference, b.project_charging_method,
               b.payment_status, b.approval_status, b.approved_by, b.approved_date, b.paid_date,
               b.payment_reference, b.bonus_reason, b.notes, b.created_by, b.created_at, b.updated_at
        FROM employee_bonuses b
        JOIN employees e ON e.employee_code = b.employee_code
        LEFT JOIN projects dp ON dp.project_id = e.default_project_id
        LEFT JOIN projects cp ON cp.project_id = b.charged_project
        {where}
        ORDER BY b.year DESC, b.month DESC, b.bonus_date DESC, b.id DESC
        """,
        tuple(params),
    )
    if project and project != "All" and not df.empty:
        allocations = read_df("SELECT DISTINCT bonus_id FROM bonus_project_allocations WHERE project = ?", (project,))
        df = df[df["bonus_id"].isin(allocations["bonus_id"].tolist())]
    allowed = allowed_projects()
    if allowed is not None and not df.empty:
        if not allowed:
            df = df.iloc[0:0]
        else:
            placeholders = ",".join(["?"] * len(allowed))
            allocations = read_df(f"SELECT DISTINCT bonus_id FROM bonus_project_allocations WHERE project IN ({placeholders})", tuple(allowed))
            df = df[df["bonus_id"].isin(allocations["bonus_id"].tolist())]
    return restrict_df_by_access(df, None, "department")


def employee_bonus_history_df(employee_code: str) -> pd.DataFrame:
    df = bonus_register_df(employee_code=employee_code)
    return df[
        [
            "year",
            "month",
            "bonus_date",
            "bonus_category",
            "bonus_type",
            "net_bonus_amount",
            "gross_bonus_amount",
            "tax_difference",
            "employee_insurance_difference",
            "company_insurance_difference",
            "company_cost_difference",
            "payment_status",
            "approval_status",
            "charged_project",
            "bonus_reason",
            "payment_reference",
        ]
    ] if not df.empty else df


def employee_bonus_profile_section(employee_code: str) -> None:
    df = employee_bonus_history_df(employee_code)
    current_year = date.today().year
    if df.empty:
        kpi_cards([
            ("Total Bonuses This Year", money(0)),
            ("Total Bonuses All Years", money(0)),
            ("Number This Year", "0"),
            ("Last Bonus Date", "-"),
            ("Highest Bonus Amount", money(0)),
            ("Total Company Cost", money(0)),
        ])
        st.info("No bonus register records for this employee.")
        return
    this_year = df[df["year"] == current_year]
    kpi_cards(
        [
            ("Total Bonuses This Year", money(this_year["net_bonus_amount"].sum() if not this_year.empty else 0)),
            ("Total Bonuses All Years", money(df["net_bonus_amount"].sum())),
            ("Number This Year", f"{len(this_year):,}"),
            ("Last Bonus Date", str(df["bonus_date"].max())),
            ("Highest Bonus Amount", money(df["net_bonus_amount"].max())),
            ("Total Company Cost", money(df["company_cost_difference"].sum())),
        ]
    )
    display = mask_salary_columns(df)
    st.dataframe(display, use_container_width=True, hide_index=True)
    protected_download_button("Export Employee Bonus History", df, f"employee_bonus_history_{employee_code}.xlsx")


def bonus_simulations_df(employee_code: str | None = None) -> pd.DataFrame:
    where = ""
    params: tuple = ()
    if employee_code:
        where = "WHERE b.employee_code = ?"
        params = (employee_code,)
    return read_df(
        f"""
        SELECT b.bonus_simulation_id, b.employee_code, b.employee_name, b.year, b.month, b.bonus_type,
               b.bonus_amount, b.bonus_reason, b.project_charging_method, p.project_name AS specific_project,
               b.project_allocation_summary, b.department, b.sponsor, b.gross_before, b.gross_after,
               b.gross_difference, b.tax_difference, b.employee_insurance_difference,
               b.company_insurance_difference, b.company_cost_difference, b.net_increase,
               CASE WHEN b.saved_as_allowance = 1 THEN 'Yes' ELSE 'No' END AS save_as_allowance_status,
               b.created_by, b.created_at
        FROM bonus_simulations b
        LEFT JOIN projects p ON p.project_id = b.specific_project_id
        {where}
        ORDER BY b.created_at DESC
        """,
        params,
    )


def bonus_simulations_page() -> None:
    page_header("Bonus Simulations", "Saved bonus calculations with filters and export.")
    df = bonus_simulations_df()
    c1, c2, c3, c4, c5 = st.columns(5)
    employee = c1.selectbox("Employee", ["All"] + sorted(df["employee_code"].dropna().unique().tolist()) if not df.empty else ["All"])
    year = c2.selectbox("Year", ["All"] + sorted(df["year"].dropna().unique().tolist(), reverse=True) if not df.empty else ["All"])
    month = c3.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    bonus_type = c4.selectbox("Bonus Type", ["All", "Net Bonus", "Gross Bonus"])
    project = c5.selectbox("Project", ["All"] + sorted(df["specific_project"].dropna().unique().tolist()) if not df.empty else ["All"])
    view = df.copy()
    if employee != "All":
        view = view[view["employee_code"] == employee]
    if year != "All":
        view = view[view["year"] == year]
    if month != "All":
        view = view[view["month"] == month]
    if bonus_type != "All":
        view = view[view["bonus_type"] == bonus_type]
    if project != "All":
        view = view[view["specific_project"] == project]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Export Bonus Simulations", excel_bytes({"Bonus Simulations": view}), "bonus_simulations.xlsx")


def bonus_register_page() -> None:
    page_header("Bonus Register", "Track every granted bonus by employee, month, project, department, type, approval and payment status.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=False)
    years = ["All"] + list(range(2023, date.today().year + 2))
    f1, f2, f3, f4, f5 = st.columns(5)
    year = f1.selectbox("Year", years, index=years.index(date.today().year) if date.today().year in years else 0, key="bonus_reg_year")
    month = f2.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x, key="bonus_reg_month")
    employee = f3.selectbox("Employee", ["All"] + [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()], key="bonus_reg_employee")
    project = f4.selectbox("Project", ["All"] + list(projects.keys()), key="bonus_reg_project")
    department = f5.selectbox("Department", ["All"] + option_rows("departments", "department"), key="bonus_reg_department")
    f6, f7, f8, f9 = st.columns(4)
    sponsor = f6.selectbox("Sponsor", ["All"] + option_rows("sponsors", "sponsor"), key="bonus_reg_sponsor")
    bonus_type = f7.selectbox("Bonus Type", ["All", "Net Bonus", "Gross Bonus"], key="bonus_reg_type")
    bonus_category = f8.selectbox("Bonus Category", ["All"] + BONUS_CATEGORIES, key="bonus_reg_category")
    payment_status = f9.selectbox("Payment Status", ["All"] + BONUS_PAYMENT_STATUSES, key="bonus_reg_payment")
    approval_status = st.selectbox("Approval Status", ["All"] + APPROVAL_STATUSES, key="bonus_reg_approval")

    selected_employee_code = employee.split(" - ")[0] if employee != "All" else None
    df = bonus_register_df(year, month, selected_employee_code, project, department, None, sponsor, bonus_type, bonus_category, payment_status, approval_status)
    kpi_cards(
        [
            ("Bonus Records", f"{len(df):,}"),
            ("Total Net Bonus", money(df["net_bonus_amount"].sum() if not df.empty else 0)),
            ("Total Gross Bonus", money(df["gross_bonus_amount"].sum() if not df.empty else 0)),
            ("Company Cost Difference", money(df["company_cost_difference"].sum() if not df.empty else 0)),
            ("Pending / Planned", f"{df['payment_status'].isin(['Planned', 'Hold']).sum() if not df.empty else 0:,}"),
            ("Approved Unpaid", f"{((df['approval_status'] == 'Approved') & (df['payment_status'] != 'Paid')).sum() if not df.empty else 0:,}"),
        ]
    )

    tab_table, tab_add, tab_workflow, tab_alloc = st.tabs(["Register", "Add Bonus", "Approval & Payment", "Project Allocations"])
    with tab_table:
        display = mask_salary_columns(df)
        st.dataframe(display, use_container_width=True, hide_index=True)
        protected_download_button("Export Bonus Register", df, "bonus_register.xlsx")
        if not df.empty:
            c1, c2 = st.columns(2)
            with c1:
                by_month = df.groupby("month", as_index=False)["company_cost_difference"].sum()
                by_month["month_name"] = by_month["month"].map(MONTHS)
                st.subheader("Bonus by Month")
                st.bar_chart(by_month, x="month_name", y="company_cost_difference")
            with c2:
                st.subheader("Bonus by Category")
                st.bar_chart(df.groupby("bonus_category", as_index=False)["company_cost_difference"].sum(), x="bonus_category", y="company_cost_difference")
    with tab_add:
        if require_write("Bonus Register", "Can Add Bonus"):
            with st.form("bonus_register_add"):
                c1, c2, c3 = st.columns(3)
                employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()], key="bonus_register_add_employee")
                year_in = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
                month_in = c3.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
                c4, c5, c6 = st.columns(3)
                bonus_date = c4.date_input("Bonus Date", value=date.today())
                bonus_type_in = c5.selectbox("Bonus Type", ["Net Bonus", "Gross Bonus"])
                category_in = c6.selectbox("Bonus Category", BONUS_CATEGORIES)
                c7, c8, c9 = st.columns(3)
                amount = c7.number_input("Bonus Amount Entered", min_value=0.0, step=100.0)
                charge_method = c8.selectbox("Project Charging Method", PROJECT_CHARGING_METHODS)
                specific_project = c9.selectbox("Bonus Project / Charged Project", [""] + list(projects.keys()), disabled=charge_method != "Charge to Specific Project")
                c10, c11 = st.columns(2)
                payment_status_in = c10.selectbox("Payment Status", BONUS_PAYMENT_STATUSES)
                approval_status_in = c11.selectbox("Approval Status", APPROVAL_STATUSES)
                reason = st.text_area("Bonus Reason")
                notes = st.text_area("Notes")
                save_allowance = st.checkbox("Also save as one-time allowance")
                submitted = st.form_submit_button("Calculate and Save Bonus", type="primary")
            if submitted:
                if amount <= 0:
                    st.error("Bonus amount must be greater than zero.")
                elif not require_month_open(int(year_in), int(month_in)):
                    pass
                else:
                    employee_code = employee_label.split(" - ")[0]
                    employee_row = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
                    result = bonus_calculation(employee_row, int(year_in), int(month_in), bonus_type_in, amount, charge_method, projects.get(specific_project))
                    result.update(
                        {
                            "employee_code": employee_code,
                            "employee_name": employee_row["arabic_name"],
                            "year": int(year_in),
                            "month": int(month_in),
                            "bonus_date": bonus_date.isoformat(),
                            "bonus_type": bonus_type_in,
                            "bonus_category": category_in,
                            "bonus_amount": amount,
                            "bonus_reason": reason,
                            "project_charging_method": charge_method,
                            "specific_project_id": projects.get(specific_project),
                            "department": employee_row["department"],
                            "sponsor": employee_row["sponsor"],
                        }
                    )
                    try:
                        bonus_id = save_bonus_register_record(result, category_in, payment_status_in, approval_status_in, notes, save_allowance)
                        st.success(f"Bonus saved as record #{bonus_id}.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
    with tab_workflow:
        if df.empty:
            st.info("No bonus records match the current filters.")
        else:
            bonus_id = st.selectbox("Bonus ID", df["bonus_id"].tolist(), key="bonus_workflow_id")
            selected = df[df["bonus_id"] == bonus_id].iloc[0]
            kpi_cards([
                ("Employee", f"{selected['employee_code']}"),
                ("Bonus", money(selected["net_bonus_amount"])),
                ("Company Cost", money(selected["company_cost_difference"])),
                ("Current Status", f"{selected['approval_status']} / {selected['payment_status']}"),
            ])
            comments = st.text_area("Approval / Payment Comments")
            c1, c2, c3, c4, c5 = st.columns(5)
            if c1.button("Submit for Approval"):
                run_sql("UPDATE employee_bonuses SET approval_status = 'Submitted', updated_at = ? WHERE id = ?", (now_text(), int(bonus_id)))
                create_approval_request("Bonus", int(bonus_id), comments)
                audit("Bonus approval", "employee_bonuses", bonus_id, "Submitted for approval")
                st.success("Bonus submitted.")
                st.rerun()
            if c2.button("Approve Bonus"):
                if has_action("Can Approve Bonus"):
                    approve_record("Bonus", int(bonus_id), comments)
                    run_sql("UPDATE employee_bonuses SET approval_status = 'Approved', approved_by = ?, approved_date = ?, updated_at = ? WHERE id = ?", (st.session_state.get("username"), now_text(), now_text(), int(bonus_id)))
                    audit("Bonus approval", "employee_bonuses", bonus_id, "Approved")
                    st.success("Bonus approved.")
                    st.rerun()
                else:
                    st.error("You do not have permission to approve bonuses.")
            if c3.button("Reject Bonus"):
                if has_action("Can Approve Bonus"):
                    reject_record("Bonus", int(bonus_id), comments)
                    run_sql("UPDATE employee_bonuses SET approval_status = 'Rejected', updated_at = ? WHERE id = ?", (now_text(), int(bonus_id)))
                    st.success("Bonus rejected.")
                    st.rerun()
                else:
                    st.error("You do not have permission to reject bonuses.")
            if c4.button("Mark as Paid"):
                if has_action("Can Mark Bonus as Paid"):
                    reference = f"BON-{int(selected['year'])}{int(selected['month']):02d}-{int(bonus_id)}"
                    run_sql("UPDATE employee_bonuses SET payment_status = 'Paid', paid_date = ?, payment_reference = ?, updated_at = ? WHERE id = ?", (date.today().isoformat(), reference, now_text(), int(bonus_id)))
                    audit("Bonus payment", "employee_bonuses", bonus_id, reference)
                    st.success("Bonus marked as paid.")
                    st.rerun()
                else:
                    st.error("You do not have permission to mark bonuses as paid.")
            if c5.button("Put on Hold"):
                run_sql("UPDATE employee_bonuses SET payment_status = 'Hold', updated_at = ? WHERE id = ?", (now_text(), int(bonus_id)))
                audit("Bonus payment", "employee_bonuses", bonus_id, "Hold")
                st.success("Bonus put on hold.")
                st.rerun()
    with tab_alloc:
        alloc = read_df(
            """
            SELECT * FROM bonus_project_allocations
            ORDER BY year DESC, month DESC, bonus_id DESC
            """
        )
        alloc = restrict_df_by_access(alloc, "project", None)
        if project != "All":
            alloc = alloc[alloc["project"] == project]
        st.dataframe(mask_salary_columns(alloc), use_container_width=True, hide_index=True)
        protected_download_button("Export Bonus Project Allocation", alloc, "bonus_project_allocations.xlsx")


def employee_bonus_history_page() -> None:
    page_header("Employee Bonus History", "Employee-level yearly and all-time bonus history, costs, approval and payment status.")
    employees = employee_options(active_only=False)
    employee_label = st.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
    employee_code = employee_label.split(" - ")[0]
    employee_bonus_profile_section(employee_code)


def build_bonus_report(report: str, filters: dict) -> pd.DataFrame:
    df = bonus_register_df(
        filters.get("year"),
        filters.get("month"),
        filters.get("employee_code"),
        filters.get("project"),
        filters.get("department"),
        filters.get("section"),
        filters.get("sponsor"),
        filters.get("bonus_type"),
        filters.get("bonus_category"),
        filters.get("payment_status"),
        filters.get("approval_status"),
    )
    if df.empty:
        return df
    if "charged_project" in df.columns and "default_project" in df.columns:
        df = df.copy()
        df["report_project"] = df["charged_project"].fillna(df["default_project"])
        df.loc[df["report_project"].astype(str) == "", "report_project"] = df["default_project"]
    if report == "Annual Bonus Summary by Employee":
        pivot = df.pivot_table(index=["employee_code", "arabic_name", "department", "section", "report_project", "sponsor", "year"], columns="month", values="net_bonus_amount", aggfunc="sum", fill_value=0).reset_index()
        for i in range(1, 13):
            if i not in pivot.columns:
                pivot[i] = 0
        month_rename = {i: f"{MONTHS[i]} Bonus" for i in range(1, 13)}
        month_rename["report_project"] = "Project"
        pivot = pivot.rename(columns=month_rename)
        totals = df.groupby(["employee_code", "arabic_name", "department", "section", "report_project", "sponsor", "year"], as_index=False).agg(
            **{
                "Total Net Bonus": ("net_bonus_amount", "sum"),
                "Total Gross Bonus": ("gross_bonus_amount", "sum"),
                "Total Tax Difference": ("tax_difference", "sum"),
                "Total Employee Insurance Difference": ("employee_insurance_difference", "sum"),
                "Total Company Insurance Difference": ("company_insurance_difference", "sum"),
                "Total Company Cost Difference": ("company_cost_difference", "sum"),
                "Number of Bonuses": ("bonus_id", "count"),
                "Last Bonus Date": ("bonus_date", "max"),
            }
        ).rename(columns={"report_project": "Project"})
        return pivot.merge(totals, on=["employee_code", "arabic_name", "department", "section", "Project", "sponsor", "year"], how="left")
    if report == "Monthly Bonus Report":
        return df[["year", "month", "employee_code", "arabic_name", "department", "section", "report_project", "bonus_category", "bonus_type", "net_bonus_amount", "gross_bonus_amount", "company_cost_difference", "payment_status", "approval_status"]].rename(columns={"report_project": "Project"})
    if report == "Project Bonus Report":
        alloc = read_df("SELECT * FROM bonus_project_allocations")
        if filters.get("year") != "All":
            alloc = alloc[alloc["year"] == int(filters["year"])]
        if filters.get("month") != "All":
            alloc = alloc[alloc["month"] == int(filters["month"])]
        if filters.get("project") != "All":
            alloc = alloc[alloc["project"] == filters["project"]]
        return alloc.groupby(["project", "year", "month"], as_index=False).agg(
            **{
                "Total Net Bonus": ("allocated_net_bonus", "sum"),
                "Total Gross Bonus": ("allocated_gross_bonus", "sum"),
                "Total Company Cost Difference": ("allocated_company_cost_difference", "sum"),
                "Number of Employees Received Bonus": ("employee_code", "nunique"),
                "Number of Bonus Records": ("bonus_id", "nunique"),
            }
        ).rename(columns={"project": "Project"})
    if report == "Department Bonus Report":
        return df.groupby(["department", "section", "year"], as_index=False).agg(
            **{
                "Total Net Bonus": ("net_bonus_amount", "sum"),
                "Total Gross Bonus": ("gross_bonus_amount", "sum"),
                "Total Company Cost Difference": ("company_cost_difference", "sum"),
                "Number of Employees Received Bonus": ("employee_code", "nunique"),
            }
        )
    if report == "Sponsor Bonus Report":
        return df.groupby(["sponsor", "year"], as_index=False).agg(
            **{
                "Total Net Bonus": ("net_bonus_amount", "sum"),
                "Total Gross Bonus": ("gross_bonus_amount", "sum"),
                "Total Company Cost Difference": ("company_cost_difference", "sum"),
                "Number of Employees Received Bonus": ("employee_code", "nunique"),
            }
        )
    if report == "Bonus Cost Analysis Report":
        out = df[["employee_code", "arabic_name", "year", "bonus_type", "bonus_category", "net_bonus_amount", "gross_bonus_amount", "tax_difference", "employee_insurance_difference", "company_insurance_difference", "company_cost_difference"]].copy()
        out["Cost Multiplier"] = out.apply(lambda row: safe_float(row["company_cost_difference"]) / safe_float(row["net_bonus_amount"]) if safe_float(row["net_bonus_amount"]) else 0, axis=1)
        return out.rename(columns={"company_cost_difference": "Total Company Cost Difference"})
    if report == "Unpaid / Pending Bonus Report":
        pending = df[df["payment_status"].isin(["Planned", "Approved", "Hold"])]
        return pending[["employee_code", "arabic_name", "department", "report_project", "bonus_date", "bonus_amount_entered", "payment_status", "approval_status", "bonus_reason", "created_at"]].rename(columns={"report_project": "Project", "bonus_amount_entered": "Bonus Amount", "bonus_reason": "Reason"})
    return df


def bonus_reports_page() -> None:
    page_header("Bonus Reports", "Annual, monthly, project, department, sponsor, cost analysis and unpaid bonus reports.")
    base = bonus_register_df()
    current_year = date.today().year
    f1, f2, f3, f4, f5 = st.columns(5)
    report = f1.selectbox(
        "Report",
        [
            "Annual Bonus Summary by Employee",
            "Monthly Bonus Report",
            "Project Bonus Report",
            "Department Bonus Report",
            "Sponsor Bonus Report",
            "Bonus Cost Analysis Report",
            "Unpaid / Pending Bonus Report",
        ],
    )
    year = f2.selectbox("Year", ["All"] + list(range(2023, current_year + 2)), index=(["All"] + list(range(2023, current_year + 2))).index(current_year))
    month = f3.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    project = f4.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))
    department = f5.selectbox("Department", ["All"] + option_rows("departments", "department"))
    g1, g2, g3, g4, g5 = st.columns(5)
    employee = g1.selectbox("Employee", ["All"] + sorted(base["employee_code"].dropna().unique().tolist()) if not base.empty else ["All"])
    section = g2.selectbox("Section", ["All"] + option_rows("sections", "section"))
    sponsor = g3.selectbox("Sponsor", ["All"] + option_rows("sponsors", "sponsor"))
    bonus_type = g4.selectbox("Bonus Type", ["All", "Net Bonus", "Gross Bonus"])
    bonus_category = g5.selectbox("Bonus Category", ["All"] + BONUS_CATEGORIES)
    h1, h2 = st.columns(2)
    payment_status = h1.selectbox("Payment Status", ["All"] + BONUS_PAYMENT_STATUSES)
    approval_status = h2.selectbox("Approval Status", ["All"] + APPROVAL_STATUSES)
    filters = {
        "year": year,
        "month": month,
        "employee_code": employee,
        "project": project,
        "department": department,
        "section": section,
        "sponsor": sponsor,
        "bonus_type": bonus_type,
        "bonus_category": bonus_category,
        "payment_status": payment_status,
        "approval_status": approval_status,
    }
    report_df = build_bonus_report(report, filters)
    kpi_source = bonus_register_df(year, month, employee, project, department, section, sponsor, bonus_type, bonus_category, payment_status, approval_status)
    if not kpi_source.empty:
        kpi_source = kpi_source.copy()
        kpi_source["report_project"] = kpi_source["charged_project"].fillna(kpi_source["default_project"])
        kpi_source.loc[kpi_source["report_project"].astype(str) == "", "report_project"] = kpi_source["default_project"]
    kpi_cards(
        [
            ("Total Bonuses This Year", f"{len(kpi_source[kpi_source['year'] == current_year]) if not kpi_source.empty else 0:,}"),
            ("Total Net Bonus This Year", secure_money(kpi_source.loc[kpi_source["year"] == current_year, "net_bonus_amount"].sum() if not kpi_source.empty else 0, "Can View Bonus Amount")),
            ("Total Gross Bonus This Year", secure_money(kpi_source.loc[kpi_source["year"] == current_year, "gross_bonus_amount"].sum() if not kpi_source.empty else 0, "Can View Bonus Amount")),
            ("Total Company Cost", secure_money(kpi_source["company_cost_difference"].sum() if not kpi_source.empty else 0, "Can View Bonus Amount")),
            ("Employees Received Bonus", f"{kpi_source['employee_code'].nunique() if not kpi_source.empty else 0:,}"),
            ("Pending Bonuses", f"{kpi_source['payment_status'].isin(['Planned', 'Hold']).sum() if not kpi_source.empty else 0:,}"),
            ("Approved Unpaid", f"{((kpi_source['approval_status'] == 'Approved') & (kpi_source['payment_status'] != 'Paid')).sum() if not kpi_source.empty else 0:,}"),
            ("Paid Bonuses", f"{(kpi_source['payment_status'] == 'Paid').sum() if not kpi_source.empty else 0:,}"),
        ]
    )
    st.dataframe(mask_salary_columns(report_df), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        protected_download_button("Export Bonus Report to Excel", report_df, f"{report.lower().replace(' ', '_')}.xlsx")
    with c2:
        protected_download_button("Export Bonus Report to CSV", report_df, f"{report.lower().replace(' ', '_')}.csv", file_type="csv")
    if not kpi_source.empty:
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Bonus by Project")
            st.bar_chart(kpi_source.groupby("report_project", as_index=False)["company_cost_difference"].sum(), x="report_project", y="company_cost_difference")
            st.subheader("Bonus by Department")
            st.bar_chart(kpi_source.groupby("department", as_index=False)["company_cost_difference"].sum(), x="department", y="company_cost_difference")
            st.subheader("Top 10 Employees by Bonus Amount")
            top_bonus = kpi_source.groupby(["employee_code", "arabic_name"], as_index=False)["net_bonus_amount"].sum().sort_values("net_bonus_amount", ascending=False).head(10)
            st.dataframe(mask_salary_columns(top_bonus), use_container_width=True, hide_index=True)
        with c4:
            st.subheader("Bonus by Month")
            by_month = kpi_source.groupby("month", as_index=False)["company_cost_difference"].sum()
            by_month["month_name"] = by_month["month"].map(MONTHS)
            st.bar_chart(by_month, x="month_name", y="company_cost_difference")
            st.subheader("Bonus by Sponsor")
            st.bar_chart(kpi_source.groupby("sponsor", as_index=False)["company_cost_difference"].sum(), x="sponsor", y="company_cost_difference")
            st.subheader("Top 10 Employees by Company Bonus Cost")
            top_cost = kpi_source.groupby(["employee_code", "arabic_name"], as_index=False)["company_cost_difference"].sum().sort_values("company_cost_difference", ascending=False).head(10)
            st.dataframe(mask_salary_columns(top_cost), use_container_width=True, hide_index=True)


def yearly_summary_page() -> None:
    page_header("Yearly Summary", "Yearly transferred amount per employee with monthly columns and totals.")
    years = sorted(read_df("SELECT DISTINCT year FROM payroll_transactions ORDER BY year DESC")["year"].tolist(), reverse=True)
    year = st.selectbox("Year", years or [date.today().year])
    df = read_df(
        """
        SELECT employee_code, arabic_name, month, net_transfer_amount, base_net_salary, total_allowances,
               net_earning, monthly_tax, employee_insurance, company_insurance, total_company_cost, payment_status
        FROM payroll_transactions
        WHERE year = ?
        """,
        (year,),
    )
    if df.empty:
        st.info("No payroll transactions for this year.")
        return
    pivot = df.pivot_table(index=["employee_code", "arabic_name"], columns="month", values="net_transfer_amount", aggfunc="sum", fill_value=0).reset_index()
    for i in range(1, 13):
        if i not in pivot.columns:
            pivot[i] = 0
    rename = {i: MONTHS[i] for i in range(1, 13)}
    pivot = pivot.rename(columns=rename)
    totals = df.groupby(["employee_code", "arabic_name"], as_index=False).agg(
        **{
            "Total Yearly Transferred": ("net_transfer_amount", "sum"),
            "Total Base Net Salary": ("base_net_salary", "sum"),
            "Total Allowances": ("total_allowances", "sum"),
            "Total Net Earning": ("net_earning", "sum"),
            "Total Tax": ("monthly_tax", "sum"),
            "Total Employee Insurance": ("employee_insurance", "sum"),
            "Total Company Insurance": ("company_insurance", "sum"),
            "Total Company Cost": ("total_company_cost", "sum"),
            "Number of Paid Months": ("payment_status", lambda s: (s == "Transferred").sum()),
            "Number of Pending Months": ("payment_status", lambda s: (s == "Pending").sum()),
        }
    )
    summary = pivot.merge(totals, on=["employee_code", "arabic_name"])
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.download_button("Export Yearly Summary", excel_bytes({"Yearly Summary": summary}), f"yearly_summary_{year}.xlsx")


def project_yearly_summary_page() -> None:
    page_header("Project Yearly Summary", "Yearly payroll cost by project including allowances, bonus, tax, insurance and headcount allocation.")
    years = sorted(read_df("SELECT DISTINCT year FROM payroll_project_allocations ORDER BY year DESC")["year"].tolist(), reverse=True)
    year = st.selectbox("Year", years or [date.today().year])
    df = read_df(
        """
        SELECT p.project_name, a.month, a.allocated_total_company_cost, a.allocated_net_salary, a.allocated_allowances,
               a.allocated_tax, a.allocated_employee_insurance, a.allocated_company_insurance,
               a.allocation_percentage / 100.0 AS headcount_allocation
        FROM payroll_project_allocations a
        JOIN projects p ON p.project_id = a.project_id
        WHERE a.year = ?
        """,
        (year,),
    )
    if df.empty:
        st.info("No project allocation rows for this year.")
        return
    pivot = df.pivot_table(index="project_name", columns="month", values="allocated_total_company_cost", aggfunc="sum", fill_value=0).reset_index()
    for i in range(1, 13):
        if i not in pivot.columns:
            pivot[i] = 0
    pivot = pivot.rename(columns={i: f"{MONTHS[i]} Cost" for i in range(1, 13)})
    totals = df.groupby("project_name", as_index=False).agg(
        **{
            "Total Yearly Cost": ("allocated_total_company_cost", "sum"),
            "Total Net Salary": ("allocated_net_salary", "sum"),
            "Total Allowances": ("allocated_allowances", "sum"),
            "Total Tax": ("allocated_tax", "sum"),
            "Total Employee Insurance": ("allocated_employee_insurance", "sum"),
            "Total Company Insurance": ("allocated_company_insurance", "sum"),
            "Headcount Allocation": ("headcount_allocation", "sum"),
        }
    )
    bonus = read_df(
        """
        SELECT project AS project_name, SUM(allocated_company_cost_difference) AS Total_Bonus_Cost
        FROM bonus_project_allocations
        WHERE year = ?
        GROUP BY project
        """,
        (year,),
    )
    summary = pivot.merge(totals, on="project_name", how="left").merge(bonus, on="project_name", how="left")
    summary = summary.rename(columns={"project_name": "Project", "Total_Bonus_Cost": "Total Bonus Cost"}).fillna(0)
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.download_button("Export Project Yearly Summary", excel_bytes({"Project Yearly Summary": summary}), f"project_yearly_summary_{year}.xlsx")


def reports_page() -> None:
    page_header("Reports", "Filter and export payroll, project, tax, insurance, bank transfer, allowance and bonus reports.")
    report_names = [
        "Monthly payroll report",
        "Yearly payroll report",
        "Project payroll report",
        "Project allocation report",
        "Department payroll report",
        "Sponsor payroll report",
        "Employee allowances report",
        "Employee payroll history",
        "Bank transfer report",
        "Pending transfer report",
        "Bonus cost report",
        "Tax report",
        "Social insurance report",
        "Total allowances by project",
        "Total allowances by employee",
        "Project cost allocation report",
    ]
    c1, c2, c3, c4 = st.columns(4)
    report = c1.selectbox("Report", report_names)
    years = ["All"] + sorted(read_df("SELECT DISTINCT year FROM payroll_transactions ORDER BY year DESC")["year"].tolist(), reverse=True)
    year = c2.selectbox("Year", years)
    month = c3.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    project = c4.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))

    df = build_report(report, year, month, project)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Export Excel", excel_bytes({report[:31]: df}), f"{report.lower().replace(' ', '_')}.xlsx")
    st.download_button("Export CSV", csv_bytes(df), f"{report.lower().replace(' ', '_')}.csv")


def build_report(report: str, year, month, project: str) -> pd.DataFrame:
    year_val = None if year == "All" else int(year)
    month_val = None if month == "All" else int(month)
    if report in {"Monthly payroll report", "Yearly payroll report", "Employee payroll history", "Bank transfer report", "Pending transfer report", "Tax report", "Social insurance report"}:
        df = payroll_transactions_df(year_val, month_val)
        if report == "Pending transfer report":
            df = df[df["payment_status"] == "Pending"]
        if report == "Bank transfer report":
            df = df[["year", "month", "employee_code", "arabic_name", "net_transfer_amount", "payment_status", "transfer_date", "transfer_reference"]]
        if report == "Tax report":
            df = df[["year", "month", "employee_code", "arabic_name", "taxable_amount", "monthly_tax", "annual_tax"]]
        if report == "Social insurance report":
            df = df[["year", "month", "employee_code", "arabic_name", "insurance_base", "employee_insurance", "company_insurance"]]
        return df
    if report in {"Project payroll report", "Project allocation report", "Project cost allocation report"}:
        df = payroll_project_allocations_df(year_val, month_val)
        if project != "All":
            df = df[df["project"] == project]
        return df
    if report == "Department payroll report":
        df = payroll_transactions_df(year_val, month_val)
        return df.groupby("department", as_index=False).agg(
            employees=("employee_code", "nunique"),
            net_transfer_amount=("net_transfer_amount", "sum"),
            total_allowances=("total_allowances", "sum"),
            monthly_tax=("monthly_tax", "sum"),
            employee_insurance=("employee_insurance", "sum"),
            company_insurance=("company_insurance", "sum"),
            total_company_cost=("total_company_cost", "sum"),
        )
    if report == "Sponsor payroll report":
        df = payroll_transactions_df(year_val, month_val)
        return df.groupby("sponsor", as_index=False).agg(
            employees=("employee_code", "nunique"),
            net_transfer_amount=("net_transfer_amount", "sum"),
            total_allowances=("total_allowances", "sum"),
            total_company_cost=("total_company_cost", "sum"),
        )
    if report == "Employee allowances report":
        return allowances_report_df()
    if report == "Bonus cost report":
        return bonus_register_df(year_val if year_val else "All", month_val if month_val else "All", project=project)
    if report == "Total allowances by project":
        df = read_df(
            """
            SELECT COALESCE(p.project_name, dp.project_name) AS project, a.allowance_type, SUM(a.amount) AS total_allowances
            FROM employee_allowances a
            JOIN employees e ON e.employee_code = a.employee_code
            LEFT JOIN projects p ON p.project_id = a.specific_project_id
            LEFT JOIN projects dp ON dp.project_id = e.default_project_id
            GROUP BY COALESCE(p.project_name, dp.project_name), a.allowance_type
            ORDER BY project, a.allowance_type
            """
        )
        return df
    if report == "Total allowances by employee":
        return read_df(
            """
            SELECT a.employee_code, e.arabic_name, e.department, SUM(a.amount) AS total_allowances
            FROM employee_allowances a
            JOIN employees e ON e.employee_code = a.employee_code
            GROUP BY a.employee_code, e.arabic_name, e.department
            ORDER BY total_allowances DESC
            """
        )
    return pd.DataFrame()


def import_export_page() -> None:
    page_header("Import / Export", "Import employees, allowances and project allocations from CSV/XLSX with preview and validation.")
    if not require_write():
        return
    import_type = st.selectbox("Import Type", ["Employees", "Employee Allowances", "Employee Project Allocations"])
    uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if uploaded:
        if uploaded.name.lower().endswith(".csv"):
            incoming = pd.read_csv(uploaded)
        else:
            incoming = pd.read_excel(uploaded)
        st.subheader("Preview")
        st.dataframe(incoming.head(100), use_container_width=True, hide_index=True)
        issues = validate_import(import_type, incoming)
        if issues:
            st.error("Validation issues found.")
            st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)
        else:
            st.success("Validation passed.")
            if st.button("Import Data", type="primary"):
                imported = apply_import(import_type, incoming)
                audit("Import data", import_type, imported, f"Imported {imported} rows")
                st.success(f"Imported {imported} rows.")
                st.rerun()

    st.subheader("Export All System Data")
    tables = [
        "employees",
        "projects",
        "employee_project_allocations",
        "payroll_project_allocations",
        "employee_allowances",
        "allowance_types",
        "organizations",
        "sponsors",
        "departments",
        "sections",
        "positions",
        "payroll_transactions",
        "payroll_runs",
        "bonus_simulations",
        "tax_laws",
        "tax_brackets",
        "social_insurance_setup",
        "salary_calculation_setup",
        "payment_statuses",
        "audit_log",
        "users",
    ]
    sheets = {}
    for table in tables:
        df = read_df(f"SELECT * FROM {table}")
        if table == "users" and "password_hash" in df.columns:
            df["password_hash"] = "***"
        sheets[table[:31]] = df
    st.download_button("Export All Data to Excel", excel_bytes(sheets), "payroll_system_export.xlsx", type="primary")


def validate_import(import_type: str, incoming: pd.DataFrame) -> list[dict]:
    required = {
        "Employees": ["employee_code", "arabic_name", "default_project", "new_net_salary"],
        "Employee Allowances": ["employee_code", "allowance_type", "allowance_name", "amount"],
        "Employee Project Allocations": ["employee_code", "project", "allocation_type"],
    }[import_type]
    issues = []
    for col in required:
        if col not in incoming.columns:
            issues.append({"row": "", "issue": f"Missing required column: {col}"})
    if issues:
        return issues
    if "employee_code" in incoming.columns and incoming["employee_code"].duplicated().any() and import_type == "Employees":
        for code in incoming.loc[incoming["employee_code"].duplicated(), "employee_code"].tolist():
            issues.append({"row": "", "issue": f"Duplicate employee_code in file: {code}"})
    if "allocation_percentage" in incoming.columns:
        grouped = incoming.groupby("employee_code")["allocation_percentage"].sum()
        for employee_code, total in grouped.items():
            if abs(safe_float(total) - 100) > 0.01:
                issues.append({"row": employee_code, "issue": f"Allocation percentage total is {total}, expected 100."})
    return issues


def apply_import(import_type: str, incoming: pd.DataFrame) -> int:
    projects = project_lookup(active_only=False)
    count = 0
    with db() as conn:
        if import_type == "Employees":
            for _, row in incoming.iterrows():
                project_id = projects.get(row.get("default_project"))
                if not project_id:
                    continue
                new_net = safe_float(row.get("new_net_salary"))
                allowance = safe_float(row.get("new_allowance"))
                conn.execute(
                    """
                    INSERT INTO employees
                    (employee_code, organization, sponsor, arabic_name, position, department, section, default_project_id,
                     hiring_date, basic_salary, net_salary, gross_salary, new_net_salary, new_allowance, new_net_earning,
                     insurance_salary_base, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(employee_code) DO UPDATE SET
                        organization = excluded.organization,
                        sponsor = excluded.sponsor,
                        arabic_name = excluded.arabic_name,
                        position = excluded.position,
                        department = excluded.department,
                        section = excluded.section,
                        default_project_id = excluded.default_project_id,
                        hiring_date = excluded.hiring_date,
                        basic_salary = excluded.basic_salary,
                        net_salary = excluded.net_salary,
                        new_net_salary = excluded.new_net_salary,
                        new_allowance = excluded.new_allowance,
                        new_net_earning = excluded.new_net_earning,
                        insurance_salary_base = excluded.insurance_salary_base,
                        status = excluded.status,
                        notes = excluded.notes,
                        updated_at = ?
                    """,
                    (
                        str(row.get("employee_code")),
                        row.get("organization", ""),
                        row.get("sponsor", ""),
                        row.get("arabic_name", ""),
                        row.get("position", ""),
                        row.get("department", ""),
                        row.get("section", ""),
                        project_id,
                        clean_date(row.get("hiring_date")),
                        safe_float(row.get("basic_salary"), new_net),
                        new_net,
                        safe_float(row.get("gross_salary")),
                        new_net,
                        allowance,
                        new_net + allowance,
                        safe_float(row.get("insurance_salary_base"), safe_float(row.get("basic_salary"), new_net)),
                        row.get("status", "Active"),
                        row.get("notes", "Imported"),
                        now_text(),
                        now_text(),
                    ),
                )
                count += 1
        elif import_type == "Employee Allowances":
            for _, row in incoming.iterrows():
                conn.execute(
                    """
                    INSERT INTO employee_allowances
                    (employee_code, allowance_type, allowance_name, amount, calculation_type, payment_type, taxable,
                     social_insurance_applicable, recurring, project_charging_method, specific_project_id, effective_from,
                     effective_to, department, status, paid_year, paid_month, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(row.get("employee_code")),
                        row.get("allowance_type"),
                        row.get("allowance_name"),
                        safe_float(row.get("amount")),
                        row.get("calculation_type", "Fixed Amount"),
                        row.get("payment_type", "Net Allowance"),
                        1 if str(row.get("taxable", "Yes")).lower() in {"yes", "1", "true"} else 0,
                        1 if str(row.get("social_insurance_applicable", "No")).lower() in {"yes", "1", "true"} else 0,
                        row.get("recurring", "Monthly"),
                        row.get("project_charging_method", "Follow Employee Project Allocation"),
                        projects.get(row.get("specific_project")),
                        clean_date(row.get("effective_from")),
                        clean_date(row.get("effective_to")),
                        row.get("department", ""),
                        row.get("status", "Active"),
                        int(row.get("paid_year")) if not pd.isna(row.get("paid_year", None)) else None,
                        int(row.get("paid_month")) if not pd.isna(row.get("paid_month", None)) else None,
                        row.get("notes", "Imported"),
                        now_text(),
                    ),
                )
                count += 1
        else:
            for _, row in incoming.iterrows():
                conn.execute(
                    """
                    INSERT INTO employee_project_allocations
                    (employee_code, project_id, allocation_type, allocation_percentage, fixed_allocation_amount,
                     effective_from, effective_to, is_primary_project, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(row.get("employee_code")),
                        projects.get(row.get("project")),
                        row.get("allocation_type", "Percentage"),
                        safe_float(row.get("allocation_percentage")),
                        safe_float(row.get("fixed_allocation_amount")),
                        clean_date(row.get("effective_from")),
                        clean_date(row.get("effective_to")),
                        1 if str(row.get("is_primary_project", "No")).lower() in {"yes", "1", "true"} else 0,
                        row.get("status", "Active"),
                        row.get("notes", "Imported"),
                        now_text(),
                    ),
                )
                count += 1
        conn.commit()
    return count


def data_quality_page() -> None:
    page_header("Data Quality Center", "Detect missing master data, salary issues, invalid allocations and repeated one-time allowances.")
    checks = []
    queries = {
        "Missing hiring date": "SELECT employee_code, arabic_name, 'Missing hiring date' AS issue FROM employees WHERE hiring_date IS NULL OR hiring_date = ''",
        "Missing department": "SELECT employee_code, arabic_name, 'Missing department' AS issue FROM employees WHERE department IS NULL OR department = ''",
        "Missing section": "SELECT employee_code, arabic_name, 'Missing section' AS issue FROM employees WHERE section IS NULL OR section = ''",
        "Missing project": "SELECT employee_code, arabic_name, 'Missing project' AS issue FROM employees WHERE default_project_id IS NULL",
        "Missing net salary": "SELECT employee_code, arabic_name, 'Missing net salary' AS issue FROM employees WHERE new_net_salary IS NULL OR new_net_salary <= 0",
        "Negative salary": "SELECT employee_code, arabic_name, 'Negative salary' AS issue FROM employees WHERE new_net_salary < 0 OR basic_salary < 0",
        "Active employee without salary": "SELECT employee_code, arabic_name, 'Active employee without salary' AS issue FROM employees WHERE status = 'Active' AND new_net_salary <= 0",
        "Active employee without project": "SELECT employee_code, arabic_name, 'Active employee without project' AS issue FROM employees WHERE status = 'Active' AND default_project_id IS NULL",
        "Negative allowance": "SELECT employee_code, allowance_name AS arabic_name, 'Negative allowance' AS issue FROM employee_allowances WHERE amount < 0",
        "Missing allowance type": "SELECT employee_code, allowance_name AS arabic_name, 'Missing allowance type' AS issue FROM employee_allowances WHERE allowance_type IS NULL OR allowance_type = ''",
        "Missing tax setup": "SELECT '' AS employee_code, '' AS arabic_name, 'Missing tax setup' AS issue WHERE NOT EXISTS (SELECT 1 FROM tax_laws WHERE status = 'Active')",
        "Missing insurance setup": "SELECT '' AS employee_code, '' AS arabic_name, 'Missing insurance setup' AS issue WHERE NOT EXISTS (SELECT 1 FROM social_insurance_setup)",
        "One-time allowance paid more than once": """
            SELECT employee_code, allowance_name AS arabic_name, 'One-time allowance paid more than once' AS issue
            FROM employee_allowances
            WHERE recurring = 'One Time'
            GROUP BY employee_code, allowance_name, amount, paid_year, paid_month
            HAVING COUNT(*) > 1
        """,
    }
    for check_name, sql in queries.items():
        df = read_df(sql)
        if not df.empty:
            df["check"] = check_name
            checks.append(df)
    allocation = allocation_validation_df()
    invalid_alloc = allocation[allocation["status"] == "Invalid"]
    if not invalid_alloc.empty:
        checks.append(invalid_alloc.rename(columns={"employee_name": "arabic_name"})[["employee_code", "arabic_name", "issue"]].assign(check="Employee project allocation not equal 100%"))
    overlaps = overlapping_allocations_df()
    if not overlaps.empty:
        checks.append(overlaps.assign(check="Overlapping project allocation dates"))
    if checks:
        result = pd.concat(checks, ignore_index=True, sort=False)
        st.error(f"{len(result)} data quality issue rows detected.")
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button("Export Data Quality Issues", excel_bytes({"Data Quality": result}), "data_quality_issues.xlsx")
    else:
        st.success("No data quality issues detected.")


def overlapping_allocations_df() -> pd.DataFrame:
    df = read_df(
        """
        SELECT allocation_id, employee_code, effective_from, effective_to, status
        FROM employee_project_allocations
        WHERE status = 'Active'
        ORDER BY employee_code, effective_from
        """
    )
    rows = []
    for employee_code, group in df.groupby("employee_code"):
        records = group.to_dict("records")
        for i, a in enumerate(records):
            a_start = pd.to_datetime(a["effective_from"] or "1900-01-01")
            a_end = pd.to_datetime(a["effective_to"] or "2099-12-31")
            for b in records[i + 1 :]:
                b_start = pd.to_datetime(b["effective_from"] or "1900-01-01")
                b_end = pd.to_datetime(b["effective_to"] or "2099-12-31")
                if a_start <= b_end and b_start <= a_end:
                    rows.append({"employee_code": employee_code, "arabic_name": "", "issue": f"Allocations {a['allocation_id']} and {b['allocation_id']} overlap"})
    return pd.DataFrame(rows)


def audit_log_page() -> None:
    page_header("Audit Log", "Trace creations, updates, payroll generation, transfer changes, bonus actions and setup changes.")
    df = read_df("SELECT * FROM audit_log ORDER BY audit_id DESC")
    c1, c2, c3 = st.columns(3)
    username = c1.selectbox("Username", ["All"] + sorted(df["username"].dropna().unique().tolist()) if not df.empty else ["All"])
    action = c2.selectbox("Action", ["All"] + sorted(df["action"].dropna().unique().tolist()) if not df.empty else ["All"])
    entity = c3.selectbox("Entity", ["All"] + sorted(df["entity"].dropna().unique().tolist()) if not df.empty else ["All"])
    view = df.copy()
    if username != "All":
        view = view[view["username"] == username]
    if action != "All":
        view = view[view["action"] == action]
    if entity != "All":
        view = view[view["entity"] == entity]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Export Audit Log", excel_bytes({"Audit Log": view}), "audit_log.xlsx")


def users_permissions_page() -> None:
    page_header("Users & Permissions", "Manage users, roles, page access, salary permissions, project/department access and approvals.")
    if not has_action("Can Manage Users") and not is_admin():
        st.warning("You can view your own security details, but you do not have permission to manage users.")
    can_manage = has_action("Can Manage Users") or is_admin()
    tabs = st.tabs([
        "Users",
        "Roles",
        "Role Permissions",
        "User Permission Overrides",
        "Project Access",
        "Department Access",
        "Approval Requests",
        "Login & Security Log",
    ])
    with tabs[0]:
        users = read_df(
            """
            SELECT u.id AS user_id, u.full_name, u.username, u.email, u.mobile, COALESCE(r.role_name, u.role) AS role,
                   u.status, u.failed_login_attempts, u.last_login, u.created_by, u.created_at, u.updated_at, u.notes
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            ORDER BY u.username
            """
        )
        st.dataframe(users, use_container_width=True, hide_index=True)
        if can_manage:
            with st.form("user_create_update"):
                c1, c2, c3 = st.columns(3)
                user_id = c1.number_input("User ID for update (0 for new)", min_value=0, value=0)
                full_name = c2.text_input("Full Name")
                username = c3.text_input("Username")
                c4, c5, c6 = st.columns(3)
                email = c4.text_input("Email")
                mobile = c5.text_input("Mobile Number")
                password = c6.text_input("Password / Reset Password", type="password")
                c7, c8 = st.columns(2)
                roles = read_df("SELECT id, role_name FROM roles WHERE status = 'Active' ORDER BY role_name")
                role_label = c7.selectbox("Role", [f"{r.id} - {r.role_name}" for r in roles.itertuples()])
                status = c8.selectbox("Status", ["Active", "Inactive", "Locked"])
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Save User", type="primary")
            if submit:
                role_id = int(role_label.split(" - ")[0])
                role_name = role_label.split(" - ", 1)[1]
                if user_id:
                    if password:
                        run_sql(
                            """
                            UPDATE users
                            SET full_name = ?, username = ?, email = ?, mobile = ?, password_hash = ?, role_id = ?,
                                role = ?, status = ?, failed_login_attempts = CASE WHEN ? = 'Locked' THEN failed_login_attempts ELSE 0 END,
                                updated_at = ?, notes = ?
                            WHERE id = ?
                            """,
                            (full_name, username, email, mobile, hash_password(password), role_id, role_name, status, status, now_text(), notes, int(user_id)),
                        )
                    else:
                        run_sql(
                            """
                            UPDATE users
                            SET full_name = ?, username = ?, email = ?, mobile = ?, role_id = ?, role = ?,
                                status = ?, failed_login_attempts = CASE WHEN ? = 'Locked' THEN failed_login_attempts ELSE 0 END,
                                updated_at = ?, notes = ?
                            WHERE id = ?
                            """,
                            (full_name, username, email, mobile, role_id, role_name, status, status, now_text(), notes, int(user_id)),
                        )
                    audit("User updated", "users", user_id, f"Role={role_name}; Status={status}")
                else:
                    if not username or not password:
                        st.error("Username and password are required for new users.")
                    else:
                        run_sql(
                            """
                            INSERT INTO users (full_name, username, email, mobile, password_hash, role_id, role, status, created_by, created_at, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (full_name, username, email, mobile, hash_password(password), role_id, role_name, status, st.session_state.get("username"), now_text(), notes),
                        )
                        audit("User created", "users", username, f"Role={role_name}")
                st.success("User saved.")
                st.rerun()
    with tabs[1]:
        roles_df = read_df("SELECT * FROM roles ORDER BY role_name")
        st.dataframe(roles_df, use_container_width=True, hide_index=True)
        if can_manage:
            with st.form("role_form"):
                c1, c2, c3 = st.columns(3)
                role_name = c1.text_input("Role Name")
                description = c2.text_input("Description")
                status = c3.selectbox("Status", ["Active", "Inactive"])
                submit = st.form_submit_button("Save Role", type="primary")
            if submit and role_name:
                run_sql(
                    """
                    INSERT INTO roles (role_name, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(role_name) DO UPDATE SET description = excluded.description,
                        status = excluded.status, updated_at = excluded.updated_at
                    """,
                    (role_name, description, status, now_text(), now_text()),
                )
                audit("Role changed", "roles", role_name, status)
                st.success("Role saved.")
                st.rerun()
    with tabs[2]:
        roles = read_df("SELECT id, role_name FROM roles ORDER BY role_name")
        if not roles.empty:
            role_label = st.selectbox("Role", [f"{r.id} - {r.role_name}" for r in roles.itertuples()], key="role_perm_role")
            role_id = int(role_label.split(" - ")[0])
            perms = read_df(
                """
                SELECT p.permission_code, p.permission_name, p.module_name, COALESCE(rp.access_level, 'No Access') AS access_level
                FROM permissions p
                LEFT JOIN role_permissions rp ON rp.permission_code = p.permission_code AND rp.role_id = ?
                ORDER BY p.module_name, p.permission_name
                """,
                (role_id,),
            )
            if can_manage:
                edited = st.data_editor(
                    perms,
                    use_container_width=True,
                    hide_index=True,
                    column_config={"access_level": st.column_config.SelectboxColumn("Access Level", options=ACCESS_LEVELS)},
                    disabled=["permission_code", "permission_name", "module_name"],
                    key="role_perm_editor",
                )
                if st.button("Save Role Permissions", type="primary"):
                    with db() as conn:
                        for row in edited.to_dict("records"):
                            conn.execute(
                                """
                                INSERT INTO role_permissions (role_id, permission_code, access_level)
                                VALUES (?, ?, ?)
                                ON CONFLICT(role_id, permission_code) DO UPDATE SET access_level = excluded.access_level
                                """,
                                (role_id, row["permission_code"], row["access_level"]),
                            )
                        conn.commit()
                    audit("Permission changed", "role_permissions", role_id, "Role permission matrix updated")
                    st.success("Role permissions saved.")
                    st.rerun()
            else:
                st.dataframe(perms, use_container_width=True, hide_index=True)
    with tabs[3]:
        users = read_df("SELECT id, username, full_name FROM users ORDER BY username")
        perms = read_df("SELECT permission_code, permission_name FROM permissions ORDER BY module_name, permission_name")
        if not users.empty and not perms.empty:
            user_label = st.selectbox("User", [f"{r.id} - {r.username}" for r in users.itertuples()], key="user_override_user")
            user_id = int(user_label.split(" - ")[0])
            current = read_df(
                "SELECT id, permission_code, access_level, override_type FROM user_permissions WHERE user_id = ? ORDER BY permission_code",
                (user_id,),
            )
            st.dataframe(current, use_container_width=True, hide_index=True)
            if can_manage:
                with st.form("user_override_form"):
                    perm = st.selectbox("Permission", perms["permission_code"].tolist())
                    access = st.selectbox("Access Level", ACCESS_LEVELS)
                    override_type = st.selectbox("Override Type", ["Allow", "Deny"])
                    submit = st.form_submit_button("Save Override", type="primary")
                if submit:
                    run_sql(
                        """
                        INSERT INTO user_permissions (user_id, permission_code, access_level, override_type)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id, permission_code) DO UPDATE SET access_level = excluded.access_level,
                            override_type = excluded.override_type
                        """,
                        (user_id, perm, access, override_type),
                    )
                    audit("Permission changed", "user_permissions", user_id, f"{perm}={access}/{override_type}")
                    st.success("Override saved.")
                    st.rerun()
    with tabs[4]:
        users = read_df("SELECT id, username FROM users ORDER BY username")
        projects = list(project_lookup(active_only=False).keys())
        if not users.empty:
            user_label = st.selectbox("User", [f"{r.id} - {r.username}" for r in users.itertuples()], key="proj_access_user")
            user_id = int(user_label.split(" - ")[0])
            current = read_df("SELECT * FROM user_project_access WHERE user_id = ?", (user_id,))
            st.dataframe(current, use_container_width=True, hide_index=True)
            if can_manage:
                access_type = st.radio("Project Access", ["All", "Selected"], horizontal=True)
                selected_projects = st.multiselect("Selected Projects", projects, disabled=access_type == "All")
                if st.button("Save Project Access", type="primary"):
                    with db() as conn:
                        conn.execute("DELETE FROM user_project_access WHERE user_id = ?", (user_id,))
                        if access_type == "All":
                            conn.execute("INSERT INTO user_project_access (user_id, project, access_type) VALUES (?, 'All Projects', 'All')", (user_id,))
                        else:
                            for project in selected_projects:
                                conn.execute("INSERT INTO user_project_access (user_id, project, access_type) VALUES (?, ?, 'Selected')", (user_id, project))
                        conn.commit()
                    audit("Permission changed", "user_project_access", user_id, access_type)
                    st.success("Project access saved.")
                    st.rerun()
    with tabs[5]:
        users = read_df("SELECT id, username FROM users ORDER BY username")
        departments = option_rows("departments", "department")
        if not users.empty:
            user_label = st.selectbox("User", [f"{r.id} - {r.username}" for r in users.itertuples()], key="dept_access_user")
            user_id = int(user_label.split(" - ")[0])
            current = read_df("SELECT * FROM user_department_access WHERE user_id = ?", (user_id,))
            st.dataframe(current, use_container_width=True, hide_index=True)
            if can_manage:
                access_type = st.radio("Department Access", ["All", "Selected"], horizontal=True)
                selected_departments = st.multiselect("Selected Departments", departments, disabled=access_type == "All")
                if st.button("Save Department Access", type="primary"):
                    with db() as conn:
                        conn.execute("DELETE FROM user_department_access WHERE user_id = ?", (user_id,))
                        if access_type == "All":
                            conn.execute("INSERT INTO user_department_access (user_id, department, access_type) VALUES (?, 'All Departments', 'All')", (user_id,))
                        else:
                            for department in selected_departments:
                                conn.execute("INSERT INTO user_department_access (user_id, department, access_type) VALUES (?, ?, 'Selected')", (user_id, department))
                        conn.commit()
                    audit("Permission changed", "user_department_access", user_id, access_type)
                    st.success("Department access saved.")
                    st.rerun()
    with tabs[6]:
        approvals = read_df("SELECT * FROM approval_requests ORDER BY requested_at DESC")
        st.dataframe(approvals, use_container_width=True, hide_index=True)
        if can_manage or has_action("Can Approve Bonus") or has_action("Can Close Payroll Run"):
            if not approvals.empty:
                request_id = st.selectbox("Approval Request ID", approvals["id"].tolist())
                comments = st.text_area("Comments", key="approval_request_comments")
                c1, c2, c3 = st.columns(3)
                if c1.button("Approve Request"):
                    req = fetch_one("SELECT * FROM approval_requests WHERE id = ?", (int(request_id),))
                    approve_record(req["request_type"], req["record_id"], comments)
                    audit("Approval action", "approval_requests", request_id, "Approved")
                    st.success("Request approved.")
                    st.rerun()
                if c2.button("Reject Request"):
                    req = fetch_one("SELECT * FROM approval_requests WHERE id = ?", (int(request_id),))
                    reject_record(req["request_type"], req["record_id"], comments)
                    audit("Approval action", "approval_requests", request_id, "Rejected")
                    st.success("Request rejected.")
                    st.rerun()
                if c3.button("Return for Edit"):
                    run_sql("UPDATE approval_requests SET status = 'Returned', rejection_reason = ? WHERE id = ?", (comments, int(request_id)))
                    audit("Approval action", "approval_requests", request_id, "Returned")
                    st.success("Request returned.")
                    st.rerun()
        history = read_df("SELECT * FROM approval_history ORDER BY action_at DESC")
        st.subheader("Approval History")
        st.dataframe(history, use_container_width=True, hide_index=True)
    with tabs[7]:
        sessions = read_df("SELECT * FROM user_sessions ORDER BY login_time DESC")
        st.dataframe(sessions, use_container_width=True, hide_index=True)
        security_log = read_df(
            """
            SELECT * FROM audit_log
            WHERE action IN ('Login success', 'Login failed', 'Password changed', 'User created', 'User updated', 'Permission changed', 'Role changed')
            ORDER BY audit_id DESC
            """
        )
        st.subheader("Security Audit")
        st.dataframe(security_log, use_container_width=True, hide_index=True)
        st.subheader("Change My Password")
        with st.form("change_password"):
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm = st.text_input("Confirm New Password", type="password")
            submit = st.form_submit_button("Change Password", type="primary")
        if submit:
            user = current_user_row()
            if not user or user["password_hash"] != hash_password(old_password):
                st.error("Current password is incorrect.")
            elif new_password != confirm or not new_password:
                st.error("New passwords do not match.")
            else:
                run_sql("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (hash_password(new_password), now_text(), user["id"]))
                audit("Password changed", "users", user["username"], "User changed own password")
                st.success("Password changed.")


def salary_revision_history_page() -> None:
    page_header("Salary Revision History", "Track salary increments, preview cost impact, approve and apply revisions.")
    employees = employee_options(active_only=True)
    df = read_df(
        """
        SELECT r.revision_id, r.employee_code, e.arabic_name, e.department, e.section, p.project_name AS project,
               r.old_basic_salary, r.new_basic_salary, r.old_net_salary, r.new_net_salary, r.old_allowance,
               r.new_allowance, r.old_net_earning, r.new_net_earning, r.old_gross_salary, r.new_gross_salary,
               r.gross_difference, r.net_difference, r.company_cost_before, r.company_cost_after,
               r.company_cost_difference, r.effective_from, r.effective_to, r.revision_type, r.reason,
               r.approval_status, r.approved_by, r.approved_date, r.applied, r.created_by, r.created_at, r.notes
        FROM salary_revisions r
        JOIN employees e ON e.employee_code = r.employee_code
        LEFT JOIN projects p ON p.project_id = e.default_project_id
        ORDER BY r.created_at DESC
        """
    )
    df = restrict_df_by_access(df, "project", "department")
    st.dataframe(mask_salary_columns(df), use_container_width=True, hide_index=True)
    protected_download_button("Export Salary Revision Report", df, "salary_revision_history.xlsx")
    tab_add, tab_apply = st.tabs(["Add Revision", "Approve / Apply"])
    with tab_add:
        if require_write("Salary Revision History", "Can Edit Employee"):
            with st.form("salary_revision_form"):
                employee_label = st.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
                employee_code = employee_label.split(" - ")[0]
                employee = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
                c1, c2, c3 = st.columns(3)
                new_basic = c1.number_input("New Basic Salary", value=float(employee["basic_salary"]), min_value=0.0)
                new_net = c2.number_input("New Net Salary", value=float(employee["new_net_salary"]), min_value=0.0)
                new_allowance = c3.number_input("New Allowance", value=float(employee["new_allowance"]), min_value=0.0)
                c4, c5, c6 = st.columns(3)
                effective_from = c4.date_input("Effective From", value=date.today())
                effective_to = c5.date_input("Effective To", value=None)
                revision_type = c6.selectbox("Revision Type", ["Annual Increase", "Promotion", "Market Adjustment", "Correction", "Contract Change", "Other"])
                reason = st.text_area("Reason")
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Preview and Save Revision", type="primary")
            if submit:
                old_calc = gross_up_for_net(float(employee["new_net_earning"]), employee, effective_from.year)
                proposed = dict(employee)
                proposed["basic_salary"] = new_basic
                proposed["new_net_salary"] = new_net
                proposed["new_allowance"] = new_allowance
                proposed["new_net_earning"] = new_net + new_allowance
                new_calc = gross_up_for_net(new_net + new_allowance, proposed, effective_from.year)
                run_sql(
                    """
                    INSERT INTO salary_revisions
                    (employee_code, old_basic_salary, new_basic_salary, old_net_salary, new_net_salary,
                     old_allowance, new_allowance, old_net_earning, new_net_earning, old_gross_salary,
                     new_gross_salary, gross_difference, net_difference, company_cost_before, company_cost_after,
                     company_cost_difference, effective_from, effective_to, revision_type, reason, approval_status,
                     created_by, created_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?, ?)
                    """,
                    (
                        employee_code,
                        employee["basic_salary"],
                        new_basic,
                        employee["new_net_salary"],
                        new_net,
                        employee["new_allowance"],
                        new_allowance,
                        employee["new_net_earning"],
                        new_net + new_allowance,
                        old_calc["gross"],
                        new_calc["gross"],
                        new_calc["gross"] - old_calc["gross"],
                        (new_net + new_allowance) - employee["new_net_earning"],
                        old_calc["total_company_cost"],
                        new_calc["total_company_cost"],
                        new_calc["total_company_cost"] - old_calc["total_company_cost"],
                        effective_from.isoformat(),
                        clean_date(effective_to),
                        revision_type,
                        reason,
                        st.session_state.get("username"),
                        now_text(),
                        notes,
                    ),
                )
                audit("Salary revision created", "salary_revisions", employee_code, reason)
                st.success("Salary revision saved with cost impact.")
                st.rerun()
    with tab_apply:
        if not df.empty:
            revision_id = st.selectbox("Revision ID", df["revision_id"].tolist())
            c1, c2, c3 = st.columns(3)
            if c1.button("Submit for Approval"):
                run_sql("UPDATE salary_revisions SET approval_status = 'Submitted' WHERE revision_id = ?", (int(revision_id),))
                create_approval_request("Salary Revision", int(revision_id), "Salary revision submitted")
                st.success("Submitted.")
                st.rerun()
            if c2.button("Approve Revision"):
                if has_action("Can Edit Employee"):
                    run_sql("UPDATE salary_revisions SET approval_status = 'Approved', approved_by = ?, approved_date = ? WHERE revision_id = ?", (st.session_state.get("username"), now_text(), int(revision_id)))
                    approve_record("Salary Revision", int(revision_id), "Approved")
                    st.success("Approved.")
                    st.rerun()
            if c3.button("Apply to Employee Master"):
                revision = fetch_one("SELECT * FROM salary_revisions WHERE revision_id = ?", (int(revision_id),))
                if revision and revision["approval_status"] == "Approved":
                    run_sql(
                        """
                        UPDATE employees
                        SET basic_salary = ?, new_net_salary = ?, new_allowance = ?, new_net_earning = ?,
                            net_salary = ?, updated_at = ?
                        WHERE employee_code = ?
                        """,
                        (revision["new_basic_salary"], revision["new_net_salary"], revision["new_allowance"], revision["new_net_earning"], revision["new_net_salary"], now_text(), revision["employee_code"]),
                    )
                    run_sql("UPDATE salary_revisions SET applied = 1 WHERE revision_id = ?", (int(revision_id),))
                    audit("Salary revision applied", "employees", revision["employee_code"], f"Revision {revision_id}")
                    st.success("Revision applied to employee master data.")
                    st.rerun()
                else:
                    st.error("Only approved revisions can be applied.")


def payroll_approvals_locking_page() -> None:
    page_header("Payroll Approvals & Locking", "Control payroll approval workflow, month locks, close/reopen, and approval history.")
    runs = read_df(
        """
        SELECT r.run_id, r.year, r.month, p.project_name, r.department, r.status, r.approval_status,
               r.generated_at, r.generated_by, r.submitted_by, r.submitted_at, r.hr_reviewed_by,
               r.finance_reviewed_by, r.approved_by, r.approved_at, r.closed_at, r.approval_comments
        FROM payroll_runs r
        LEFT JOIN projects p ON p.project_id = r.project_id
        ORDER BY r.year DESC, r.month DESC, r.run_id DESC
        """
    )
    st.dataframe(runs, use_container_width=True, hide_index=True)
    locks = read_df("SELECT * FROM payroll_locks ORDER BY year DESC, month DESC")
    st.subheader("Payroll Locks")
    st.dataframe(locks, use_container_width=True, hide_index=True)
    c1, c2, c3, c4 = st.columns(4)
    year = c1.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    month = c2.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
    status = c3.selectbox("Lock Status", LOCK_STATUSES)
    reason = c4.text_input("Reopen / Lock Reason")
    if st.button("Save Month Lock", type="primary"):
        if status == "Open" and not is_admin():
            st.error("Only Admin or Super Admin can reopen a payroll month.")
        else:
            run_sql(
                """
                INSERT INTO payroll_locks (year, month, lock_status, locked_by, locked_at, closed_by, closed_at, reopened_by, reopened_at, reopen_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(year, month) DO UPDATE SET
                    lock_status = excluded.lock_status,
                    locked_by = CASE WHEN excluded.lock_status = 'Locked' THEN excluded.locked_by ELSE locked_by END,
                    locked_at = CASE WHEN excluded.lock_status = 'Locked' THEN excluded.locked_at ELSE locked_at END,
                    closed_by = CASE WHEN excluded.lock_status = 'Closed' THEN excluded.closed_by ELSE closed_by END,
                    closed_at = CASE WHEN excluded.lock_status = 'Closed' THEN excluded.closed_at ELSE closed_at END,
                    reopened_by = CASE WHEN excluded.lock_status = 'Open' THEN excluded.reopened_by ELSE reopened_by END,
                    reopened_at = CASE WHEN excluded.lock_status = 'Open' THEN excluded.reopened_at ELSE reopened_at END,
                    reopen_reason = excluded.reopen_reason
                """,
                (
                    int(year),
                    int(month),
                    status,
                    st.session_state.get("username") if status == "Locked" else None,
                    now_text() if status == "Locked" else None,
                    st.session_state.get("username") if status == "Closed" else None,
                    now_text() if status == "Closed" else None,
                    st.session_state.get("username") if status == "Open" else None,
                    now_text() if status == "Open" else None,
                    reason,
                ),
            )
            audit("Payroll lock change", "payroll_locks", f"{year}-{month}", f"{status}: {reason}")
            st.success("Lock status saved.")
            st.rerun()
    if not runs.empty:
        run_id = st.selectbox("Payroll Run ID", runs["run_id"].tolist())
        comments = st.text_area("Approval Comments")
        cols = st.columns(6)
        actions = [
            ("Submit", "Submitted"),
            ("HR Reviewed", "HR Reviewed"),
            ("Finance Reviewed", "Finance Reviewed"),
            ("Final Approval", "Approved"),
            ("Reject", "Cancelled"),
            ("Return for Edit", "Draft"),
        ]
        for col, (label, new_status) in zip(cols, actions):
            if col.button(label):
                run_sql("UPDATE payroll_runs SET approval_status = ?, approval_comments = ?, updated_at = ? WHERE run_id = ?", (new_status, comments, now_text(), int(run_id)))
                if label == "Submit":
                    create_approval_request("Payroll Run", int(run_id), comments)
                if new_status == "Approved":
                    approve_record("Payroll Run", int(run_id), comments)
                audit("Payroll approval", "payroll_runs", run_id, new_status)
                st.success(f"Payroll run marked {new_status}.")
                st.rerun()
    st.subheader("Approval History")
    st.dataframe(read_df("SELECT * FROM approval_history ORDER BY action_at DESC"), use_container_width=True, hide_index=True)


def payroll_variance_report_page() -> None:
    page_header("Payroll Variance Report", "Compare current month payroll with previous month and highlight major changes.")
    c1, c2, c3, c4 = st.columns(4)
    year = c1.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    month = c2.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
    project = c3.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))
    department = c4.selectbox("Department", ["All"] + option_rows("departments", "department"))
    prev_year, prev_month = (int(year) - 1, 12) if int(month) == 1 else (int(year), int(month) - 1)
    current = payroll_transactions_df(int(year), int(month))
    previous = payroll_transactions_df(prev_year, prev_month)
    if current.empty and previous.empty:
        st.info("Generate payroll for current and previous months to see variance.")
        return
    key_cols = ["employee_code", "arabic_name", "department", "section", "default_project", "sponsor"]
    current_small = current[key_cols + ["base_net_salary", "total_allowances", "estimated_gross", "monthly_tax", "employee_insurance", "company_insurance", "total_company_cost"]].copy() if not current.empty else pd.DataFrame(columns=key_cols)
    previous_small = previous[key_cols + ["base_net_salary", "total_allowances", "estimated_gross", "monthly_tax", "employee_insurance", "company_insurance", "total_company_cost"]].copy() if not previous.empty else pd.DataFrame(columns=key_cols)
    merged = current_small.merge(previous_small, on="employee_code", how="outer", suffixes=("_current", "_previous"))
    rows = []
    for _, row in merged.iterrows():
        emp_code = row["employee_code"]
        name = row.get("arabic_name_current") or row.get("arabic_name_previous")
        dept = row.get("department_current") or row.get("department_previous")
        sec = row.get("section_current") or row.get("section_previous")
        proj = row.get("default_project_current") or row.get("default_project_previous")
        sponsor = row.get("sponsor_current") or row.get("sponsor_previous")
        curr_bonus = safe_float(fetch_one("SELECT SUM(net_bonus_amount) AS s FROM employee_bonuses WHERE employee_code = ? AND year = ? AND month = ?", (emp_code, int(year), int(month)))["s"])
        prev_bonus = safe_float(fetch_one("SELECT SUM(net_bonus_amount) AS s FROM employee_bonuses WHERE employee_code = ? AND year = ? AND month = ?", (emp_code, prev_year, prev_month))["s"])
        company_diff = safe_float(row.get("total_company_cost_current")) - safe_float(row.get("total_company_cost_previous"))
        reason = "Other"
        if pd.isna(row.get("total_company_cost_previous")):
            reason = "New Joiner"
        elif pd.isna(row.get("total_company_cost_current")):
            reason = "Leaver"
        elif curr_bonus - prev_bonus != 0:
            reason = "Bonus"
        elif safe_float(row.get("total_allowances_current")) - safe_float(row.get("total_allowances_previous")) != 0:
            reason = "New Allowance" if safe_float(row.get("total_allowances_current")) > safe_float(row.get("total_allowances_previous")) else "Removed Allowance"
        elif safe_float(row.get("base_net_salary_current")) - safe_float(row.get("base_net_salary_previous")) != 0:
            reason = "Salary Increase"
        rows.append(
            {
                "Employee Code": emp_code,
                "Arabic Name": name,
                "Department": dept,
                "Section": sec,
                "Project": proj,
                "Sponsor": sponsor,
                "Previous Month Net Salary": safe_float(row.get("base_net_salary_previous")),
                "Current Month Net Salary": safe_float(row.get("base_net_salary_current")),
                "Net Difference": safe_float(row.get("base_net_salary_current")) - safe_float(row.get("base_net_salary_previous")),
                "Previous Month Allowances": safe_float(row.get("total_allowances_previous")),
                "Current Month Allowances": safe_float(row.get("total_allowances_current")),
                "Allowance Difference": safe_float(row.get("total_allowances_current")) - safe_float(row.get("total_allowances_previous")),
                "Previous Month Bonus": prev_bonus,
                "Current Month Bonus": curr_bonus,
                "Bonus Difference": curr_bonus - prev_bonus,
                "Previous Month Gross": safe_float(row.get("estimated_gross_previous")),
                "Current Month Gross": safe_float(row.get("estimated_gross_current")),
                "Gross Difference": safe_float(row.get("estimated_gross_current")) - safe_float(row.get("estimated_gross_previous")),
                "Previous Month Tax": safe_float(row.get("monthly_tax_previous")),
                "Current Month Tax": safe_float(row.get("monthly_tax_current")),
                "Tax Difference": safe_float(row.get("monthly_tax_current")) - safe_float(row.get("monthly_tax_previous")),
                "Previous Month Insurance": safe_float(row.get("employee_insurance_previous")) + safe_float(row.get("company_insurance_previous")),
                "Current Month Insurance": safe_float(row.get("employee_insurance_current")) + safe_float(row.get("company_insurance_current")),
                "Insurance Difference": safe_float(row.get("employee_insurance_current")) + safe_float(row.get("company_insurance_current")) - safe_float(row.get("employee_insurance_previous")) - safe_float(row.get("company_insurance_previous")),
                "Previous Month Company Cost": safe_float(row.get("total_company_cost_previous")),
                "Current Month Company Cost": safe_float(row.get("total_company_cost_current")),
                "Company Cost Difference": company_diff,
                "Variance Reason": reason,
            }
        )
    report = pd.DataFrame(rows)
    if project != "All":
        report = report[report["Project"] == project]
    if department != "All":
        report = report[report["Department"] == department]
    report = restrict_df_by_access(report, "Project", "Department")
    kpi_cards([
        ("Total Payroll Increase", money(report.loc[report["Company Cost Difference"] > 0, "Company Cost Difference"].sum() if not report.empty else 0)),
        ("Total Payroll Decrease", money(abs(report.loc[report["Company Cost Difference"] < 0, "Company Cost Difference"].sum()) if not report.empty else 0)),
        ("Total Bonus Variance", money(report["Bonus Difference"].sum() if not report.empty else 0)),
        ("Total Allowance Variance", money(report["Allowance Difference"].sum() if not report.empty else 0)),
        ("Company Cost Variance", money(report["Company Cost Difference"].sum() if not report.empty else 0)),
    ])
    st.dataframe(mask_salary_columns(report), use_container_width=True, hide_index=True)
    protected_download_button("Export Payroll Variance", report, "payroll_variance.xlsx")


def bank_transfer_page() -> None:
    page_header("Bank Transfer File", "Prepare monthly payroll bank transfers, validate bank data, export file, and mark paid.")
    c1, c2, c3, c4 = st.columns(4)
    year = c1.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    month = c2.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
    project = c3.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))
    department = c4.selectbox("Department", ["All"] + option_rows("departments", "department"))
    tx = payroll_transactions_df(int(year), int(month))
    if project != "All":
        tx = tx[tx["default_project"] == project]
    if department != "All":
        tx = tx[tx["department"] == department]
    tx = restrict_df_by_access(tx, "default_project", "department")
    bank = read_df("SELECT employee_code, english_name, bank_name, bank_branch, bank_account_iban FROM employees")
    file_df = tx.merge(bank, on="employee_code", how="left")
    file_df = file_df[file_df["payment_status"].isin(["Pending", "Transferred"])]
    cols = ["employee_code", "arabic_name", "english_name", "bank_name", "bank_branch", "bank_account_iban", "net_transfer_amount", "month", "year", "transfer_date", "transfer_reference", "payment_status", "notes"]
    file_df = file_df[[c for c in cols if c in file_df.columns]]
    missing = file_df[file_df["bank_account_iban"].isna() | (file_df["bank_account_iban"].astype(str) == "")]
    if not missing.empty:
        st.warning(f"{len(missing)} employees are missing bank account / IBAN.")
    st.dataframe(mask_salary_columns(file_df), use_container_width=True, hide_index=True)
    protected_download_button("Export Bank Transfer File", file_df, f"bank_transfer_{year}_{int(month):02d}.xlsx")
    if require_write("Bank Transfer", "Can Mark Payroll as Transferred"):
        selected = st.multiselect("Employees to mark transferred", file_df["employee_code"].tolist() if not file_df.empty else [])
        reference = st.text_input("Transfer Reference", value=f"TRF-{int(year)}{int(month):02d}")
        transfer_date = st.date_input("Transfer Date", value=date.today())
        if st.button("Mark Selected as Transferred", type="primary") and selected:
            if not require_month_open(int(year), int(month)):
                return
            placeholders = ",".join(["?"] * len(selected))
            with db() as conn:
                conn.execute(
                    f"UPDATE payroll_transactions SET payment_status = 'Transferred', transfer_date = ?, transfer_reference = ?, updated_at = ? WHERE year = ? AND month = ? AND employee_code IN ({placeholders})",
                    tuple([transfer_date.isoformat(), reference, now_text(), int(year), int(month)] + selected),
                )
                conn.commit()
            audit("Payroll transfer status change", "payroll_transactions", reference, f"Employees={len(selected)}")
            st.success("Selected transfers marked.")
            st.rerun()


def bank_reconciliation_page() -> None:
    page_header("Payroll Bank Reconciliation", "Compare payroll calculated transfers with actual bank payment confirmation amounts.")
    uploaded = st.file_uploader("Import bank confirmation CSV/XLSX", type=["csv", "xlsx"])
    if uploaded and require_write("Bank Reconciliation", "Can Import Data"):
        bank_df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        st.dataframe(bank_df.head(100), use_container_width=True, hide_index=True)
        if st.button("Import Reconciliation", type="primary"):
            rows = []
            for _, row in bank_df.iterrows():
                employee_code = str(row.get("employee_code", row.get("Employee Code", "")))
                reference = str(row.get("transfer_reference", row.get("Bank Reference", "")))
                actual = safe_float(row.get("actual_bank_transfer_amount", row.get("Actual Bank Transfer Amount", 0)))
                payroll = fetch_one("SELECT net_transfer_amount, transfer_date FROM payroll_transactions WHERE employee_code = ? AND transfer_reference = ? ORDER BY year DESC, month DESC LIMIT 1", (employee_code, reference))
                payroll_amount = safe_float(payroll["net_transfer_amount"] if payroll else 0)
                diff = actual - payroll_amount
                status = "Matched" if abs(diff) < 0.01 else ("Overpaid" if diff > 0 else "Underpaid")
                if not payroll:
                    status = "Not Transferred"
                rows.append((employee_code, row.get("bank_account_iban", ""), reference, payroll_amount, actual, diff, clean_date(row.get("transfer_date")) or date.today().isoformat(), reference, status, row.get("notes", ""), now_text()))
            with db() as conn:
                conn.executemany(
                    """
                    INSERT INTO bank_reconciliation
                    (employee_code, bank_account_iban, transfer_reference, payroll_net_transfer_amount,
                     actual_bank_transfer_amount, difference, transfer_date, bank_reference, status, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
            audit("Import action", "bank_reconciliation", uploaded.name, f"Imported {len(rows)} rows")
            st.success("Reconciliation imported.")
            st.rerun()
    df = read_df("SELECT * FROM bank_reconciliation ORDER BY created_at DESC")
    st.dataframe(mask_salary_columns(df), use_container_width=True, hide_index=True)
    protected_download_button("Export Reconciliation Report", df, "bank_reconciliation.xlsx")


def employee_cost_sheet_page() -> None:
    page_header("Employee Cost Sheet", "Monthly and yearly employee cost including salary, allowances, bonus, tax, insurance and allocation.")
    employees = employee_options(active_only=False)
    c1, c2, c3 = st.columns(3)
    employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
    year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    month = c3.selectbox("Month", ["All"] + list(MONTHS.keys()), format_func=lambda x: MONTHS[x] if isinstance(x, int) else x)
    employee_code = employee_label.split(" - ")[0]
    payroll = payroll_transactions_df(int(year), None if month == "All" else int(month), employee_code)
    bonuses = bonus_register_df(year=int(year), month=month, employee_code=employee_code)
    allocations = payroll_project_allocations_df(int(year), None if month == "All" else int(month))
    allocations = allocations[allocations["employee_code"] == employee_code] if not allocations.empty else allocations
    total = payroll["total_company_cost"].sum() if not payroll.empty else 0
    bonus_total = bonuses["company_cost_difference"].sum() if not bonuses.empty else 0
    kpi_cards([
        ("Monthly Cost", money(total if month != "All" else payroll.loc[payroll["month"] == date.today().month, "total_company_cost"].sum() if not payroll.empty else 0)),
        ("Yearly Payroll Cost", money(total)),
        ("Bonus Cost", money(bonus_total)),
        ("Net Transfer", money(payroll["net_transfer_amount"].sum() if not payroll.empty else 0)),
    ])
    t1, t2, t3 = st.tabs(["Cost Sheet", "Bonus Details", "Project Allocation"])
    with t1:
        st.dataframe(mask_salary_columns(payroll), use_container_width=True, hide_index=True)
    with t2:
        st.dataframe(mask_salary_columns(bonuses), use_container_width=True, hide_index=True)
    with t3:
        st.dataframe(mask_salary_columns(allocations), use_container_width=True, hide_index=True)
    protected_download_button("Export Employee Cost Sheet", pd.concat({"Payroll": payroll}, names=["Source"]).reset_index(level=0), f"employee_cost_sheet_{employee_code}.xlsx")


def project_payroll_cost_dashboard_page() -> None:
    page_header("Project Payroll Cost Dashboard", "Analyze allocated salary, allowances, bonus, tax, insurance, headcount and project payroll cost.")
    c1, c2 = st.columns(2)
    year = c1.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    project = c2.selectbox("Project", ["All"] + list(project_lookup(active_only=False).keys()))
    alloc = payroll_project_allocations_df(int(year), None)
    bonus_alloc = read_df("SELECT project, year, month, SUM(allocated_company_cost_difference) AS allocated_bonus FROM bonus_project_allocations WHERE year = ? GROUP BY project, year, month", (int(year),))
    if project != "All":
        alloc = alloc[alloc["project"] == project]
        bonus_alloc = bonus_alloc[bonus_alloc["project"] == project]
    alloc = restrict_df_by_access(alloc, "project", None)
    summary = alloc.groupby(["project", "year", "month"], as_index=False).agg(
        **{
            "Allocated Net Salary": ("allocated_net_salary", "sum"),
            "Allocated Allowances": ("allocated_allowances", "sum"),
            "Allocated Gross": ("allocated_gross", "sum"),
            "Allocated Tax": ("allocated_tax", "sum"),
            "Allocated Employee Insurance": ("allocated_employee_insurance", "sum"),
            "Allocated Company Insurance": ("allocated_company_insurance", "sum"),
            "Total Allocated Company Cost": ("allocated_total_company_cost", "sum"),
            "Headcount": ("employee_code", "nunique"),
            "FTE / Allocation Headcount": ("allocation_percentage", lambda s: s.sum() / 100),
        }
    ) if not alloc.empty else pd.DataFrame()
    if not summary.empty and not bonus_alloc.empty:
        summary = summary.merge(bonus_alloc.rename(columns={"project": "project"}), on=["project", "year", "month"], how="left")
        summary["Allocated Bonus"] = summary["allocated_bonus"].fillna(0)
        summary["Total Allocated Company Cost"] += summary["Allocated Bonus"]
        summary = summary.drop(columns=["allocated_bonus"])
    elif not summary.empty:
        summary["Allocated Bonus"] = 0
    kpi_cards([
        ("Projects", f"{summary['project'].nunique() if not summary.empty else 0:,}"),
        ("Total Project Payroll Cost", money(summary["Total Allocated Company Cost"].sum() if not summary.empty else 0)),
        ("Allocated Bonus", money(summary["Allocated Bonus"].sum() if not summary.empty else 0)),
        ("FTE", f"{summary['FTE / Allocation Headcount'].sum() if not summary.empty else 0:,.2f}"),
    ])
    st.dataframe(mask_salary_columns(summary), use_container_width=True, hide_index=True)
    if not summary.empty:
        st.subheader("Top Costly Projects")
        st.bar_chart(summary.groupby("project", as_index=False)["Total Allocated Company Cost"].sum(), x="project", y="Total Allocated Company Cost")
    protected_download_button("Export Project Payroll Cost", summary, "project_payroll_cost.xlsx")


def alerts_center_page() -> None:
    page_header("Alerts Center", "Operational payroll alerts, severity, assignment and resolution tracking.")
    if st.button("Refresh System Alerts"):
        generated = []
        quality = []
        for row in data_quality_alert_rows():
            generated.append((row["alert_type"], row["severity"], row["message"], row["module_name"], row["record_id"], "Open", None, now_text()))
        with db() as conn:
            conn.executemany(
                """
                INSERT INTO alerts (alert_type, severity, message, module_name, record_id, status, assigned_to, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                generated,
            )
            conn.commit()
        st.success(f"{len(generated)} alerts generated.")
        st.rerun()
    df = read_df("SELECT * FROM alerts ORDER BY CASE severity WHEN 'Critical' THEN 1 WHEN 'Warning' THEN 2 ELSE 3 END, created_at DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty and require_write("Alerts Center"):
        alert_id = st.selectbox("Alert ID", df["id"].tolist())
        assign_to = st.text_input("Assign To")
        c1, c2 = st.columns(2)
        if c1.button("Assign Alert"):
            run_sql("UPDATE alerts SET assigned_to = ? WHERE id = ?", (assign_to, int(alert_id)))
            st.success("Assigned.")
            st.rerun()
        if c2.button("Mark Resolved"):
            run_sql("UPDATE alerts SET status = 'Resolved', resolved_by = ?, resolved_at = ? WHERE id = ?", (st.session_state.get("username"), now_text(), int(alert_id)))
            st.success("Resolved.")
            st.rerun()
    protected_download_button("Export Alerts", df, "alerts.xlsx")


def data_quality_alert_rows() -> list[dict]:
    rows = []
    emp_missing_project = read_df("SELECT employee_code FROM employees WHERE status = 'Active' AND default_project_id IS NULL")
    for row in emp_missing_project.itertuples():
        rows.append({"alert_type": "Employee without project", "severity": "Critical", "message": f"Employee {row.employee_code} has no project.", "module_name": "Employees", "record_id": row.employee_code})
    missing_bank = read_df("SELECT employee_code FROM employees WHERE status = 'Active' AND (bank_account_iban IS NULL OR bank_account_iban = '')")
    for row in missing_bank.itertuples():
        rows.append({"alert_type": "Employee without bank account", "severity": "Warning", "message": f"Employee {row.employee_code} has no bank account.", "module_name": "Bank Transfer", "record_id": row.employee_code})
    invalid_alloc = allocation_validation_df()
    for row in invalid_alloc[invalid_alloc["status"] == "Invalid"].itertuples():
        rows.append({"alert_type": "Invalid project allocation", "severity": "Critical", "message": f"{row.employee_code}: {row.issue}", "module_name": "Employee Project Allocation", "record_id": row.employee_code})
    return rows


def employee_documents_page() -> None:
    page_header("Employee Documents", "Track employee documents, missing items, expiry dates, and document alerts.")
    employees = employee_options(active_only=False)
    df = read_df(
        """
        SELECT d.document_id, d.employee_code, e.arabic_name, d.document_type, d.file_name, d.upload_date,
               d.expiry_date, d.uploaded_by, d.status, d.notes, d.created_at
        FROM employee_documents d
        JOIN employees e ON e.employee_code = d.employee_code
        ORDER BY d.created_at DESC
        """
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.form("document_form"):
        c1, c2, c3 = st.columns(3)
        employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
        doc_type = c2.selectbox("Document Type", ["Contract", "National ID", "Insurance Form", "Work Permit", "Bank Letter", "Medical Certificate", "Other"])
        file_name = c3.text_input("File Name")
        c4, c5, c6 = st.columns(3)
        upload_date = c4.date_input("Upload Date", value=date.today())
        expiry_date = c5.date_input("Expiry Date", value=None)
        status = c6.selectbox("Status", ["Valid", "Expired", "Missing"])
        notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Document", type="primary")
    if submit and require_write("Employee Documents"):
        run_sql(
            """
            INSERT INTO employee_documents (employee_code, document_type, file_name, upload_date, expiry_date, uploaded_by, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_label.split(" - ")[0], doc_type, file_name, upload_date.isoformat(), clean_date(expiry_date), st.session_state.get("username"), status, notes, now_text()),
        )
        audit("Document saved", "employee_documents", employee_label.split(" - ")[0], doc_type)
        st.success("Document saved.")
        st.rerun()
    protected_download_button("Export Documents", df, "employee_documents.xlsx")


def attendance_adjustments_page() -> None:
    page_header("Attendance Adjustments", "Record unpaid days, absences and approved payroll deductions.")
    employees = employee_options(active_only=True)
    df = read_df(
        """
        SELECT a.*, e.arabic_name, e.department, e.section
        FROM attendance_adjustments a
        JOIN employees e ON e.employee_code = a.employee_code
        ORDER BY a.year DESC, a.month DESC, a.created_at DESC
        """
    )
    df = restrict_df_by_access(df, None, "department")
    st.dataframe(mask_salary_columns(df), use_container_width=True, hide_index=True)
    with st.form("attendance_form"):
        c1, c2, c3 = st.columns(3)
        employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
        year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
        month = c3.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
        c4, c5, c6, c7 = st.columns(4)
        working_days = c4.number_input("Working Days", min_value=0.0, value=30.0)
        unpaid_days = c5.number_input("Unpaid Leave Days", min_value=0.0, value=0.0)
        absence_days = c6.number_input("Absence Days", min_value=0.0, value=0.0)
        approval_status = c7.selectbox("Approval Status", APPROVAL_STATUSES)
        reason = st.text_area("Reason")
        notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Attendance Adjustment", type="primary")
    if submit and require_write("Attendance Adjustments"):
        if not require_month_open(int(year), int(month)):
            return
        employee_code = employee_label.split(" - ")[0]
        emp = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (employee_code,))
        daily_rate = safe_float(emp["new_net_salary"]) / working_days if working_days else 0
        deduction_days = unpaid_days + absence_days
        deduction_amount = daily_rate * deduction_days
        run_sql(
            """
            INSERT INTO attendance_adjustments
            (employee_code, year, month, working_days, paid_days, unpaid_leave_days, absence_days,
             deduction_days, daily_rate, deduction_amount, reason, approval_status, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_code, int(year), int(month), working_days, working_days - deduction_days, unpaid_days, absence_days, deduction_days, daily_rate, deduction_amount, reason, approval_status, notes, st.session_state.get("username"), now_text()),
        )
        st.success("Attendance adjustment saved.")
        st.rerun()
    protected_download_button("Export Attendance Adjustments", df, "attendance_adjustments.xlsx")


def overtime_page() -> None:
    page_header("Overtime", "Record, approve and include overtime in payroll by employee/project/month.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    df = read_df(
        """
        SELECT o.*, e.arabic_name, e.department, e.section, p.project_name
        FROM overtime_records o
        JOIN employees e ON e.employee_code = o.employee_code
        LEFT JOIN projects p ON p.project_id = o.project
        ORDER BY o.year DESC, o.month DESC, o.overtime_date DESC
        """
    )
    df = restrict_df_by_access(df, "project_name", "department")
    st.dataframe(mask_salary_columns(df), use_container_width=True, hide_index=True)
    with st.form("overtime_form"):
        c1, c2, c3 = st.columns(3)
        employee_label = c1.selectbox("Employee", [f"{r.employee_code} - {r.arabic_name}" for r in employees.itertuples()])
        year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
        month = c3.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
        c4, c5, c6 = st.columns(3)
        project = c4.selectbox("Project", list(projects.keys()))
        overtime_date = c5.date_input("Overtime Date", value=date.today())
        payment_type = c6.selectbox("Payment Type", ["Net", "Gross"])
        c7, c8, c9, c10 = st.columns(4)
        hours = c7.number_input("Overtime Hours", min_value=0.0)
        hourly_rate = c8.number_input("Hourly Rate", min_value=0.0)
        multiplier = c9.number_input("Overtime Multiplier", min_value=0.0, value=1.5)
        approval_status = c10.selectbox("Approval Status", APPROVAL_STATUSES)
        taxable = st.checkbox("Taxable", value=True)
        insurance = st.checkbox("Insurance Applicable")
        reason = st.text_area("Reason")
        notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Overtime", type="primary")
    if submit and require_write("Overtime"):
        if not require_month_open(int(year), int(month)):
            return
        amount = hours * hourly_rate * multiplier
        run_sql(
            """
            INSERT INTO overtime_records
            (employee_code, year, month, project, overtime_date, overtime_hours, hourly_rate,
             overtime_multiplier, overtime_amount, payment_type, taxable, insurance_applicable,
             approval_status, reason, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_label.split(" - ")[0], int(year), int(month), projects[project], overtime_date.isoformat(), hours, hourly_rate, multiplier, amount, payment_type, 1 if taxable else 0, 1 if insurance else 0, approval_status, reason, notes, st.session_state.get("username"), now_text()),
        )
        st.success("Overtime saved.")
        st.rerun()
    protected_download_button("Export Overtime", df, "overtime.xlsx")


def payslips_page() -> None:
    page_header("Payslips", "Generate employee payslip views and Excel exports.")
    tx = payroll_transactions_df()
    if tx.empty:
        st.info("Generate payroll first.")
        return
    c1, c2, c3 = st.columns(3)
    year = c1.selectbox("Year", sorted(tx["year"].unique().tolist(), reverse=True))
    month = c2.selectbox("Month", sorted(tx[tx["year"] == year]["month"].unique().tolist()), format_func=lambda x: MONTHS[x])
    employee = c3.selectbox("Employee", tx[(tx["year"] == year) & (tx["month"] == month)]["employee_code"].tolist())
    row = tx[(tx["year"] == year) & (tx["month"] == month) & (tx["employee_code"] == employee)].iloc[0]
    bonus = bonus_register_df(year=year, month=month, employee_code=employee)
    payslip = pd.DataFrame(
        [
            ("Company Name", row["organization"]),
            ("Employee Code", row["employee_code"]),
            ("Arabic Name", row["arabic_name"]),
            ("Position", row["position"]),
            ("Department", row["department"]),
            ("Section", row["section"]),
            ("Project", row["default_project"]),
            ("Payroll Month", f"{MONTHS[int(month)]} {year}"),
            ("Basic Salary", row["basic_salary"]),
            ("Net Salary", row["base_net_salary"]),
            ("Allowances", row["total_allowances"]),
            ("Bonus", bonus["net_bonus_amount"].sum() if not bonus.empty else 0),
            ("Overtime", row.get("overtime_amount", 0)),
            ("Deductions", row.get("attendance_deduction", 0)),
            ("Tax", row["monthly_tax"]),
            ("Employee Insurance", row["employee_insurance"]),
            ("Net Transfer Amount", row["net_transfer_amount"]),
            ("Payment Status", row["payment_status"]),
        ],
        columns=["Item", "Value"],
    )
    st.dataframe(mask_salary_columns(payslip), use_container_width=True, hide_index=True)
    protected_download_button("Export Payslip", payslip, f"payslip_{employee}_{year}_{int(month):02d}.xlsx")


def scenario_simulation_page() -> None:
    page_header("Scenario Simulation Center", "Test payroll impact before applying increases, bonuses, allowances, tax or project changes.")
    employees = employee_options(active_only=True)
    projects = project_lookup(active_only=True)
    with st.form("scenario_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Scenario Name")
        scenario_type = c2.selectbox("Scenario Type", ["Increase all employees by %", "Add net bonus", "Add project allowance", "Transfer project", "Annual salary increase"])
        value = c3.number_input("Input Value", min_value=0.0, value=10.0)
        c4, c5, c6 = st.columns(3)
        year = c4.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
        month = c5.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
        target_project = c6.selectbox("Target Project", ["All"] + list(projects.keys()))
        target_department = st.selectbox("Target Department", ["All"] + option_rows("departments", "department"))
        notes = st.text_area("Notes")
        submit = st.form_submit_button("Run and Save Scenario", type="primary")
    if submit:
        emp_df = employee_options(active_only=True)
        if target_project != "All":
            emp_df = emp_df[emp_df["default_project"] == target_project]
        if target_department != "All":
            emp_df = emp_df[emp_df["department"] == target_department]
        details = []
        current_total = new_total = tax_diff = insurance_diff = 0.0
        for emp_row in emp_df.itertuples():
            emp = fetch_one("SELECT * FROM employees WHERE employee_code = ?", (emp_row.employee_code,))
            current_calc = payroll_calculation(emp, int(year), int(month))[0]
            if scenario_type in {"Increase all employees by %", "Annual salary increase"}:
                proposed = dict(emp)
                proposed["new_net_salary"] = emp["new_net_salary"] * (1 + value / 100)
                proposed["new_net_earning"] = proposed["new_net_salary"] + emp["new_allowance"]
                new_calc = gross_up_for_net(proposed["new_net_earning"], proposed, int(year))
            elif scenario_type == "Add net bonus":
                new_calc = bonus_calculation(emp, int(year), int(month), "Net Bonus", value, "Follow Employee Project Allocation", None)
                new_calc = {"total_company_cost": current_calc["total_company_cost"] + new_calc["company_cost_difference"], "monthly_tax": current_calc["monthly_tax"] + new_calc["tax_difference"], "employee_insurance": current_calc["employee_insurance"] + new_calc["employee_insurance_difference"]}
            else:
                new_calc = current_calc
            current_total += current_calc["total_company_cost"]
            new_total += new_calc["total_company_cost"]
            tax_diff += safe_float(new_calc.get("monthly_tax")) - current_calc["monthly_tax"]
            insurance_diff += safe_float(new_calc.get("employee_insurance")) - current_calc["employee_insurance"]
            details.append((emp_row.employee_code, current_calc["total_company_cost"], new_calc["total_company_cost"], new_calc["total_company_cost"] - current_calc["total_company_cost"], scenario_type))
        with db() as conn:
            cur = conn.execute(
                """
                INSERT INTO scenarios (scenario_name, scenario_type, year, month, target_project, target_department,
                                       input_value, current_payroll_cost, new_payroll_cost, cost_difference,
                                       tax_difference, insurance_difference, created_by, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, scenario_type, int(year), int(month), projects.get(target_project), target_department, value, current_total, new_total, new_total - current_total, tax_diff, insurance_diff, st.session_state.get("username"), now_text(), notes),
            )
            scenario_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO scenario_details (scenario_id, employee_code, current_cost, new_cost, cost_difference, details) VALUES (?, ?, ?, ?, ?, ?)",
                [(scenario_id, *row) for row in details],
            )
            conn.commit()
        st.success(f"Scenario saved #{scenario_id}.")
        st.rerun()
    scenarios = read_df("SELECT * FROM scenarios ORDER BY created_at DESC")
    st.dataframe(mask_salary_columns(scenarios), use_container_width=True, hide_index=True)
    protected_download_button("Export Scenarios", scenarios, "scenarios.xlsx")


def import_templates_page() -> None:
    page_header("Import Templates", "Download blank templates, upload completed files, preview and validate before import.")
    templates = {
        "Employees": ["employee_code", "organization", "sponsor", "arabic_name", "position", "department", "section", "default_project", "hiring_date", "basic_salary", "new_net_salary", "new_allowance", "insurance_salary_base", "status", "notes"],
        "Employee Allowances": ["employee_code", "allowance_type", "allowance_name", "amount", "calculation_type", "payment_type", "taxable", "social_insurance_applicable", "recurring", "project_charging_method", "specific_project", "effective_from", "effective_to", "department", "status"],
        "Employee Project Allocation": ["employee_code", "project", "allocation_type", "allocation_percentage", "fixed_allocation_amount", "effective_from", "effective_to", "is_primary_project", "status"],
        "Bonuses": ["employee_code", "year", "month", "bonus_date", "bonus_type", "bonus_category", "bonus_amount_entered", "project_charging_method", "charged_project", "payment_status", "approval_status", "bonus_reason", "notes"],
        "Salary Revisions": ["employee_code", "new_basic_salary", "new_net_salary", "new_allowance", "effective_from", "revision_type", "reason", "notes"],
        "Overtime": ["employee_code", "year", "month", "project", "overtime_date", "overtime_hours", "hourly_rate", "overtime_multiplier", "payment_type", "taxable", "insurance_applicable", "approval_status"],
        "Attendance Adjustments": ["employee_code", "year", "month", "working_days", "unpaid_leave_days", "absence_days", "reason", "approval_status"],
        "Bank Transfer Reconciliation": ["employee_code", "bank_account_iban", "transfer_reference", "actual_bank_transfer_amount", "transfer_date", "bank_reference", "notes"],
    }
    choice = st.selectbox("Template", list(templates.keys()))
    blank = pd.DataFrame(columns=templates[choice])
    protected_download_button("Download Blank Template", blank, f"{choice.lower().replace(' ', '_')}_template.xlsx")
    uploaded = st.file_uploader("Upload completed template for preview", type=["csv", "xlsx"], key="template_upload")
    if uploaded:
        incoming = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        missing = [col for col in templates[choice] if col not in incoming.columns]
        if missing:
            st.error(f"Missing columns: {', '.join(missing)}")
        else:
            st.success("Template structure is valid.")
        st.dataframe(incoming.head(200), use_container_width=True, hide_index=True)


def backup_restore_page() -> None:
    pg_mode = bool(DATABASE_URL)
    label = "PostgreSQL" if pg_mode else "SQLite"
    page_header("Backup & Restore", f"Export data, download backups, and track backup history ({label}).")
    if pg_mode:
        st.info("PostgreSQL mode: use the Export All Data button below. For full database backup, use your hosting provider's backup tools (e.g. Supabase Dashboard → Database → Backups).")
        data = export_all_tables_to_excel()
        st.download_button("Download All Tables (Excel)", excel_bytes(data), f"payroll_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", type="primary")
        if st.button("Record Export History"):
            run_sql("INSERT INTO backup_history (backup_name, backup_path, backup_type, created_by, created_at, notes) VALUES (?, ?, ?, ?, ?, ?)", (f"manual_export_{now_text()}", "excel", "Data Export", st.session_state.get("username"), now_text(), "Manual data export downloaded"))
            st.success("Export history recorded.")
    else:
        db_path = Path(__file__).with_name("payroll.db")
        c1, c2 = st.columns(2)
        with c1:
            if db_path.exists():
                st.download_button("Download SQLite Database Backup", db_path.read_bytes(), f"payroll_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db", type="primary")
                if st.button("Record Backup History"):
                    run_sql("INSERT INTO backup_history (backup_name, backup_path, backup_type, created_by, created_at, notes) VALUES (?, ?, 'SQLite', ?, ?, ?)", (db_path.name, str(db_path), st.session_state.get("username"), now_text(), "Manual backup downloaded"))
                    st.success("Backup history recorded.")
        with c2:
            uploaded = st.file_uploader("Restore SQLite Backup", type=["db", "sqlite"])
            if uploaded and is_admin():
                st.warning("Restore replaces the current local database. A safety copy is created first.")
                if st.button("Restore Database", type="primary"):
                    safety = db_path.with_name(f"payroll_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
                    if db_path.exists():
                        shutil.copy2(db_path, safety)
                    db_path.write_bytes(uploaded.read())
                    st.success(f"Database restored. Safety copy: {safety.name}. Restart the app.")
    history = read_df("SELECT * FROM backup_history ORDER BY created_at DESC")
    st.dataframe(history, use_container_width=True, hide_index=True)


def export_all_tables_to_excel() -> dict[str, pd.DataFrame]:
    tables = [
        "projects", "employees", "employee_project_allocations", "allowance_types",
        "employee_allowances", "payroll_runs", "payroll_transactions",
        "payroll_project_allocations", "bonus_simulations", "tax_laws",
        "tax_brackets", "social_insurance_setup", "salary_calculation_setup",
        "payment_statuses", "organizations", "sponsors", "departments",
        "sections", "positions", "users", "audit_log", "roles", "permissions",
        "role_permissions", "user_permissions", "user_project_access",
        "user_department_access", "user_sessions", "approval_requests",
        "approval_history", "employee_bonuses", "bonus_project_allocations",
        "salary_revisions", "payroll_locks", "bank_transfer_records",
        "bank_reconciliation", "alerts", "employee_documents",
        "attendance_adjustments", "overtime_records", "scenarios",
        "scenario_details", "backup_history", "organization_setup",
        "payroll_calendar", "tax_exemptions",
    ]
    result = {}
    for table in tables:
        try:
            result[table] = read_df(f"SELECT * FROM {table}")
        except Exception:
            pass
    return result


def organizations_page() -> None:
    page_header("Organizations", "Multi-organization setup for tax, social insurance, address and bank details.")
    df = read_df("SELECT * FROM organization_setup ORDER BY organization_code")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if require_write("Organizations", "Can Edit Tax Setup"):
        with st.form("org_setup_form"):
            c1, c2, c3 = st.columns(3)
            code = c1.text_input("Organization Code")
            name = c2.text_input("Organization Name")
            status = c3.selectbox("Status", ["Active", "Inactive"])
            c4, c5 = st.columns(2)
            tax_no = c4.text_input("Tax Registration Number")
            insurance_no = c5.text_input("Social Insurance Number")
            address = st.text_area("Address")
            bank_account = st.text_input("Bank Account")
            submit = st.form_submit_button("Save Organization", type="primary")
        if submit:
            run_sql(
                """
                INSERT INTO organization_setup
                (organization_code, organization_name, tax_registration_number, social_insurance_number, address, bank_account, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(organization_code) DO UPDATE SET organization_name = excluded.organization_name,
                    tax_registration_number = excluded.tax_registration_number,
                    social_insurance_number = excluded.social_insurance_number,
                    address = excluded.address,
                    bank_account = excluded.bank_account,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (code, name, tax_no, insurance_no, address, bank_account, status, now_text(), now_text()),
            )
            st.success("Organization saved.")
            st.rerun()


def payroll_calendar_page() -> None:
    page_header("Payroll Calendar", "Payroll cutoffs, review dates, bank transfer dates and close deadlines.")
    df = read_df("SELECT * FROM payroll_calendar ORDER BY year DESC, month DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.form("payroll_calendar_form"):
        c1, c2, c3 = st.columns(3)
        organization = c1.selectbox("Organization", option_rows("organizations", "organization"))
        year = c2.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
        month = c3.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
        c4, c5, c6 = st.columns(3)
        cutoff = c4.date_input("Cutoff Date", value=date.today())
        generation = c5.date_input("Payroll Generation Date", value=date.today())
        hr_review = c6.date_input("HR Review Date", value=date.today())
        c7, c8, c9 = st.columns(3)
        finance = c7.date_input("Finance Approval Date", value=date.today())
        bank = c8.date_input("Bank Transfer Date", value=date.today())
        close = c9.date_input("Payroll Close Date", value=date.today())
        status = st.selectbox("Status", ["Planned", "In Progress", "Completed", "Delayed"])
        notes = st.text_area("Notes")
        submit = st.form_submit_button("Save Calendar", type="primary")
    if submit and require_write("Payroll Calendar"):
        run_sql(
            """
            INSERT INTO payroll_calendar
            (organization, year, month, cutoff_date, payroll_generation_date, hr_review_date, finance_approval_date,
             bank_transfer_date, payroll_close_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization, year, month) DO UPDATE SET
                cutoff_date = excluded.cutoff_date,
                payroll_generation_date = excluded.payroll_generation_date,
                hr_review_date = excluded.hr_review_date,
                finance_approval_date = excluded.finance_approval_date,
                bank_transfer_date = excluded.bank_transfer_date,
                payroll_close_date = excluded.payroll_close_date,
                status = excluded.status,
                notes = excluded.notes
            """,
            (organization, int(year), int(month), cutoff.isoformat(), generation.isoformat(), hr_review.isoformat(), finance.isoformat(), bank.isoformat(), close.isoformat(), status, notes),
        )
        st.success("Calendar saved.")
        st.rerun()


def executive_reports_package_page() -> None:
    page_header("Executive Reports Package", "One-click Excel package with payroll, variance, bonus, project, bank, pending, quality and audit sheets.")
    year = st.number_input("Year", min_value=2023, max_value=2100, value=date.today().year)
    month = st.selectbox("Month", list(MONTHS.keys()), format_func=lambda x: MONTHS[x], index=date.today().month - 1)
    dashboard = pd.DataFrame(
        [
            {"Metric": "Employees", "Value": fetch_one("SELECT COUNT(*) AS c FROM employees WHERE status = 'Active'")["c"]},
            {"Metric": "Payroll Company Cost", "Value": safe_float(fetch_one("SELECT SUM(total_company_cost) AS s FROM payroll_transactions WHERE year = ? AND month = ?", (int(year), int(month)))["s"])},
            {"Metric": "Bonus Company Cost", "Value": safe_float(fetch_one("SELECT SUM(company_cost_difference) AS s FROM employee_bonuses WHERE year = ? AND month = ?", (int(year), int(month)))["s"])},
            {"Metric": "Pending Bonuses", "Value": fetch_one("SELECT COUNT(*) AS c FROM employee_bonuses WHERE payment_status != 'Paid'")["c"]},
        ]
    )
    sheets = {
        "Dashboard Summary": dashboard,
        "Monthly Payroll": payroll_transactions_df(int(year), int(month)),
        "Bonus Summary": bonus_register_df(year=int(year), month=int(month)),
        "Project Cost": payroll_project_allocations_df(int(year), int(month)),
        "Department Cost": payroll_transactions_df(int(year), int(month)).groupby("department", as_index=False)["total_company_cost"].sum() if not payroll_transactions_df(int(year), int(month)).empty else pd.DataFrame(),
        "Bank Transfer": payroll_transactions_df(int(year), int(month))[["employee_code", "arabic_name", "net_transfer_amount", "payment_status", "transfer_reference"]] if not payroll_transactions_df(int(year), int(month)).empty else pd.DataFrame(),
        "Pending Items": bonus_register_df(payment_status="Planned"),
        "Data Quality Issues": allocation_validation_df(),
        "Audit Summary": read_df("SELECT * FROM audit_log ORDER BY audit_id DESC LIMIT 500"),
    }
    package_has_salary = any(has_salary_columns(frame) for frame in sheets.values() if isinstance(frame, pd.DataFrame))
    if package_has_salary and not has_action("Can Export Salary Data"):
        st.warning("Executive package contains salary and company cost data. Export is disabled for this user.")
    else:
        st.download_button("Download Executive Reports Package", excel_bytes(sheets), f"executive_reports_{year}_{int(month):02d}.xlsx", type="primary")


PAGES = {
    "Executive Dashboard": dashboard_page,
    "Projects": projects_page,
    "Employees": employees_page,
    "Employee Project Allocation": allocation_page,
    "Employee Allowances": allowances_page,
    "Payroll Setup": setup_page,
    "Payroll Run Center": payroll_run_center_page,
    "Payroll Transactions": transactions_page,
    "Payroll Project Cost Allocation": project_cost_allocation_page,
    "Net to Gross Calculator": net_to_gross_page,
    "Bonus Calculator": bonus_calculator_page,
    "Bonus Register": bonus_register_page,
    "Employee Bonus History": employee_bonus_history_page,
    "Bonus Reports": bonus_reports_page,
    "Bonus Simulations": bonus_simulations_page,
    "Salary Revision History": salary_revision_history_page,
    "Payroll Approvals & Locking": payroll_approvals_locking_page,
    "Payroll Variance Report": payroll_variance_report_page,
    "Bank Transfer": bank_transfer_page,
    "Bank Reconciliation": bank_reconciliation_page,
    "Employee Cost Sheet": employee_cost_sheet_page,
    "Project Payroll Cost Dashboard": project_payroll_cost_dashboard_page,
    "Alerts Center": alerts_center_page,
    "Employee Documents": employee_documents_page,
    "Attendance Adjustments": attendance_adjustments_page,
    "Overtime": overtime_page,
    "Payslips": payslips_page,
    "Scenario Simulation Center": scenario_simulation_page,
    "Yearly Summary": yearly_summary_page,
    "Project Yearly Summary": project_yearly_summary_page,
    "Reports": reports_page,
    "Import Templates": import_templates_page,
    "Import / Export": import_export_page,
    "Backup & Restore": backup_restore_page,
    "Organizations": organizations_page,
    "Payroll Calendar": payroll_calendar_page,
    "Executive Reports Package": executive_reports_package_page,
    "Data Quality Center": data_quality_page,
    "Audit Log": audit_log_page,
    "Users & Permissions": users_permissions_page,
}

PAGE_GROUPS = {
    "Executive": ["Executive Dashboard", "Alerts Center", "Scenario Simulation Center"],
    "Employees": [
        "Employees",
        "Employee Bonus History",
        "Employee Allowances",
        "Employee Project Allocation",
        "Salary Revision History",
        "Employee Documents",
        "Attendance Adjustments",
        "Overtime",
        "Employee Cost Sheet",
    ],
    "Payroll": [
        "Payroll Run Center",
        "Payroll Transactions",
        "Payroll Project Cost Allocation",
        "Payroll Approvals & Locking",
        "Bank Transfer",
        "Bank Reconciliation",
        "Payslips",
        "Net to Gross Calculator",
    ],
    "Bonus": ["Bonus Calculator", "Bonus Register", "Bonus Reports", "Bonus Simulations"],
    "Reports": [
        "Reports",
        "Yearly Summary",
        "Project Yearly Summary",
        "Payroll Variance Report",
        "Project Payroll Cost Dashboard",
        "Executive Reports Package",
    ],
    "Setup": [
        "Payroll Setup",
        "Projects",
        "Organizations",
        "Payroll Calendar",
        "Import Templates",
        "Import / Export",
        "Data Quality Center",
        "Users & Permissions",
        "Backup & Restore",
        "Audit Log",
    ],
}

VIEWER_PAGES = {
    "Executive Dashboard",
    "Payroll Transactions",
    "Payroll Project Cost Allocation",
    "Bonus Simulations",
    "Yearly Summary",
    "Project Yearly Summary",
    "Reports",
}


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="P", layout="wide")
    init_app()
    if not st.session_state.get("authenticated"):
        apply_theme()
        login_page()
        return
    apply_theme()
    with st.sidebar:
        st.title(APP_NAME)
        st.caption(f"{st.session_state.get('role')} - {st.session_state.get('username')}")
        available_pages = [p for p in PAGES.keys() if has_page_access(p)]
        if not available_pages:
            st.error("No page permissions are assigned to this user.")
            if st.button("Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
            return
        current = st.session_state.get("current_page")
        if current not in available_pages:
            current = available_pages[0]
            st.session_state["current_page"] = current
        for group_name, group_pages in PAGE_GROUPS.items():
            visible_pages = [page_name for page_name in group_pages if page_name in available_pages]
            if not visible_pages:
                continue
            expanded = current in visible_pages or group_name in {"Executive", "Payroll"}
            with st.expander(group_name, expanded=expanded):
                for page_name in visible_pages:
                    button_type = "primary" if page_name == st.session_state.get("current_page") else "secondary"
                    if st.button(page_name, key=f"nav_{page_name}", use_container_width=True, type=button_type):
                        st.session_state["current_page"] = page_name
                        st.rerun()
        ungrouped_pages = [page_name for page_name in available_pages if not any(page_name in group for group in PAGE_GROUPS.values())]
        if ungrouped_pages:
            with st.expander("Other", expanded=current in ungrouped_pages):
                for page_name in ungrouped_pages:
                    button_type = "primary" if page_name == st.session_state.get("current_page") else "secondary"
                    if st.button(page_name, key=f"nav_{page_name}", use_container_width=True, type=button_type):
                        st.session_state["current_page"] = page_name
                        st.rerun()
        page = st.session_state.get("current_page", available_pages[0])
        st.session_state["current_page"] = page
        st.divider()
        st.caption("Currency: EGP")
        if st.button("Logout", use_container_width=True):
            if st.session_state.get("user_id"):
                run_sql(
                    """
                    UPDATE user_sessions
                    SET logout_time = ?, session_status = 'Logged Out'
                    WHERE user_id = ? AND session_status = 'Active'
                    """,
                    (now_text(), st.session_state.get("user_id")),
                )
            st.session_state.clear()
            st.rerun()
    if not has_page_access(page):
        st.error("You do not have access to this page.")
        return
    PAGES[page]()


if __name__ == "__main__":
    main()
