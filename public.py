import decimal, json, os, uuid, datetime

from public_api_sdk import PreflightRequest, OrderRequest, OrderInstrument, InstrumentType, OrderSide, OrderType,\
    OrderExpirationRequest, TimeInForce, OrderStatus
from public_api_sdk.models.history import TransactionType, TransactionSubType, TransactionDirection
# from config import ALLOCATIONS, CHECK_ACCOUNTS
from decimal import Decimal
from time import sleep
from scipy.optimize import newton

from helper.arghelper import command, exec_command, parse_args
from helper.tableprint import choose_table_format, string_format, number_format,\
    print_divider, print_header, print_row
from helper.public_api import get_client
from helper.config_helper import validate_allocations, get_accounts, get_account, get_target_allocation
from helper.portfolio import parse_portfolio

from commands import show, rebalance, recover, CheckPointer

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

def main():
    args = parse_args()

    checkpoints = CheckPointer.try_load()
    if checkpoints and args.action != "recover":
        print("There is a pending rebalancing transaction. Run with action 'recover' to continue")
        return

    if not validate_allocations():
        return

    client = get_client()
    if client is None:
        return

    account = args.account
    run = args.run

    return exec_command(args.action, locals())


if __name__ == "__main__":
    main()