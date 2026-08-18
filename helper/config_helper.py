from decimal import Decimal

from config.config import ALLOCATIONS, GROUPINGS

try:
    from config.config import ACCOUNTS
except ModuleNotFoundError:
    from config.config import CHECK_ACCOUNTS
    ACCOUNTS = CHECK_ACCOUNTS
    print("Deprecation Warning. CHECK_ACCOUNTS is deprecated, replace with ACCOUNTS")

def get_target_allocation(name):
    return ALLOCATIONS.get(name,ALLOCATIONS[None])

def get_accounts():
    yield from ACCOUNTS.items()

def get_account(name):
    return ACCOUNTS.get(name, None)

def get_group(name):
    return [(n,ACCOUNTS[n]) for n in GROUPINGS.get(name, [])]

def validate_configs():
    return all((
        validate_accounts(),
        validate_allocations(),
        validate_groupings(),
        ))

def validate_accounts():
    return True

def validate_allocations():
    error = False
    for name,allocs in ALLOCATIONS.items():
        total_pct = Decimal('0.0')
        for symbol, a in allocs.items():
            try:
                total_pct += Decimal(a["allocation"])
            except: #NOQA
                pass
            if type(a["allocation"]) != Decimal:
                error = True
                print(
                    f"Error validating the configuration for {(name or "Default (None)")}. \
The allocation should be of type Decimal. '{symbol}' is not")
        if total_pct != Decimal('100.0'):
            error = True
            print(f"Error validating the configuration for {(name or "Default (None)")}. \
Total allocation should be 100%. Found {total_pct:.2}%")
    return not error

def validate_groupings():
    error = False
    for group, accounts in GROUPINGS.items():
        if group in ACCOUNTS:
            print(f"Error validating the configuration for group {group}. \
Group name cannot be also an account name")
            error = True
        if type(accounts) != list:
            print(f"Error validating the configuration for group {group}. \
The group definition should be a list of accounts")
            error = True
        else:
            for account in accounts:
                if account not in ACCOUNTS:
                    print(f"Error validating the configuration for group {group}. \
Account {account} does not exists" % (group, account))
                    error = True
    return not error
