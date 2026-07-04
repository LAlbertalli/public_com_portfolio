from decimal import Decimal

CHECK_ACCOUNTS = {
#    "Account1": "5xxxx",
#    "Account2": "5yyyy"
}

ALLOCATIONS = {
    None: { # None for the allocation for all accounts
#        "XXX": { # Ticker Symbol
#           "allocation": Decimal(100.0), # Target Allocation (use decimal) 
#           "tags": ["bond", "Total"] # (Tags)
#        }, 
    },
    "Account2": { # Account specific the allocation
#        "XXX": { # Ticker Symbol
#           "allocation": Decimal(100.0), # Target Allocation (use decimal) 
#           "tags": ["bond", "Total"] # (Tags)
#        }, 
    },
}
