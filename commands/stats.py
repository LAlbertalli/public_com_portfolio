import datetime

from public_api_sdk.models.history import (
    TransactionSubType,
    TransactionDirection,
    TransactionType,  
)

from scipy.optimize import newton

from helper.arghelper import command
from helper.config_helper import get_accounts
from helper.portfolio import parse_portfolio


def history_and_stats(client, account_name, account_id):
    history = client.get_history(account_id=account_id)
    value, _, _ = parse_portfolio(client.get_portfolio(account_id=account_id))
    today = datetime.datetime.now(datetime.UTC)
    transactions = []
    for t in history.transactions:
        if t.type == TransactionType.MONEY_MOVEMENT and t.sub_type in (
            TransactionSubType.MISC, TransactionSubType.DEPOSIT,
            TransactionSubType.WITHDRAWAL, TransactionSubType.TRANSFER):
            transactions+=[(
                t.timestamp,
                t.net_amount * (-1 if t.direction == TransactionDirection.INCOMING else 1)
                )]
    for d,v in transactions:
        if v>0:
            print("[%s] Withdrawal of %.2f$"%(d.date(), v))
        else:
            print("[%s] Deposit of %.2f$"%(d.date(), -v))
    print("[%s] Final value: %.2f$"%(today.date(), value))

    transactions += [(today, value)]
    dates, cash_flows = zip(*((i,float(j)) for i,j in transactions))

    def irr_target(r, dates, cash_flows):
        t0 = dates[0]
        # Calculate fractional years from the first deposit date
        years = [(d - t0).days / 365.0 for d in dates]
        return sum(cf / ((1 + r) ** y) for cf, y in zip(cash_flows, years))
    irr = newton(irr_target, 0.1, args=(dates, cash_flows))
    print("Interal Rate of Return: %.2f%%"%(irr*100))


@command
def stats(client, account):
    """Show account deposit history and calculate performance statistics"""
    for k,v in get_accounts():
        if not account or k == account:
            history_and_stats(client, k, v)
