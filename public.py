from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig

with open(".publicdotcom_key") as f:
    key = f.readline()

client = PublicApiClient(
    ApiKeyAuthConfig(api_secret_key=key), 
    config=PublicApiClientConfiguration()
    )

accounts = client.get_accounts()

for acc in accounts.accounts:
    print(acc.account_type.name, acc.account_id)

check_accounts = {
    "Traditional IRA": "5OC34877",
    "Roth IRA": "5OD57333"
}

def string_format(name, length = 40):
    if len(name) > length:
        return name[:length]
    return name.ljust(length)

def number_format(number, symbol, length = 12):
    return ("%s %s"%(number, symbol)).rjust(length)

for k,v in check_accounts.items():
    portfolio = client.get_portfolio(v)
    value = portfolio.equity[0].value
    cash = portfolio.buying_power.cash_only_buying_power
    positions = portfolio.positions
    print("\n Portfolio %s"%k)
    print("| %s | %s | %s | %s | %s |"%(
        string_format("Name"), string_format("Symbol", 10), string_format("Value", 12),
        string_format("% of portfolio",15), string_format("Cost Basis", 12)))
    for p in positions:
        symbol = p.instrument.symbol
        name = p.instrument.name
        cost_basis = p.cost_basis.total_cost
        current_value = p.current_value
        percentage = p.percent_of_portfolio
        print("| %s | %s | %s | %s | %s |"%(
            string_format(name),string_format(symbol, 10),number_format(current_value, "$"),
            number_format(percentage, "%", 15), number_format(cost_basis, "$")))
