# Payroll

Professional local payroll management system built with Python, Streamlit, and SQLite.

## What It Includes

- Employee master data with Arabic name support
- Project management and employee project allocation
- Monthly, one-time, and temporary employee allowances
- Payroll generation with tax, employee insurance, company insurance, net transfer, and company cost
- Project cost allocation for payroll, allowances, and bonuses
- Dynamic Egyptian tax setup with Law 175/2023 and Current 2024/2026 presets
- Year-based social insurance setup with editable min/max limits and shares
- Net-to-gross calculator with bracket-by-bracket tax breakdown
- Bonus calculator, bonus register/ledger, bonus reports, and saved simulations
- Users and permissions with role, page, project, department, salary, export, and action access
- Payroll approvals, payroll locks, salary revision history, bank transfer, bank reconciliation, payslips, overtime, attendance adjustments, documents, alerts, scenarios, and backup/restore
- Yearly summaries by employee and by project
- Reports with Excel and CSV export
- Import/export center
- Data quality center
- Audit log
- Login with Super Admin, Admin, Payroll Manager, HR, Finance, and Viewer roles

## Default Login

| Role | Username | Password |
|---|---|---|
| Super Admin | `superadmin` | `superadmin123` |
| Admin | `admin` | `admin123` |
| Payroll Manager | `payroll` | `payroll123` |
| HR User | `hr` | `hr123` |
| Finance User | `finance` | `finance123` |
| Viewer | `viewer` | `viewer123` |

## Install

```bash
pip install streamlit pandas openpyxl xlsxwriter
```

## Run Locally

```bash
python -m streamlit run payroll_system.py --server.address 127.0.0.1 --server.port 8505
```

Open:

```text
http://127.0.0.1:8505
```

If port 8505 is already in use, change only the port number, for example:

```bash
python -m streamlit run payroll_system.py --server.address 127.0.0.1 --server.port 8506
```

## Database

The SQLite database is created automatically as:

```text
payroll.db
```

On first run, the app creates all required tables, seeds Chevron and Chevron Upstream projects, seeds the supplied employee data, creates 100% default project allocations, and inserts current New Allowance values as active monthly employee allowance lines.

## Notes

- Currency is EGP.
- Basic salary is independent and editable. The current default calculation uses the sheet-style rule from `Net To Gross Osama.xlsx`: insurance base is derived from gross salary divided by 1.3, then basic salary equals gross salary less 30% of the insurance base.
- Tax laws, brackets, exemptions, bracket-skipping rules, tax rounding, and social insurance values are editable setup data.
- The current default tax preset is `Egypt Current Income Tax Setup 2024/2026`; Payroll Setup also includes an `Egypt Income Tax Law 175/2023` preset button.
- Default 2026 social insurance setup uses minimum 2,700 EGP, maximum 16,700 EGP, employee share 11%, and company share 18.75%, all editable by year.
- Bonus Calculator treats bonuses as one-time annual income for tax impact by default. It does not increase social insurance unless `Social Insurance Applicable` is checked.
- Payroll transactions are not physically deleted. Recalculation updates existing employee/month rows and recreates project allocation rows.
- For production use, review seeded tax and insurance setup with your payroll/tax advisor before closing payroll.
