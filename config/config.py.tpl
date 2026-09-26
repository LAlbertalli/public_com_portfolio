from decimal import Decimal

ACCOUNTS = {
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

GROUPINGS = { # Groups to use for the --group option
#     "Alias": ["Account1", "Account2"], # Each account should appear in the ACCOUNTS dict above
#     "Alias2": ["Account2", "Account3"],
}

COMPARISONS = { # Named comparisons for the --compare option
#    "Alias": ["Ticker1", "Ticker2", "Ticker3"], # List of valid Ticker Symbol
#    "Alias2": ["Ticker1", "Ticker4", "Ticker5"],
}


HISTORY_IGNORE = { # Set of transaction to ignore for stats calculation. 
#    "Transaction_ID1", # The transaction id is the id received in transaction. Looks like a UUID
#    "Transaction_ID2", # Use comments to document the change
}