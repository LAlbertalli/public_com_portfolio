import argparse, decimal

from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig
from config import ALLOCATIONS, CHECK_ACCOUNTS
from decimal import Decimal


FORMAT_SHOW = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("% of portfolio", 15, lambda x: number_format(x, "%", 15)),
    ("Diff", 12, lambda x: number_format(x, "%")),
    ("Cost Basis", 12, lambda x: number_format(x, "$")),
    ("Gain/Loss", 12, lambda x: number_format(x, "$"))
    ]


FORMAT_REBALANCE = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("Buy Sell", 10, lambda x: string_format(x, 10)),
    ("Amount", 12, lambda x: number_format(x, "$")),
    ("New Balance", 12, lambda x: number_format(x, "$")),
    ("New %", 12, lambda x: number_format(x, "%")),
    ]


# Formatter helper functions
FORMAT = FORMAT_SHOW

def choose_table_format(format):
    global FORMAT
    FORMAT = format


def string_format(name, length = 40):
    if len(name) > length:
        return name[:length]
    return name.ljust(length)


def number_format(number, symbol, length = 12):
    return ("%s %s"%(number, symbol)).rjust(length)


def print_divider():
    div_len = sum(i for _,i,_ in FORMAT) + 3 * (len(FORMAT)-1) + 4
    print("-"* div_len)


def print_header(account):
    print("\n\n Portfolio %s\n"%account)
    print_divider()
    print("| "+ " | ".join([string_format(i,j) for i,j,_ in FORMAT]) + " |")
    print_divider()


def print_row(row):
    print("| " + " | ".join(f(r) for r,(_,_,f) in zip(row,FORMAT)) + " |")


def portfolio_allocation_analysis(positions,allocations):
    shown_symbols = []
    for p in positions:
        symbol = p.instrument.symbol
        shown_symbols += [symbol]
        name = p.instrument.name
        cost_basis = p.cost_basis.total_cost
        current_value = p.current_value
        percentage = p.percent_of_portfolio
        try:
            a = allocations[symbol]["allocation"]
        except KeyError:
            a = Decimal('0.0')
        change_from_basis = current_value - cost_basis
        yield [name, symbol,current_value, percentage, 
            a, cost_basis, change_from_basis]

    for symbol, a in allocations.items():
        if symbol not in shown_symbols:
            shown_symbols+=[symbol]
            yield ["", symbol, Decimal('0.0'), Decimal('0.0'), 
                a['allocation'], Decimal('0.0'), Decimal('0.0')]


def get_target_allocation(name):
    return ALLOCATIONS.get(name,ALLOCATIONS[None])



