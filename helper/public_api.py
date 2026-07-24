from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig

def get_client():
    try:
        with open(".publicdotcom_key") as f:
            key = f.readline()
    except:
        print("Error loading the key for public.com from the file .publicdotcom_key")
        return None
    return PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=key),
        config=PublicApiClientConfiguration()
        )

def parse_portfolio(portfolio):
    value = sum(i.value for i in portfolio.equity)
    cash = [i for i in portfolio.equity if i.type == 'CASH']
    if len(cash) == 1:
        cash = cash[0].value
    elif len(cash) == 0:
        cash = Decimal('0.00')
    else:
        raise Exception("Received more than one cash position. Aborting")
    positions = portfolio.positions
    return value, cash, positions