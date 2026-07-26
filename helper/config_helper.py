from decimal import Decimal

from config.config import ALLOCATIONS, CHECK_ACCOUNTS

def get_target_allocation(name):
    return ALLOCATIONS.get(name,ALLOCATIONS[None])

def get_accounts():
	for name, aid in CHECK_ACCOUNTS.items():
		yield name, aid

def get_account(name):
	return CHECK_ACCOUNTS[name]

def validate_allocations():
    error = False
    for name,allocs in ALLOCATIONS.items():
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