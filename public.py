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

from commands import show, rebalance, recover, CheckPointer, stats


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