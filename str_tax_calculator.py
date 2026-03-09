#!/usr/bin/env python3
"""
Short-Term Rental (STR) Tax Savings Calculator
═══════════════════════════════════════════════
Estimates Year-1 tax savings for W2 earners purchasing a short-term rental.
Includes bonus/accelerated depreciation via cost segregation study.

DISCLAIMER: For educational purposes only. Consult a licensed CPA or tax
attorney before making any tax or investment decisions.
"""

import sys
import os
from datetime import date, datetime

# ── Terminal colors ───────────────────────────────────────────────────────────
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
ORANGE = "\033[38;5;208m"
RESET  = "\033[0m"

def clr(text, *codes):
    return "".join(codes) + str(text) + RESET

def moneyf(v):
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"

def pctf(v):
    return f"{v * 100:.1f}%"

def line(char="─", width=66):
    return char * width

# ── Input helpers ─────────────────────────────────────────────────────────────
def ask_float(prompt, default=None, min_v=0):
    while True:
        hint = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{hint}: ").strip()
        if not raw and default is not None:
            return float(default)
        try:
            val = float(raw.replace(",", "").replace("$", "").replace("%", ""))
            if val < min_v:
                print(clr(f"  ⚠  Value must be ≥ {min_v}", YELLOW))
                continue
            return val
        except ValueError:
            print(clr("  ⚠  Enter a valid number.", YELLOW))

def ask_int(prompt, default=None, choices=None):
    while True:
        hint = f" [{default}]" if default is not None else ""
        raw = input(f"  {prompt}{hint}: ").strip()
        if not raw and default is not None:
            return int(default)
        try:
            val = int(raw)
            if choices and val not in choices:
                print(clr(f"  ⚠  Choose from: {choices}", YELLOW))
                continue
            return val
        except ValueError:
            print(clr("  ⚠  Enter a whole number.", YELLOW))

def ask_yn(prompt, default=True):
    opts = "Y/n" if default else "y/N"
    raw = input(f"  {prompt} [{opts}]: ").strip().lower()
    if not raw:
        return default
    return raw.startswith("y")

def section(title):
    print()
    print(clr(line(), CYAN))
    print(clr(f"  {title}", BOLD + CYAN))
    print(clr(line(), CYAN))

def row(label, value, color=RESET, width=44):
    print(f"    {label:<{width}}{clr(value, color)}")

def divider(width=66):
    print(f"    {clr(line('·', width - 4), DIM)}")

# ── Federal tax brackets (2025, approximate) ──────────────────────────────────
_SINGLE = [(11925,.10),(48475,.12),(103350,.22),(197300,.24),(250525,.32),(626350,.35),(1e9,.37)]
_MFJ    = [(23850,.10),(96950,.12),(206700,.22),(394600,.24),(501050,.32),(751600,.35),(1e9,.37)]

def total_federal_tax(income, married):
    """Compute total federal income tax using 2025 brackets."""
    if income <= 0:
        return 0.0
    brackets = _MFJ if married else _SINGLE
    tax, prev = 0.0, 0.0
    for limit, rate in brackets:
        chunk = min(income, limit) - prev
        if chunk <= 0:
            break
        tax += chunk * rate
        prev = limit
        if income <= limit:
            break
    return tax

def marginal_rate(income, married):
    brackets = _MFJ if married else _SINGLE
    for limit, rate in brackets:
        if income <= limit:
            return rate
    return brackets[-1][1]

# ── Bonus depreciation schedule (TCJA phase-down) ─────────────────────────────
_BONUS = {2022: 1.00, 2023: 0.80, 2024: 0.60, 2025: 0.40, 2026: 0.20, 2027: 0.00}

def bonus_pct(year):
    if year <= 2022:
        return 1.00
    return _BONUS.get(year, 0.00)

# ── Year-1 MACRS rates (200DB / 150DB, half-year convention) ──────────────────
_MACRS_Y1 = {5: 0.2000, 7: 0.1429, 15: 0.0500}

