from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig
from config import ALLOCATIONS, CHECK_ACCOUNTS
from decimal import Decimal

with open(".publicdotcom_key") as f:
    key = f.readline()

client = PublicApiClient(
    ApiKeyAuthConfig(api_secret_key=key), 
    config=PublicApiClientConfiguration()
    )

accounts = client.get_accounts()

for acc in accounts.accounts:
    print(acc.account_type.name, acc.account_id)

def string_format(name, length = 40):
    if len(name) > length:
        return name[:length]
    return name.ljust(length)

def number_format(number, symbol, length = 12):
    return ("%s %s"%(number, symbol)).rjust(length)

FORMAT = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("% of portfolio", 15, lambda x: number_format(x, "%", 15)),
    ("Diff", 12, lambda x: number_format(x, "%")),
    ("Cost Basis", 12, lambda x: number_format(x, "$")),
    ("Gain/Loss", 12, lambda x: number_format(x, "$"))
    ]

def print_divider():
    div_len = sum(i for _,i,_ in FORMAT) + 3 * (len(FORMAT)-1) + 4
    print("-"* div_len)

def print_header(account):
    print("\n Portfolio %s\n"%account)
    print_divider()
    print("| "+ " | ".join([string_format(i,j) for i,j,_ in FORMAT]) + " |")
    print_divider()

def print_row(row):
    print("| " + " | ".join(f(r) for r,(_,_,f) in zip(row,FORMAT)) + " |")

for k,v in CHECK_ACCOUNTS.items():
    portfolio = client.get_portfolio(v)
    value = portfolio.equity[0].value
    cash = portfolio.buying_power.cash_only_buying_power
    positions = portfolio.positions
    total_val = Decimal(0.0)
    total_cb = Decimal(0.0)
    total_pct = Decimal(0.0)
    abs_delta = Decimal(0.0)
    total_change_b = Decimal(0.0)
    print_header(k)
    allocations = ALLOCATIONS.get(k,ALLOCATIONS[None])
    for p in positions:
        symbol = p.instrument.symbol
        name = p.instrument.name
        cost_basis = p.cost_basis.total_cost
        current_value = p.current_value
        percentage = p.percent_of_portfolio
        try:
            a = allocations[symbol]["allocation"]
        except KeyError:
            a = Decimal(0.0)
        delta = percentage - a
        change_from_basis = current_value - cost_basis
        print_row([name, symbol,current_value, percentage, 
            delta, cost_basis, change_from_basis])
        total_val += current_value
        total_cb += cost_basis
        total_pct += percentage
        abs_delta += abs(delta)
        total_change_b += change_from_basis
    print_divider()
    print_row(["Total", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()