def parse_portfolio(portfolio):
    return (
        sum(i.value for i in portfolio.equity), 
        [i for i in portfolio.equity if i.type == 'CASH'][0],
        portfolio.positions
        )


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
    shown_symbols = []
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
    print_row(["Cash", "", cash.value, cash.percentage_of_portfolio, 
        cash.percentage_of_portfolio, 0.0, 0.0])
    print_divider()
    total_val += cash.value
    total_pct += cash.percentage_of_portfolio
    abs_delta += abs(cash.percentage_of_portfolio)
    print_row(["Total", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()

    # suggest rebalance
    cash_reb = cash.value > Decimal('20.0')
    abs_delts_reb = abs_delta > len(allocations) * Decimal('0.15')
    if abs_delts_reb or cash_reb:
        print("Suggested to rebalance this portfolio. Causes:")
        if abs_delts_reb:
            print("- Portfolio is out of balance of %.2f%%. Max is %.2f%%"%(
                abs_delta, len(allocations) * Decimal('0.15')))
        if cash_reb:
            print("- Portfolio has excessive cash balance %.2f$. Max is 20$"%(cash.value))


def calculate_rebalance(portfolio, name):
    allocations = get_target_allocation(name)
    value, cash, positions = parse_portfolio(portfolio)
    cash_value = cash.value
    sell = []
    buy = []
    for r in portfolio_allocation_analysis(positions, allocations):
        name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
        delta = alloc - percentage
        if delta < Decimal(-0.05): # Don't sell if difference is less than 0.05%
            sell_amt = current_value/percentage*delta
            sell_amt = sell_amt.quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
            sell += [(symbol, sell_amt)]
            cash_value += -sell_amt
        if delta > Decimal('0.0'): # Always buy everything underindexed
            buy += [(symbol, delta)]
    if len(buy) == 0:
        print("Error, found no underindexed fund to buy")
        return None, None
    total_delta = sum(delta for _, delta in buy)
    buy = [(symbol, (delta/total_delta*cash_value).quantize(
        Decimal('0.01'), rounding =decimal.ROUND_HALF_EVEN)) for symbol, delta in buy]
    ops = dict(sell+buy)

    # Print
    total_cval = Decimal('0.0')
    total_ops = Decimal('0.0')
    total_new = Decimal('0.0')
    total_pct = Decimal('0.0')
    choose_table_format(FORMAT_REBALANCE)
    print_header(name)
    shown_symbols = []
    for r in portfolio_allocation_analysis(positions, allocations):
        "Name","Symbol","Value","Buy Sell","Amount","New Balance","New %"
        name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
        op = ops.get(symbol, Decimal('0.0'))
        buy_sell = "Buy" if op > Decimal('0.0') else "Sell" if op < Decimal('0.0') else "Nothing"
        new_v = current_value+op
        new_pct = (new_v/value*100).quantize(Decimal('0.01'), rounding =decimal.ROUND_HALF_EVEN)
        print_row([name, symbol,current_value, buy_sell, op, new_v, new_pct])
        total_cval += current_value
        total_ops += op
        total_new += new_v
        total_pct += new_pct

    print_divider()
    print_row(["Total", "", total_cval, "", 
            total_ops, total_new, total_pct])
    print_divider()
    return sell, buy
    


def parse_args():
    parser = argparse.ArgumentParser(
        description='Help me monitor my portfolio on Public.com and keep it balanced',
        )
    parser.add_argument("action", choices=['show', 'rebalance'], 
        default = 'show', 
        help = "Action to be execute:\n\
    - show: Show the current portfolio\n\
    - rebalance: Rebalance the portfolio. Notice, without --run,\
 it will only simulate the rebalance",
        nargs = '?')
    parser.add_argument("--run", action = 'store_true',
        help = "For rebalance, actually use the public apis to run the planned actions")

    parser.add_argument('--account', 
        help = "Limit to the specified account")

    return parser.parse_args()


def show(client, account):
    for k,v in CHECK_ACCOUNTS.items():
        if not account or k == account:
            portfolio = client.get_portfolio(v)
            print_account_info(portfolio, k)


def rebalance(client, account, run):
    for k,v in CHECK_ACCOUNTS.items():
        if not account or k == account:
            portfolio = client.get_portfolio(v)
            sell,buy = calculate_rebalance(portfolio, k)


def validate_allocations(allocations):
    error = False
    for name,allocs in allocations.items():
        total_pct = Decimal('0.0')
        for symbol, a in allocs.items():
            try:
                total_pct += Decimal(a["allocation"])
            except:
                pass
            if type(a["allocation"]) != Decimal:
                error = True
                print(
                    "Error validating the configuration for %s. \
The allocation should be of type Decimal. '%s' is not" % ((name or "Default (None)"), symbol))
        if total_pct != Decimal('100.0'):
            error = True
            print("Error validating the configuration for %s. \
Total allocation should be 100%%. Found %f" % ((name or "Default (None)"), total_pct))
    return not error


def main():
    args = parse_args()
    
    try:
        with open(".publicdotcom_key") as f:
            key = f.readline()
    except:
        print("Error loading the key for public.com from the file .publicdotcom_key")
        return

    if not validate_allocations(ALLOCATIONS):
        return

    client = PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=key), 
        config=PublicApiClientConfiguration()
        )
    if args.action == "show":
        show(client, args.account)
    elif args.action == "rebalance":
        rebalance(client, args.account, args.run)

if __name__ == "__main__":
    main()