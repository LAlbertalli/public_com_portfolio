from decimal import Decimal


class PortfolioParsingException(Exception):
    pass

def portfolio_allocation_analysis(positions,allocations):
    shown_symbols = []
    for p in positions:
        symbol = p.instrument.symbol
        shown_symbols += [symbol]
        name = p.instrument.name
        cost_basis = p.cost_basis.total_cost
        current_value = p.current_value
        percentage = p.percent_of_portfolio
        try:
            a = allocations[symbol]["allocation"]
        except KeyError:
            a = Decimal('0.0')
        change_from_basis = current_value - cost_basis
        yield [name, symbol,current_value, percentage, 
            a, cost_basis, change_from_basis]

    for symbol, a in allocations.items():
        if symbol not in shown_symbols:
            shown_symbols+=[symbol]
            yield ["", symbol, Decimal('0.0'), Decimal('0.0'), 
                a['allocation'], Decimal('0.0'), Decimal('0.0')]

def parse_portfolio(portfolio):
    value = sum(i.value for i in portfolio.equity)
    cash = [i for i in portfolio.equity if i.type == 'CASH']
    if len(cash) == 1:
        cash = cash[0].value
    elif len(cash) == 0:
        cash = Decimal('0.00')
    else:
        raise PortfolioParsingException("Received more than one cash position. Aborting")
    positions = portfolio.positions
    return value, cash, positions
