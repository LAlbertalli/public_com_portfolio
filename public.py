import argparse, decimal, json, os, uuid

from public_api_sdk import PublicApiClient, PublicApiClientConfiguration, ApiKeyAuthConfig,\
    PreflightRequest, OrderRequest, OrderInstrument, InstrumentType, OrderSide, OrderType,\
    OrderExpirationRequest, TimeInForce, OrderStatus
from config import ALLOCATIONS, CHECK_ACCOUNTS
from decimal import Decimal
from time import sleep


FORMAT_SHOW = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("% of portfolio", 15, lambda x: number_format(x, "%", 15)),
    ("Diff", 12, lambda x: number_format(x, "%")),
    ("Cost Basis", 12, lambda x: number_format(x, "$")),
    ("Gain/Loss", 12, lambda x: number_format(x, "$"))
    ]


FORMAT_REBALANCE = [
    ("Name", 40, lambda x: string_format(x)),
    ("Symbol", 10, lambda x: string_format(x, 10)),
    ("Value", 12, lambda x: number_format(x, "$")),
    ("Buy Sell", 10, lambda x: string_format(x, 10)),
    ("Amount", 12, lambda x: number_format(x, "$")),
    ("New Balance", 12, lambda x: number_format(x, "$")),
    ("New %", 12, lambda x: number_format(x, "%")),
    ]


# Formatter helper functions
FORMAT = FORMAT_SHOW

def choose_table_format(format):
    global FORMAT
    FORMAT = format


def string_format(name, length = 40):
    if len(name) > length:
        return name[:length]
    return name.ljust(length)


def number_format(number, symbol, length = 12):
    return ("%s %s"%(number, symbol)).rjust(length)


def print_divider():
    div_len = sum(i for _,i,_ in FORMAT) + 3 * (len(FORMAT)-1) + 4
    print("-"* div_len)


def print_header(account):
    print("\n\n Portfolio %s\n"%account)
    print_divider()
    print("| "+ " | ".join([string_format(i,j) for i,j,_ in FORMAT]) + " |")
    print_divider()


def print_row(row):
    print("| " + " | ".join(f(r) for r,(_,_,f) in zip(row,FORMAT)) + " |")


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


def get_target_allocation(name):
    return ALLOCATIONS.get(name,ALLOCATIONS[None])



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


