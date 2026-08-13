import decimal
from decimal import Decimal

from helper.arghelper import command
from helper.config_helper import get_account, get_accounts, get_target_allocation
from helper.portfolio import parse_portfolio, portfolio_allocation_analysis
from helper.tableprint import (
    choose_table_format,
    number_format,
    print_divider,
    print_header,
    print_row,
    string_format,
)

FORMAT_SHOW = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("% of portfolio", 15, lambda x: number_format(x, "%", 15)),
    ("Diff", 12, lambda x: number_format(x, "%")),
    ("Cost Basis", 12, lambda x: number_format(x, "$")),
    ("Gain/Loss", 12, lambda x: number_format(x, "$"))
    ]


def print_account_info(portfolio, name):
    allocations = get_target_allocation(name)
    value, cash, positions = parse_portfolio(portfolio)

    total_val = Decimal('0.0')
    total_cb = Decimal('0.0')
    total_pct = Decimal('0.0')
    abs_delta = Decimal('0.0')
    total_change_b = Decimal('0.0')

    choose_table_format(FORMAT_SHOW)

    print_header(name)
    for r in portfolio_allocation_analysis(positions, allocations):
        name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
        delta = alloc - percentage
        print_row([name, symbol,current_value, percentage, delta, 
            cost_basis, change_from_basis])
        total_val += current_value
        total_cb += cost_basis
        total_pct += percentage
        abs_delta += abs(delta)
        total_change_b += change_from_basis

    print_divider()
    print_row(["Total stock", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()
    cash_percent = (cash/value*100).quantize(Decimal("0.01"), 
        rounding = decimal.ROUND_HALF_EVEN)
    print_row(["Cash", "", cash, cash_percent, 
        cash_percent, 0.0, 0.0])
    print_divider()
    total_val += cash
    total_pct += cash_percent
    abs_delta += abs(cash_percent)
    print_row(["Total", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()

    # suggest rebalance
    cash_reb = cash > Decimal('20.0')
    abs_delts_reb = abs_delta > len(allocations) * Decimal('0.15')
    if abs_delts_reb or cash_reb:
        print("Suggested to rebalance this portfolio. Causes:")
        if abs_delts_reb:
            print("- Portfolio is out of balance of %.2f%%. Max is %.2f%%"%(
                abs_delta, len(allocations) * Decimal('0.15')))
        if cash_reb:
            print("- Portfolio has excessive cash balance %.2f$. Max is 20$"%(cash))

@command
def show(client, account):
    """Show the current portfolio"""
    if account:
        account_id = get_account(account)
        if account_id is None:
            print("ERROR: Account %s not found"%account)
            return
        accounts = [(account, account_id)]
    else:
        accounts = get_accounts()

    for name, aid in accounts:
        portfolio = client.get_portfolio(aid)
        print_account_info(portfolio, name)