def year1_depreciation(basis, life, tax_year):
    """
    Calculate Year-1 depreciation combining bonus depreciation and regular MACRS.
    Real property (27.5yr / 39yr) uses straight-line only — no bonus.
    """
    if life in (27.5, 39.0):
        return basis / life
    bp      = bonus_pct(tax_year)
    bonus   = basis * bp
    regular = (basis * (1 - bp)) * _MACRS_Y1.get(life, 1 / life)
    return bonus + regular

# ── Mortgage helpers ──────────────────────────────────────────────────────────
def year1_mortgage_interest(principal, annual_rate, term_years):
    """Sum of the 12 monthly interest charges in Year 1."""
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r   = annual_rate / 12
    n   = term_years * 12
    pmt = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    balance, total_interest = principal, 0.0
    for _ in range(12):
        interest        = balance * r
        total_interest += interest
        balance        -= (pmt - interest)
    return total_interest

def annual_debt_service(principal, annual_rate, term_years):
    """Full annual principal + interest payment."""
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r   = annual_rate / 12
    n   = term_years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1) * 12

# ═════════════════════════════════════════════════════════════════════════════
def main():
    print()
    print(clr("╔" + "═" * 64 + "╗", ORANGE + BOLD))
    print(clr("║" + "  SHORT-TERM RENTAL  ·  TAX SAVINGS CALCULATOR  ".center(64) + "║", ORANGE + BOLD))
    print(clr("║" + "  W2 Income Offset  +  Bonus / Turbo Depreciation  ".center(64) + "║", ORANGE + BOLD))
    print(clr("╚" + "═" * 64 + "╝", ORANGE + BOLD))
    print(clr("  For educational use only — consult a CPA before filing.", DIM))

    cur_year = date.today().year

    # ── 1. PROPERTY ───────────────────────────────────────────────────────────
    section("1.  PROPERTY DETAILS")
    purchase_price = ask_float("Purchase price ($)", 600_000)
    land_pct_raw   = ask_float("Land value as % of purchase price  (typically 15–25%)", 20)
    land_pct       = land_pct_raw / 100
    land_value     = purchase_price * land_pct
    building_value = purchase_price - land_value
    year_placed    = ask_int("Year property placed in service", cur_year,
                             choices=list(range(2020, 2031)))
    bp             = bonus_pct(year_placed)

    print(f"\n  {clr('Depreciable building basis: ', DIM)}"
          f"{clr(moneyf(building_value), CYAN + BOLD)}")
    print(f"  {clr(f'Bonus depreciation rate for {year_placed}: {pctf(bp)}', YELLOW)}")
    if year_placed >= 2026:
        print(clr("  ℹ  Legislation to restore 100 % bonus was pending in early 2026.", DIM))
        print(clr("     Verify the current rate with your CPA before filing.", DIM))

    print("\n  Depreciation life (determines the building shell class):")
    print("    1)  27.5 years  — residential rental  (avg stay > 7 days)")
    print("    2)  39 years    — nonresidential / transient  (avg stay ≤ 7 days)")
    dep_life = 27.5 if ask_int("Select", 1, choices=[1, 2]) == 1 else 39.0

    # ── 2. COST SEGREGATION ───────────────────────────────────────────────────
    section("2.  COST SEGREGATION STUDY")
    print(clr("  Reclassifies portions of the building into shorter-lived assets", DIM))
    print(clr("  (5 / 7 / 15 year) that qualify for bonus depreciation,", DIM))
    print(clr("  dramatically accelerating Year-1 write-offs.", DIM))
    do_costseg = ask_yn("\n  Include a cost segregation study?", True)

    costseg_fee  = 0.0
    costseg_dict = {}  # {life: basis}

    if do_costseg:
        print("\n  Estimation method:")
        print("    1)  Auto-estimate  (industry averages — quick)")
        print("    2)  Manual entry   (enter your own percentages)")
        cs_mode = ask_int("  Select", 1, choices=[1, 2])
        costseg_fee = ask_float("  Cost segregation study fee ($)", 5_000)

        if cs_mode == 1:
            p5, p7, p15 = 0.12, 0.06, 0.08
            print(clr(f"\n  Using: 5-yr 12% | 7-yr 6% | 15-yr 8% | {dep_life}-yr {100-12-6-8}%", DIM))
        else:
            print(clr(f"\n  Enter each class as % of depreciable building value ({moneyf(building_value)}):", DIM))
            p5  = ask_float("  5-year  property % (appliances, fixtures, flooring)  [12]", 12) / 100
            p7  = ask_float("  7-year  property % (furniture, equipment)             [6]",  6)  / 100
            p15 = ask_float("  15-year property % (landscaping, paving, fencing)     [8]", 8)  / 100
            total_short = p5 + p7 + p15
            if total_short >= 1.0:
                print(clr("  ⚠  Short-life % ≥ 100%; capping combined at 80 %.", YELLOW))
                scale = 0.80 / total_short
                p5, p7, p15 = p5 * scale, p7 * scale, p15 * scale

        costseg_dict[5]        = building_value * p5
        costseg_dict[7]        = building_value * p7
        costseg_dict[15]       = building_value * p15
        costseg_dict[dep_life] = building_value * (1 - p5 - p7 - p15)
    else:
        costseg_dict[dep_life] = building_value

    # Total Year-1 depreciation
    total_depreciation = sum(
        year1_depreciation(basis, life, year_placed)
        for life, basis in costseg_dict.items()
    )

    # For comparison: depreciation WITHOUT cost seg
    no_costseg_dep = building_value / dep_life

    # ── 3. FINANCING ──────────────────────────────────────────────────────────
    section("3.  FINANCING")
    financed           = ask_yn("Did you finance the purchase?", True)
    mortgage_int_y1    = 0.0
    debt_service       = 0.0
    loan_amount        = 0.0
    interest_rate      = 0.0
    loan_term          = 30

    if financed:
        loan_amount   = ask_float("Loan amount ($)", round(purchase_price * 0.75, -3))
        interest_rate = ask_float("Annual interest rate (%)", 7.0) / 100
        loan_term     = ask_int("Loan term (years)", 30, choices=[10, 15, 20, 25, 30])
        mortgage_int_y1 = year1_mortgage_interest(loan_amount, interest_rate, loan_term)
        debt_service    = annual_debt_service(loan_amount, interest_rate, loan_term)

    # ── 4. RENTAL INCOME ──────────────────────────────────────────────────────
    section("4.  RENTAL INCOME")
    avg_nightly    = ask_float("Average nightly rate ($)", 250)
    occupancy_raw  = ask_float("Expected occupancy rate (%)", 65)
    occupancy      = occupancy_raw / 100
    rental_income  = avg_nightly * 365 * occupancy
    print(f"\n  {clr('Projected gross annual rental income:', DIM)} "
          f"{clr(moneyf(rental_income), CYAN + BOLD)}")

    # ── 5. OPERATING EXPENSES ─────────────────────────────────────────────────
    section("5.  OPERATING EXPENSES  (Annual)")
    prop_tax  = ask_float("Property taxes ($)",                          round(purchase_price * 0.012, -2))
    insurance = ask_float("Insurance / STR policy ($)",                  2_500)
    hoa       = ask_float("HOA / condo fees ($)",                        0)
    mgmt_pct  = ask_float("Property management fee (% of revenue) [20]", 20) / 100
    mgmt_fee  = rental_income * mgmt_pct
    utilities = ask_float("Utilities ($)",                               3_000)
    supplies  = ask_float("Supplies & consumables ($)",                  1_500)
    repairs   = ask_float("Repairs & maintenance ($)",                   2_000)
    platform  = ask_float("Platform / Airbnb fees ($)",                  round(rental_income * 0.03, -2))
    other_exp = ask_float("Other expenses ($)",                          0)

    operating_expenses = (prop_tax + insurance + hoa + mgmt_fee + utilities
                          + supplies + repairs + platform + other_exp + costseg_fee)

    # ── 6. TAX PROFILE ────────────────────────────────────────────────────────
    section("6.  YOUR TAX PROFILE")
    w2_income  = ask_float("W2 gross income ($)", 250_000)
    married    = ask_yn("Filing as Married Filing Jointly?", True)
    state_rate = ask_float("State income tax rate (%)  [0 if no income tax]", 9.3) / 100

    print()
    print(clr("  STR NON-PASSIVE STATUS", BOLD))
    print("  When an STR qualifies as non-passive, losses directly offset W2 income.")
    print("  Two common paths:")
    print("    A)  STR Loophole  — avg stay ≤ 7 days + you materially participate")
    print("        (100+ hrs/yr in the STR, more than any other person)")
    print("    B)  RE Professional — 750+ hrs/yr in real estate activities total,")
    print("        more than half your work time, + material participation in each rental")
    str_nonpassive = ask_yn("\n  Will this STR loss be treated as non-passive?", True)

    # ── CALCULATIONS ──────────────────────────────────────────────────────────
    total_deductions   = operating_expenses + mortgage_int_y1 + total_depreciation
    net_rental_income  = rental_income - total_deductions  # negative = loss

    if str_nonpassive and net_rental_income < 0:
        loss_applied = abs(net_rental_income)
    else:
        loss_applied = 0.0

    reduced_w2       = max(0.0, w2_income - loss_applied)
    fed_tax_original = total_federal_tax(w2_income, married)
    fed_tax_after    = total_federal_tax(reduced_w2, married)
    fed_savings      = fed_tax_original - fed_tax_after
    state_savings    = loss_applied * state_rate
    total_savings    = fed_savings + state_savings
    marg_rate        = marginal_rate(w2_income, married)

    # Cash flow (depreciation is non-cash — add back for cash picture)
    noi              = rental_income - operating_expenses   # before financing & depreciation
    cash_flow        = noi - debt_service                   # after debt service, before tax
    net_benefit      = cash_flow + total_savings            # all-in year-1 benefit

    # Cost-seg comparison
    costseg_extra_dep   = total_depreciation - no_costseg_dep
    costseg_extra_saves = costseg_extra_dep * (marg_rate + state_rate)

    # ── RESULTS ───────────────────────────────────────────────────────────────
    section("  ★  RESULTS SUMMARY")

    # --- Property Basis ---
    print(clr("\n  PROPERTY BASIS", BOLD))
    row("Purchase Price",             moneyf(purchase_price))
    row("Land Value (non-depreciable)", f"({moneyf(land_value)})")
    row("Depreciable Building Basis", moneyf(building_value), GREEN + BOLD)

    # --- Depreciation Breakdown ---
    print(clr("\n  YEAR-1 DEPRECIATION BREAKDOWN", BOLD))
    if do_costseg:
        for life in sorted(costseg_dict.keys()):
            basis = costseg_dict[life]
            dep   = year1_depreciation(basis, life, year_placed)
            bonus = dep - (basis / life) if life not in (27.5, 39.0) else 0
            life_label = f"{life:.0f}-yr class (basis {moneyf(basis)})"
            row(life_label, moneyf(dep), CYAN)
    else:
        row(f"{dep_life:.0f}-year straight-line (no cost seg)", moneyf(total_depreciation), CYAN)

    divider()
    row("TOTAL Year-1 Depreciation",   moneyf(total_depreciation), GREEN + BOLD)
    if do_costseg:
        row(f"  vs. without cost seg ({dep_life:.0f}-yr)",
            moneyf(no_costseg_dep), DIM)
        row("  Extra depreciation from cost seg",
            moneyf(costseg_extra_dep), YELLOW)
    row(f"Bonus depreciation rate ({year_placed})", pctf(bp), YELLOW)

    # --- Income & Expenses ---
    print(clr("\n  RENTAL INCOME & EXPENSES", BOLD))
    row("Gross Rental Income",         moneyf(rental_income),       GREEN)
    row("  Operating Expenses",       f"({moneyf(operating_expenses)})", "")
    row("  Mortgage Interest (Yr 1)", f"({moneyf(mortgage_int_y1)})", "")
    row("  Depreciation (non-cash)",  f"({moneyf(total_depreciation)})", "")
    divider()
    if net_rental_income < 0:
        row("Net Rental LOSS (Year 1)",
            f"({moneyf(abs(net_rental_income))})", YELLOW + BOLD)
    else:
        row("Net Rental Income (Year 1)",  moneyf(net_rental_income), GREEN + BOLD)

    # --- W2 Offset ---
    print(clr("\n  W2 INCOME OFFSET", BOLD))
    row("W2 Gross Income",             moneyf(w2_income))
    if str_nonpassive and net_rental_income < 0:
        row("STR Loss Applied to W2",  f"({moneyf(loss_applied)})",  GREEN)
        row("Adjusted Taxable Income", moneyf(reduced_w2),           GREEN + BOLD)
    elif not str_nonpassive and net_rental_income < 0:
        row("STR Loss Status",         "PASSIVE — carried forward",  YELLOW)
        row("W2 Income (unchanged)",   moneyf(w2_income))
        print(clr("  ℹ  Passive losses may offset future STR income or gains on sale.", DIM))
    else:
        row("STR produces taxable income", moneyf(net_rental_income), YELLOW)

    # --- Tax Savings ---
    print(clr("\n  TAX SAVINGS ESTIMATE", BOLD))
    row("Federal Marginal Rate",       pctf(marg_rate))
    row("State Rate",                  pctf(state_rate))
    row("Combined Marginal Rate",      pctf(marg_rate + state_rate))
    divider()
    row("Federal Tax Savings",         moneyf(fed_savings),    GREEN)
    row("State Tax Savings",           moneyf(state_savings),  GREEN)
    row("TOTAL ESTIMATED TAX SAVINGS", moneyf(total_savings),  GREEN + BOLD)
    if do_costseg:
        row("  Attributable to cost seg", moneyf(costseg_extra_saves), DIM)

    # --- Cash Flow ---
    print(clr("\n  YEAR-1 CASH FLOW SNAPSHOT", BOLD))
    row("Gross Rental Income",         moneyf(rental_income),     GREEN)
    row("Operating Expenses",         f"({moneyf(operating_expenses)})", "")
    row("Net Operating Income (NOI)",  moneyf(noi),               CYAN)
    if financed:
        row("Annual Debt Service",     f"({moneyf(debt_service)})", "")
    row("Cash Flow (before tax)",      moneyf(cash_flow),
        GREEN if cash_flow >= 0 else YELLOW)
    row("Tax Savings / Refund",        moneyf(total_savings),     GREEN)
    divider()
    row("TOTAL YEAR-1 ECONOMIC BENEFIT", moneyf(net_benefit),    GREEN + BOLD)

    # --- Quick Comparison: No Cost Seg vs Cost Seg ---
    if do_costseg:
        print(clr("\n  COST SEGREGATION IMPACT COMPARISON", BOLD))
        no_cs_loss   = rental_income - (operating_expenses + mortgage_int_y1 + no_costseg_dep)
        no_cs_loss_a = abs(no_cs_loss) if no_cs_loss < 0 else 0
        no_cs_savings = (no_cs_loss_a * (marg_rate + state_rate)
                         if str_nonpassive else 0)

        print(f"  {'':44}{'No Cost Seg':>12}   {'With Cost Seg':>12}")
        print(f"  {clr(line('·', 62), DIM)}")
        print(f"  {'Year-1 Depreciation':<44}"
              f"{moneyf(no_costseg_dep):>12}   {moneyf(total_depreciation):>12}")
        print(f"  {'Est. Net Rental Loss':<44}"
              f"{moneyf(abs(no_cs_loss)) if no_cs_loss < 0 else '$0':>12}   "
              f"{moneyf(abs(net_rental_income)) if net_rental_income < 0 else '$0':>12}")
        print(f"  {'Est. Total Tax Savings':<44}"
              f"{moneyf(no_cs_savings):>12}   "
              f"{clr(moneyf(total_savings), GREEN + BOLD):>12}")
        extra = total_savings - no_cs_savings
        if extra > 0:
            print(f"\n  {clr(f'Cost seg study nets ~{moneyf(extra)} extra tax savings vs. {moneyf(costseg_fee)} fee', GREEN)}")

    # --- Notes ---
    print()
    print(clr("  " + line("─", 62), DIM))
    print(clr("  KEY ASSUMPTIONS & NOTES", BOLD))
    notes = [
        f"Bonus depreciation rate for {year_placed}: {pctf(bp)}",
        "STR losses offset W2 only when activity is non-passive.",
        "Material participation: typically 100+ hrs & most time of any person.",
        "Depreciation recapture (Sec. 1245 / 1250) applies upon property sale.",
        "State conformity to bonus depreciation varies — check your state.",
        "Some states cap STR deductions — verify local rules.",
        f"Cost seg fee of {moneyf(costseg_fee)} deducted as a business expense in Year 1."
        if do_costseg else "",
        "DISCLAIMER: Estimate only. Consult a licensed CPA before filing.",
    ]
    for note in notes:
        if note:
            color = RED + BOLD if "DISCLAIMER" in note else DIM
            print(clr(f"  • {note}", color))
    print()

    # ── Save Report ───────────────────────────────────────────────────────────
    if ask_yn("Save a detailed text report to the Desktop?", True):
        _save_report(
            purchase_price, land_value, building_value, dep_life,
            do_costseg, costseg_dict, costseg_fee, year_placed, bp,
            total_depreciation, no_costseg_dep,
            rental_income, operating_expenses, mortgage_int_y1,
            net_rental_income, w2_income, married, reduced_w2, loss_applied,
            marg_rate, state_rate, fed_savings, state_savings, total_savings,
            noi, debt_service, cash_flow, net_benefit, str_nonpassive, financed
        )


