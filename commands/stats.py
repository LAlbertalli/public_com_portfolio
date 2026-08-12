import datetime
import decimal
from copy import deepcopy
from decimal import Decimal

from public_api_sdk.models import (
    BarPeriod,
    InstrumentType,
)
from public_api_sdk.models.history import (
    TransactionDirection,
    TransactionSubType,
    TransactionType,
)
from scipy.optimize import newton

from helper.arghelper import command
from helper.config_helper import get_accounts
from helper.portfolio import parse_portfolio


class PriceHistory:
    def __init__(self):
        self.client = None
        self.parsed_history = {}

    def set_client(self, client):
        self.client = client

    def close_for_symbol_at(self, symbol, date):
        if symbol not in self.parsed_history:
            self.fetch_history_for_symbol(symbol, date - datetime.timedelta(days = 7))
        if date < self.parsed_history[symbol][0][0]:
            self.fetch_history_for_symbol(symbol, date - datetime.timedelta(days = 7))
        prev = None
        for d,q in self.parsed_history[symbol]:
            if d==date:
                return q
            if d>date:
                return prev
            prev = q
        #If running out of fetched history return last value but give a warning if of by too much
        if (date-d).days > 3:
            print("WARNING, quotes for symbol %s is outdated by %d days" % (symbol, (date-d).days))
        return prev

    def fetch_history_for_symbol(self, symbol, date):
        if self.client is None:
            raise Exception("set_client not called before using the class")
        data = self.client.get_bars(
            symbol = symbol,
            instrument_type = InstrumentType.EQUITY,
            period = BarPeriod.SINCE_PURCHASE,
            purchase_date = date
        )
        bars = data.regular_market.bars
        quotes = [(self.parse_date(i.timestamp),i.close) for i in bars]
        self.parsed_history[symbol] = sorted(quotes, key = lambda x:x[0])

    def parse_date(self, date_string):
        return datetime.datetime.fromisoformat(date_string[:-6]).date()

price_history = PriceHistory()

class PortfolioHistory:
    def __init__(self, client, account_name, account_id):
        self.client = client
        self.account_name = account_name
        self.account_id = account_id

        self.populate_history()

    def fetch_transaction_history(self):
        history = self.client.get_history(account_id=self.account_id)
        self.transactions = []
        for t in history.transactions:
            if t.type == TransactionType.MONEY_MOVEMENT and t.sub_type in (
                TransactionSubType.MISC, TransactionSubType.DEPOSIT,
                TransactionSubType.WITHDRAWAL, TransactionSubType.TRANSFER):
                day = t.timestamp.date()
                net_amount = t.net_amount
                action = 'deposit' if t.direction == TransactionDirection.INCOMING else 'withdrawal'
                self.transactions += [(action, day, net_amount,None, None)]
            if t.type == TransactionType.MONEY_MOVEMENT and \
                    t.sub_type == TransactionSubType.DIVIDEND:
                day = t.timestamp.date()
                net_amount = t.net_amount
                self.transactions += [('dividend', day, net_amount,None, None)]
            if t.type == TransactionSubType.TRADE:
                day = t.timestamp.date()
                net_amount = t.net_amount
                symbol = t.symbol
                qty = t.quantity
                self.transactions += [('trade', day, net_amount,symbol, qty)]

        self.transactions = sorted(self.transactions, key = lambda x:x[1])

    def fill_net_value(self):
        price_history.set_client(self.client)
        for day in self.history:
            balance = self.history[day]['balance']
            value = balance['cash']
            for symbol, qty in balance["portfolio"].items():
                price = price_history.close_for_symbol_at(symbol, day)
                try:
                    value += price*qty
                except:
                    print(symbol, qty, day, price)
                    raise
            balance["net_value"] = value.quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)

    def populate_history(self):
        self.today = datetime.datetime.now(datetime.UTC).date()
        self.fetch_transaction_history()

        self.history = {}
        balance = {
            'cash': Decimal("0.00"),
            "portfolio": {},
            "net_value": Decimal("0.00"),
        }
        for action, day, value, symbol, qty in self.transactions:
            if day not in self.history:
                self.history[day] = {
                    "balance": None,
                    "in_out_flow": Decimal("0.00"),
                    "dividends": Decimal("0.00"),
                }
            match action:
                case 'withdrawal':
                    balance['cash'] -= value
                    self.history[day]['in_out_flow'] -= value
                case 'deposit':
                    balance['cash'] += value
                    self.history[day]['in_out_flow'] += value
                case 'dividend':
                    balance['cash'] += value
                    self.history[day]['in_out_flow'] += value
                case 'trade':
                    balance['cash'] += value
                    new_qty = balance['portfolio'].get(symbol, Decimal("0.00000")) + qty
                    balance['portfolio'][symbol] = new_qty
            self.history[day]['balance'] = deepcopy(balance)

        if self.today not in self.history:
            self.history[self.today] = {
                    "balance": deepcopy(balance),
                    "in_out_flow": Decimal("0.00"),
                    "dividends": Decimal("0.00"),
                }

        self.fill_net_value()

    def get_all_in_out(self, balance = False, today = False):
        for action, day, value, _, _ in self.transactions:
            if action in ("deposit", "withdrawal"):
                if balance:
                    yield action, day, value, self.history[day]
                else:
                    yield action, day, value
        if today:
            today_value = self.history[self.today]["balance"]["net_value"]
            if balance:
                yield "final", self.today, today_value, self.history[self.today]
            else:
                yield "final", self.today, today_value

    def get_today_value(self, balance = False):
        today_value = self.history[self.today]["balance"]["net_value"]
        if balance:
            return today_value, self.history[self.today]
        else:
            return today_value

    def get_balance_in_out_days(self, today = False):
        prev_day = None
        for _, day, _value, balance in self.get_all_in_out(balance = True, today = today):
            if day == prev_day:
                continue
            prev_day = day
            yield day, balance