def print_account_info(portfolio, name):
    allocations = get_target_allocation(name)
    value, cash, positions = parse_portfolio(portfolio)

    total_val = Decimal('0.0')
    total_cb = Decimal('0.0')
    total_pct = Decimal('0.0')
    abs_delta = Decimal('0.0')
    total_change_b = Decimal('0.0')

    choose_table_format(FORMAT_SHOW)

    print_header(name)
    shown_symbols = []
    for r in portfolio_allocation_analysis(positions, allocations):
        name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
        delta = alloc - percentage
        print_row([name, symbol,current_value, percentage, delta, 
            cost_basis, change_from_basis])
        total_val += current_value
        total_cb += cost_basis
        total_pct += percentage
        abs_delta += abs(delta)
        total_change_b += change_from_basis

    print_divider()
    print_row(["Total stock", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()
    cash_percent = (cash/value*100).quantize(Decimal("0.01"), 
        rounding = decimal.ROUND_HALF_EVEN)
    print_row(["Cash", "", cash, cash_percent, 
        cash_percent, 0.0, 0.0])
    print_divider()
    total_val += cash
    total_pct += cash_percent
    abs_delta += abs(cash_percent)
    print_row(["Total", "", total_val, total_pct, 
            abs_delta, total_cb, total_change_b])
    print_divider()

    # suggest rebalance
    cash_reb = cash > Decimal('20.0')
    abs_delts_reb = abs_delta > len(allocations) * Decimal('0.15')
    if abs_delts_reb or cash_reb:
        print("Suggested to rebalance this portfolio. Causes:")
        if abs_delts_reb:
            print("- Portfolio is out of balance of %.2f%%. Max is %.2f%%"%(
                abs_delta, len(allocations) * Decimal('0.15')))
        if cash_reb:
            print("- Portfolio has excessive cash balance %.2f$. Max is 20$"%(cash))


class CheckPointer:
    filename = ".checkpoint.json"
    def __init__(self, sell, buy, cash_value, account, orders = None):
        self.status = {
            "account": account,
            "sell": [(s, str(a)) for s,a in sell],
            "buy": [(s, str(a)) for s,a in buy],
            "orders": orders or [],
            "cash_value": str(cash_value)
        }
        self._write()

    @classmethod
    def try_load(cls):
        try:
            with open(cls.filename) as f:
                status = json.load(f)
                r = cls(status["sell"],
                    status["buy"],
                    status["cash_value"],
                    status["account"],
                    orders = status["orders"]
                    )
                return r
        except FileNotFoundError:
            return None

    def _write(self):
        with open(self.filename, "w") as f:
            json.dump(self.status, f)

    def new_order(self, order_id, symbol):
        self.status["orders"] += [{
            "order_id": order_id,
            "symbol": symbol,
            "done": False,
            "amount": "0.0",
            "cancelled": False,
        }]
        self._write()

    def order_done(self, order_id, amount):
        try:
            i = [i for i in self.status["orders"] if i["order_id"] == order_id][0]
        except IndexError:
            return
        i["amount"] = str(amount)
        i["done"] = True
        self._write()

    def order_cancelled(self, order_id):
        try:
            i = [i for i in self.status["orders"] if i["order_id"] == order_id][0]
        except IndexError:
            return
        i["cancelled"] = True
        i["done"] = True
        self._write()

    def done(self):
        if not self.all_done:
            raise Exception("done() called but not all transaction are completed")
        os.remove(self.filename)

    @property
    def account(self):
        return self.status["account"]

    @property
    def order_ids(self):
        return dict(
            (i["symbol"], i["order_id"]) for i in self.status["orders"]
            if not i["cancelled"])

    @property
    def running_amount(self):
        return sum(Decimal(i["amount"]) for i in self.status["orders"]
            if i["done"] and not i["cancelled"])

    @property
    def all_done(self):
        return all(i["done"] for i in self.status["orders"])

    @property
    def cash_value(self):
        return Decimal(self.status["cash_value"])

    @property
    def sell(self):
        for s,a in self.status["sell"]:
            yield s,Decimal(a)

    @property
    def buy(self):
        for s,a in self.status["buy"]:
            yield s,Decimal(a)

    @property
    def order_inflight(self):
        return [i["order_id"] for i in self.status["orders"]
            if not i["done"] and not i["cancelled"]]


class Rebalancer:
    def __init__(self, client, name, account_id):
        self.client = client
        self.name = name
        self.account_id = account_id
        self.portfolio = client.get_portfolio(self.account_id)

    def preflight_sell(self, sell):
        print ("Preflying the sell requests for account %s: "% self.name)
        for symbol, value in sell:
            print("Preflying symbol = %s"%symbol, end = "")
            req = PreflightRequest(
                instrument = OrderInstrument(
                    symbol = symbol,
                    type = InstrumentType.EQUITY),
                order_side = OrderSide.SELL,
                amount = -value,
                order_type = OrderType.MARKET,
                expiration = OrderExpirationRequest(
                    time_in_force = TimeInForce.DAY
                    )
                )
            res = self.client.perform_preflight_calculation(req, account_id=self.account_id)
            print("done")
            proceed = res.estimated_proceeds
            cost_and_fees = -value - proceed
            print("Proceed from %s: %.2f$ - Fees: %.2f$"%(symbol, proceed, cost_and_fees))
            yield symbol, proceed, cost_and_fees


    def calculate_rebalance(self):
        allocations = get_target_allocation(self.name)
        value, cash, positions = parse_portfolio(self.portfolio)

        self.cash_value = cash
        self.sell = []
        self.buy = []

        cost_and_fees = Decimal('0.0')

        for r in portfolio_allocation_analysis(positions, allocations):
            name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
            delta = alloc - percentage
            if delta < Decimal(-0.05): # Don't sell if difference is less than 0.05%
                sell_amt = current_value/percentage*delta
                sell_amt = sell_amt.quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
                self.sell += [(symbol, sell_amt)]
            if delta > Decimal('0.0'): # Always buy everything underindexed
                self.buy += [(symbol, delta)]
        if len(self.buy) == 0:
            print("Error, found no underindexed fund to buy")
            return False

        for symbol, proceed, cf in self.preflight_sell(self.sell):
            self.cash_value += proceed
            cost_and_fees += cf

        total_delta = sum(delta for _, delta in self.buy)
        self.buy = [(symbol, (delta/total_delta)) for symbol, delta in self.buy]

        # Print
        ops = dict(self.sell+[(i,(j*self.cash_value).quantize(
            Decimal('0.01'), rounding =decimal.ROUND_HALF_EVEN)) for i,j in self.buy])
        total_cval = Decimal('0.0')
        total_ops = Decimal('0.0')
        total_new = Decimal('0.0')
        total_pct = Decimal('0.0')
        choose_table_format(FORMAT_REBALANCE)
        print_header(name)
        shown_symbols = []
        for r in portfolio_allocation_analysis(positions, allocations):
            "Name","Symbol","Value","Buy Sell","Amount","New Balance","New %"
            name, symbol,current_value, percentage, alloc, cost_basis, change_from_basis = r
            op = ops.get(symbol, Decimal('0.0'))
            buy_sell = "Buy" if op > Decimal('0.0') else "Sell" if op < Decimal('0.0') else "Nothing"
            new_v = current_value+op
            new_pct = (new_v/value*100).quantize(Decimal('0.01'), rounding =decimal.ROUND_HALF_EVEN)
            print_row([name, symbol,current_value, buy_sell, op, new_v, new_pct])
            total_cval += current_value
            total_ops += op
            total_new += new_v
            total_pct += new_pct

        print_divider()
        print_row(["Total", "", total_cval, "",
                total_ops, total_new, total_pct])
        print_divider()
        print("Total cost and fees %.2f $"%cost_and_fees)
        return (len(self.sell) + len(self.buy) > 0)

    def wait_orders(self, checkpoints):
        orders_failed = False
        while True:
            in_flight = checkpoints.order_inflight
            if len(in_flight) == 0:
                break
            for order_id in in_flight:
                print("Checking order %s"%order_id)
                res = self.client.get_order(order_id, self.account_id)
                symbol = res.instrument.symbol
                status = res.status
                average_price = res.average_price or Decimal("0.00")
                filled_quantity = res.filled_quantity or Decimal("0.00")
                if status == OrderStatus.FILLED:
                    amount = (average_price * filled_quantity).quantize(
                        Decimal("0.01"), rounding = decimal.ROUND_HALF_EVEN)
                    checkpoints.order_done(order_id, amount)
                    print("Order %s for symbol %s executed for %.2f"%(order_id, symbol, amount))
                elif status in (OrderStatus.CANCELLED,
                    OrderStatus.PENDING_CANCEL, OrderStatus.REJECTED,
                    OrderStatus.EXPIRED, OrderStatus.QUEUED_CANCELLED):
                    checkpoints.order_cancelled(order_id)
                    print("Order %s for symbol %s cancelled"%(order_id, symbol))
                    orders_failed = True
            sleep(1)
        return orders_failed

    def place_orders(self, orders, checkpoints):
        for symbol, amount, side in orders:
            if symbol not in checkpoints.order_ids: # Check if not placed yet
                order_id = str(uuid.uuid4())
                if amount == Decimal("0.00"):
                    # Skip order and consider it executed
                    checkpoints.new_order(order_id, symbol)
                    checkpoints.order_done(order_id, Decimal("0.00"))
                    continue
                req = OrderRequest(
                    instrument = OrderInstrument(
                        symbol = symbol,
                        type = InstrumentType.EQUITY
                    ),
                    order_side = side,
                    amount = amount,
                    order_type = OrderType.MARKET,
                    expiration = OrderExpirationRequest(
                        time_in_force = TimeInForce.DAY
                    ),
                    order_id = order_id
                )
                res = self.client.place_order(req, account_id=self.account_id)
                print("Placing order to %s %.2f$ of %s" % (
                    ("buy" if side == OrderSide.BUY else "sell"), amount, symbol))
                checkpoints.new_order(order_id, symbol)

    def execute_operations(self, checkpoints = None):
        if checkpoints:
            chk = checkpoints
        else:
            chk = CheckPointer(self.sell, self.buy, self.cash_value, self.name)

        # First place sell orders
        def sell_orders(checkpoints):
            for symbol, amount in checkpoints.sell:
                # Skip rebalancing if below $1.00
                if -amount < Decimal("1.00"):
                    amount = Decimal("0.00")
                yield symbol, -amount, OrderSide.SELL
        self.place_orders(sell_orders(chk), chk)

        # Wait for order completion
        orders_failed = self.wait_orders(chk)

        if orders_failed is True:
            print("Rebalancing Failed selling. Launch the rebalancer to restart")
            return

        _, cash_value, _ = parse_portfolio(self.client.get_portfolio(self.account_id))
        # Now place buy orders
        def buy_orders(checkpoints, cash_value):
            running_cash_value = cash_value
            for symbol, perc in checkpoints.buy:
                amount = (cash_value * perc).quantize(
                        Decimal("0.01"), rounding = decimal.ROUND_HALF_EVEN)
                if amount < Decimal("1.00"):
                    # Skip rebalancing if below $1.00
                    amount = Decimal("0.00")
                amount = min(amount, running_cash_value)
                running_cash_value -= amount
                # If the residual cash value would be too small, add the residual to this
                if running_cash_value < Decimal("1.00") and amount + running_cash_value >= Decimal("1.00"):
                    amount += running_cash_value
                    running_cash_value = Decimal("0.00")
                yield symbol, amount, OrderSide.BUY
                # Note, there are corner cases were cash would be left uninvested, but less
                # than 1$. Good enough
        self.place_orders(buy_orders(chk, cash_value), chk)

        # Wait for order completion
        orders_failed = self.wait_orders(chk)
    
        if orders_failed is True:
            print("Rebalancing Failed selling. Launch the rebalancer to restart")
            return

        chk.done()

def parse_args():
    parser = argparse.ArgumentParser(
        description='Help me monitor my portfolio on Public.com and keep it balanced',
        )
    parser.add_argument("action", choices=['show', 'rebalance', 'recover'], 
        default = 'show', 
        help = "Action to be execute:\n\
    - show: Show the current portfolio\n\
    - rebalance: Rebalance the portfolio. Notice, without --run,\
 it will only simulate the rebalance\n\
    - recover: It recovers a previously failed rebalance. \
Note: it will ignore any other flags",
        nargs = '?')
    parser.add_argument("-r", "--run", action = 'store_true',
        help = "For rebalance, actually use the public apis to run the planned actions")

    parser.add_argument("-a", '--account', 
        help = "Limit to the specified account")

    return parser.parse_args()


def show(client, account):
    for k,v in CHECK_ACCOUNTS.items():
        if not account or k == account:
            portfolio = client.get_portfolio(v)
            print_account_info(portfolio, k)


def rebalance(client, account, run):
    for k,v in CHECK_ACCOUNTS.items():
        if not account or k == account:
            rebalancer = Rebalancer(client, k, v)
            ok = rebalancer.calculate_rebalance()
            if ok and run is True:
                rebalancer.execute_operations()

def recover(client, checkpoints):
    r = Rebalancer(client, checkpoints.account, CHECK_ACCOUNTS[checkpoints.account])
    r.execute_operations(checkpoints = checkpoints)

def validate_allocations(allocations):
    error = False
    for name,allocs in allocations.items():
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


def main():
    args = parse_args()

    chk = CheckPointer.try_load()
    if chk and args.action != "recover":
        print("There is a pending rebalancing transaction. Run with action 'recover' to continue")
        return
    
    try:
        with open(".publicdotcom_key") as f:
            key = f.readline()
    except:
        print("Error loading the key for public.com from the file .publicdotcom_key")
        return

    if not validate_allocations(ALLOCATIONS):
        return

    client = PublicApiClient(
        ApiKeyAuthConfig(api_secret_key=key),
        config=PublicApiClientConfiguration()
        )
    if args.action == "show":
        show(client, args.account)
    elif args.action == "rebalance":
        rebalance(client, args.account, args.run)
    elif args.action == "recover":
        recover(client, chk)

if __name__ == "__main__":
    main()