# ── Report writer ─────────────────────────────────────────────────────────────
def _save_report(purchase_price, land_value, building_value, dep_life,
                 do_costseg, costseg_dict, costseg_fee, year_placed, bp,
                 total_depreciation, no_costseg_dep,
                 rental_income, operating_expenses, mortgage_int_y1,
                 net_rental_income, w2_income, married, reduced_w2, loss_applied,
                 marg_rate, state_rate, fed_savings, state_savings, total_savings,
                 noi, debt_service, cash_flow, net_benefit, str_nonpassive, financed):

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    fname   = os.path.join(desktop, f"STR_Tax_Report_{datetime.now():%Y%m%d_%H%M}.txt")

    def mf(v): return moneyf(v)
    def pf(v): return pctf(v)
    def ln(c="─"): return c * 66

    out = []
    out.append(ln("="))
    out.append("  SHORT-TERM RENTAL (STR) TAX SAVINGS REPORT")
    out.append(f"  Generated: {datetime.now():%B %d, %Y  %I:%M %p}")
    out.append(ln("="))
    out.append("")

    out.append("PROPERTY BASIS")
    out.append(f"  Purchase Price                    : {mf(purchase_price)}")
    out.append(f"  Land Value                        : ({mf(land_value)})")
    out.append(f"  Depreciable Building Basis        : {mf(building_value)}")
    out.append(f"  Depreciation Life                 : {dep_life} years")
    out.append(f"  Year Placed in Service            : {year_placed}")
    out.append("")

    out.append("YEAR-1 DEPRECIATION")
    out.append(f"  Bonus Depreciation Rate ({year_placed})     : {pf(bp)}")
    for life in sorted(costseg_dict.keys()):
        basis = costseg_dict[life]
        dep   = year1_depreciation(basis, life, year_placed)
        out.append(f"  {life:.0f}-year class (basis {mf(basis)})  : {mf(dep)}")
    out.append(f"  {ln('·')}")
    out.append(f"  TOTAL Year-1 Depreciation         : {mf(total_depreciation)}")
    out.append(f"  Without cost seg ({dep_life:.0f}-yr only)      : {mf(no_costseg_dep)}")
    if do_costseg:
        out.append(f"  Cost Seg Study Fee                : ({mf(costseg_fee)})")
    out.append("")

    out.append("RENTAL INCOME & EXPENSES")
    out.append(f"  Gross Rental Income               : {mf(rental_income)}")
    out.append(f"  Operating Expenses                : ({mf(operating_expenses)})")
    out.append(f"  Mortgage Interest (Year 1)        : ({mf(mortgage_int_y1)})")
    out.append(f"  Depreciation                      : ({mf(total_depreciation)})")
    out.append(f"  {ln('·')}")
    out.append(f"  Net Rental Income / (Loss)        : {mf(net_rental_income)}")
    out.append("")

    out.append("W2 INCOME OFFSET")
    out.append(f"  W2 Gross Income                   : {mf(w2_income)}")
    out.append(f"  STR Loss Applied                  : ({mf(loss_applied)})")
    out.append(f"  Adjusted Taxable W2 Income        : {mf(reduced_w2)}")
    out.append(f"  Filing Status                     : {'MFJ' if married else 'Single'}")
    out.append(f"  Non-Passive Treatment             : {'Yes' if str_nonpassive else 'No — passive carry-forward'}")
    out.append("")

    out.append("TAX SAVINGS ESTIMATE")
    out.append(f"  Federal Marginal Rate             : {pf(marg_rate)}")
    out.append(f"  State Income Tax Rate             : {pf(state_rate)}")
    out.append(f"  Federal Tax Savings               : {mf(fed_savings)}")
    out.append(f"  State Tax Savings                 : {mf(state_savings)}")
    out.append(f"  {ln('·')}")
    out.append(f"  TOTAL ESTIMATED TAX SAVINGS       : {mf(total_savings)}")
    out.append("")

    out.append("YEAR-1 CASH FLOW SNAPSHOT")
    out.append(f"  Gross Rental Income               : {mf(rental_income)}")
    out.append(f"  Operating Expenses                : ({mf(operating_expenses)})")
    out.append(f"  Net Operating Income (NOI)        : {mf(noi)}")
    if financed:
        out.append(f"  Annual Debt Service               : ({mf(debt_service)})")
    out.append(f"  Cash Flow (before tax)            : {mf(cash_flow)}")
    out.append(f"  Tax Savings / Offset              : {mf(total_savings)}")
    out.append(f"  {ln('·')}")
    out.append(f"  TOTAL YEAR-1 ECONOMIC BENEFIT     : {mf(net_benefit)}")
    out.append("")

    out.append(ln("─"))
    out.append("DISCLAIMER")
    out.append("  This report is for educational and illustrative purposes only.")
    out.append("  It does not constitute tax, legal, or investment advice.")
    out.append("  Actual results depend on individual circumstances, IRS guidance,")
    out.append("  and applicable state law. Always consult a licensed CPA or tax")
    out.append("  attorney before making any tax or investment decisions.")
    out.append(ln("─"))

    with open(fname, "w") as f:
        f.write("\n".join(out))
    print(clr(f"\n  ✓  Report saved: {fname}", GREEN + BOLD))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(clr("\n\n  Exited.", DIM))
        sys.exit(0)