def simulate_etf(history, etf):
    qty = Decimal("0.00000")
    for action, date, value in history.get_all_in_out():
        price = price_history.close_for_symbol_at(etf, date)
        q = (value / price).quantize(Decimal('0.00001'), rounding = decimal.ROUND_HALF_EVEN)
        if action == "withdrawal":
            q = -1*q
        qty += q
    final_price = price_history.close_for_symbol_at(etf, history.today)
    net_value = (qty * final_price).quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
    return net_value

def calculate_irr(history):
    def irr_target(r, dates, cash_flows):
        t0 = dates[0]
        # Calculate fractional years from the first deposit date
        years = [(d - t0).days / 365.0 for d in dates]
        return sum(cf / ((1 + r) ** y) for cf, y in zip(cash_flows, years))

    dates, cash_flows = zip(*((d,float(-v if a!= "final" else v)) for a,d,v in history.get_all_in_out(today = True)))
    return newton(irr_target, 0.1, args=(dates, cash_flows))

def calculate_twrr_atwrr(history):
    balances = list(history.get_balance_in_out_days(today = True))
    twrr = Decimal("1.0000")
    for i in range(len(balances) - 1):
        initial_balance = balances[i][1]
        final_balance = balances[i+1][1]
        change = (final_balance["balance"]["net_value"] - final_balance["in_out_flow"]) - initial_balance["balance"]["net_value"]
        return_rate = change/initial_balance["balance"]["net_value"]+ Decimal("1.00")
        twrr *= return_rate
    years = Decimal((balances[-1][0] - balances[0][0]).days) / 365
    atwrr = twrr**(1/years) - Decimal("1.000")
    twrr -= Decimal("1.0000")
    return twrr, atwrr

def history_and_stats(client, account_name, account_id, compare):
    history = PortfolioHistory(client, account_name, account_id)

    print("Account %s:"%account_name)
    for action, day, value in history.get_all_in_out(today = True):
        match action:
            case "deposit":
                print("[%s] Deposit of %.2f$"%(day, value))
            case "withdrawal":
                print("[%s] Withdrawal of %.2f$"%(day, value))
            case "final":
                print("[%s] Final value: %.2f$"%(day, value))

    final_value, _, _ = parse_portfolio(client.get_portfolio(account_id=account_id))
    print("\nWARNING! There is a discrepancy between calculated net_value and reported current net_value")
    print("This happens because public.com reports the value in real time while stats looks at closing price")
    print("The difference is usually small but need to be considered when larger than normal")
    if abs(final_value - value)/final_value > Decimal("0.005"):
        print("Value discrepancy: %.2f$ %.2f$\n"%(final_value, value))
    print()
    final_value = value

    # IRR/MWRR
    irr = calculate_irr(history)
    print("Interal Rate of Return: %.2f%%"%(irr*100))

    # TWRR
    twrr, atwrr = calculate_twrr_atwrr(history)
    print("Time Weighted Rate of Return: %.2f%%"%(twrr*100))
    print("Annualized Time Weighted Rate of Return: %.2f%%\n\n"%(atwrr*100))

    if compare:
        etfs = compare.split(",")
        for etf in etfs:
            sim_value = simulate_etf(history, etf)
            diff = final_value - sim_value
            pdiff = diff/final_value*100
            print("Investing in %s would have yield %.2f$. A Net difference of %.2f$ (%.2f%%)" % (etf, sim_value, diff, pdiff))


@command
def stats(client, account, compare):
    """Show account deposit history and calculate performance statistics
    -c --compare: compares against target ETF. Multiple accepted as comma separated list"""
    for k,v in get_accounts():
        if not account or k == account:
            history_and_stats(client, k, v, compare)
