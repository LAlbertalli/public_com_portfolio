import datetime
import decimal
from copy import deepcopy
from decimal import Decimal
from itertools import chain

import matplotlib.pyplot as plt
import numpy as np
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
from helper.config_helper import (
    HISTORY_IGNORE,
    TickerNotFoundException,
    get_account,
    get_accounts,
    get_comparison,
    get_group,
)
from helper.portfolio import parse_portfolio
from helper.yfinance import yf_fetch_history_for_symbol


class PriceHistoryClientException(Exception):
    pass

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
            print(f"WARNING, quotes for symbol {symbol} is outdated by {(date-d).days} days")
        return prev

    def fetch_history_for_symbol(self, symbol, date):
        if self.client is None:
            raise PriceHistoryClientException("set_client not called before using the class")
        # If it is a closed fund, not found on Public, use YFinance
        if len(symbol) == 5 and symbol[-1] == 'X':
            quotes = yf_fetch_history_for_symbol(symbol, date)
            self.parsed_history[symbol] = quotes
            return
        # Prefer public.com otherwise
        data = self.client.get_bars(
            symbol = symbol,
            instrument_type = InstrumentType.EQUITY,
            period = BarPeriod.SINCE_PURCHASE,
            purchase_date = date
        )
        # But if ticker not on public, try Yahoo! Finance
        if data.total_expected_bars == 0:
            quotes = yf_fetch_history_for_symbol(symbol, date)
            self.parsed_history[symbol] = quotes
            return

        bars = data.regular_market.bars
        quotes = [(self.parse_date(i.timestamp),i.close) for i in bars]
        # if multiple data points for the same day, keep the last one
        quotes = sorted(quotes, key = lambda x:x[0])
        # TODO: Should use pandas?
        idx = list(enumerate(quotes))
        idx = [max(i for i,(j,_) in idx if j.date() == n) for n in {n.date() for _,(n,_) in idx}]
        quotes = [(i.date(), c) for e,(i,c) in enumerate(quotes) if e in idx]
        self.parsed_history[symbol] = quotes

    def parse_date(self, date_string):
        return datetime.datetime.fromisoformat(date_string[:-6])

price_history = PriceHistory()

class PortfolioHistory:
    def __init__(self, client, account_name, account_id, *args):
        self.client = client
        self.account_names = (account_name,) + args[::2]
        self.account_ids = (account_id,) + args[1::2]

        self.populate_history()

    def fetch_transaction_history(self, name, account_id):
        history = self.client.get_history(account_id = account_id)
        for t in history.transactions:
            if t.id in HISTORY_IGNORE:
                continue
            if t.type == TransactionType.MONEY_MOVEMENT and t.sub_type in (
                TransactionSubType.MISC, TransactionSubType.DEPOSIT,
                TransactionSubType.WITHDRAWAL, TransactionSubType.TRANSFER):
                day = t.timestamp.date()
                net_amount = t.net_amount
                action = 'deposit' if t.direction == TransactionDirection.INCOMING else 'withdrawal'
                self.transactions += [(name, action, day, net_amount,None, None)]
            if t.type == TransactionType.MONEY_MOVEMENT and \
                    t.sub_type == TransactionSubType.DIVIDEND:
                day = t.timestamp.date()
                net_amount = t.net_amount
                self.transactions += [(name, 'dividend', day, net_amount,None, None)]
            if t.type == TransactionSubType.TRADE:
                day = t.timestamp.date()
                net_amount = t.net_amount
                symbol = t.symbol
                qty = t.quantity
                self.transactions += [(name, 'trade', day, net_amount,symbol, qty)]

        self.transactions = sorted(self.transactions, key = lambda x:x[2])

    def fill_net_value(self):
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
        self.transactions = []
        for name, account_id in zip(self.account_names,self.account_ids):
            self.fetch_transaction_history(name, account_id)

        self.history = {}
        balance = {
            'cash': Decimal("0.00"),
            "portfolio": {},
            "net_value": Decimal("0.00"),
        }
        for _, action, day, value, symbol, qty in self.transactions:
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
                    self.history[day]['dividends'] += value
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
        for name, action, day, value, _, _ in self.transactions:
            if action in ("deposit", "withdrawal"):
                if balance:
                    yield name, action, day, value, self.history[day]
                else:
                    yield name, action, day, value
        if today:
            today_value = self.history[self.today]["balance"]["net_value"]
            if balance:
                yield None, "final", self.today, today_value, self.history[self.today]
            else:
                yield None, "final", self.today, today_value

    def get_today_value(self, balance = False):
        today_value = self.history[self.today]["balance"]["net_value"]
        if balance:
            return today_value, self.history[self.today]
        else:
            return today_value

    def get_balance_in_out_days(self, today = False):
        prev_day = None
        for _, _, day, _value, balance in self.get_all_in_out(balance = True, today = today):
            if day == prev_day:
                continue
            prev_day = day
            yield day, balance

    def get_net_value_end_of_week(self, start = None):
        hstart = start
        start = min(self.history.keys()) # Note, in theory is sorted. Min is more readable
        if hstart is None:
            hstart = start + datetime.timedelta(
                days = ((-3 - start.weekday()) if (4 - start.weekday()) > 0 else (4 - start.weekday())))
        dates = (hstart+datetime.timedelta(days=i) for i in range(0,(self.today-hstart).days,7))
        dates = sorted(chain(self.history.keys(), dates))
        bcash = {'cash' : Decimal('0.00'), 'portfolio': {}}
        prev = hstart - datetime.timedelta(days = 1) # start
        for d in dates:
            if d == prev:
                continue
            prev = d
            if d in self.history:
                bcash = self.history[d]['balance']
            if d.weekday() != 4:
                continue
            value = bcash['cash']+sum(qty*price_history.close_for_symbol_at(sym,d) for sym,qty in bcash['portfolio'].items())
            value = value.quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
            yield d, value



def simulate_etf_history(history, etf):
    qty = Decimal("0.00000")
    for _, action, date, value in history.get_all_in_out():
        price = price_history.close_for_symbol_at(etf, date)
        q = (value / price).quantize(Decimal('0.00001'), rounding = decimal.ROUND_HALF_EVEN)
        if action == "withdrawal":
            q = -1*q
        qty += q
        yield date, qty

def simulate_etf_end_of_week(history, etf, start = None):
    etf_history = {i:j for i,j in simulate_etf_history(history, etf)}
    hstart = start
    start = min(etf_history.keys())
    today = history.today
    if hstart is None:
        hstart = start + datetime.timedelta(
            days = ((-3 - start.weekday()) if (4 - start.weekday()) > 0 else (4 - start.weekday())))
    dates = (hstart+datetime.timedelta(days=i) for i in range(0,(today-hstart).days,7))
    dates = sorted(chain(etf_history.keys(), dates))
    qty = Decimal('0.00000')
    prev = hstart - datetime.timedelta(days = 1) # start
    for d in dates:
        if d == prev:
            continue
        prev = d
        if d in etf_history:
            qty = etf_history[d]
        if d.weekday() != 4:
            continue
        price = price_history.close_for_symbol_at(etf, d)
        value = (qty * price).quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
        yield d, value

def simulate_etf(history, etf):
    for _, qty in simulate_etf_history(history, etf): pass
    final_price = price_history.close_for_symbol_at(etf, history.today)
    net_value = (qty * final_price).quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
    return net_value

def trendline(dates, values):
    x = [(i - dates[0]).days/365 for i in dates]
    slope, intercept = np.polyfit(x, [float(i) for i in values], 1)
    trend_values = np.poly1d([slope,intercept])(x)
    return slope, intercept, trend_values

def plot_time_series(data, tickers, cash_history):
    fig, (ax1, ax2, ax3) = plt.subplots(3,1, figsize=(12,9))
    colormap = {name: plt.cm.tab20.colors[e%len(plt.cm.tab20.colors)] for e, name in enumerate(["Portfolio"] + tickers)}
    dates, values = zip(*cash_history)
    ax1.step(dates, values, label = "Cash in and out", where = 'post', color = colormap["Portfolio"], linestyle = "--")
    dates = list(data.keys())
    pvalues = [i['Portfolio'] for i in data.values()]
    ax1.plot(dates, pvalues, label = "Portfolio", color = colormap["Portfolio"])
    cash_values = []
    i = 0
    for d in dates:
        try:
            while d >= cash_history[i+1][0]:
                i += 1
        except IndexError:
            pass
        cash_values+=[cash_history[i][1]]
    ax2.plot(dates,[i-j for i,j in zip(pvalues, cash_values)], label = "Portfolio", color = colormap["Portfolio"])
    for t in tickers:
        values = [i[t] for i in data.values()]
        ax1.plot(dates, values, label = t, color = colormap[t])
        ax2.plot(dates, [i-j for i,j in zip(values, cash_values)], label = t, color = colormap[t])
        values_d = [(i-j)/i*100 if i!=Decimal("0.00") else Decimal("0.00") for i,j in zip(pvalues, values)]
        ax3.plot(dates, values_d,
            label = t, color = colormap[t])
        slope, intercept, trend_values = trendline(dates, values_d)
        ax3.plot(dates, trend_values, label = f"{t} y = {slope:.2f}x + {intercept:.2f}", color = colormap[t], linestyle = "--")

    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid()
    ax1.set_ylabel("$")
    ax1.set_title("Equivalent Value")
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid()
    ax2.set_ylabel("$")
    ax2.set_title("Gain/Loss")
    ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax3.grid()
    ax3.set_ylabel("%")
    ax3.set_title("Difference (trendline is annualized)")
    fig.tight_layout()
    plt.show()

def calculate_irr(history):
    def irr_target(r, dates, cash_flows):
        t0 = dates[0]
        # Calculate fractional years from the first deposit date
        years = [(d - t0).days / 365.0 for d in dates]
        return sum(cf / ((1 + r) ** y) for cf, y in zip(cash_flows, years))

    dates, cash_flows = zip(*((d,float(-v if a!= "final" else v)) for n,a,d,v in history.get_all_in_out(today = True)))
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

def history_and_stats_group(client, group_name, ids, compare):
    flatten_ids = (i for j in ids for i in j)
    history = PortfolioHistory(client, *flatten_ids)

    print(f"Group {group_name}:")
    cash_history = []
    for account, action, day, value in history.get_all_in_out(today = True):
        match action:
            case "deposit":
                print(f"[{day}] Deposit of {value:.2f}$ in {account}")
                cash_history += [(day, value)]
            case "withdrawal":
                print(f"[{day}] Withdrawal of {value:.2f}$ from {account}")
                cash_history += [(day, -value)]
            case "final":
                print(f"[{day}] Final value: {value:.2f}$")

    final_value = Decimal("0.00")
    for _, i in ids:
        f_value, _, _ = parse_portfolio(client.get_portfolio(account_id=i))
        final_value += f_value
    print("\nWARNING! There is a discrepancy between calculated net_value and reported current net_value")
    print("This happens because public.com reports the value in real time while stats looks at closing price")
    print("The difference is usually small but need to be considered when larger than normal")
    if abs(final_value - value)/final_value > Decimal("0.005"):
        print(f"Value discrepancy: {final_value:.2f}$ {value:.2f}$\n")
    print()
    final_value = value

    # IRR/MWRR
    irr = calculate_irr(history)
    print(f"Internal Rate of Return: {irr*100:.2f}%")

    # TWRR
    twrr, atwrr = calculate_twrr_atwrr(history)
    print(f"Time Weighted Rate of Return: {twrr*100:.2f}%")
    print(f"Annualized Time Weighted Rate of Return: {atwrr*100:.2f}%\n\n")

    if compare:
        data = {d: {"Portfolio": v} for d,v in history.get_net_value_end_of_week()}
        start = min(data.keys())
        cash_history = [(start, Decimal("0.00"))] + cash_history + [(history.today, Decimal("0.00"))]
        acc = Decimal("0.00")
        cash_history = [(d, acc := acc + v) for d,v in cash_history]
        for ticker in compare:
            sim_value = simulate_etf(history, ticker)
            for d,v in simulate_etf_end_of_week(history, ticker):
                data[d][ticker] = v
            diff = final_value - sim_value
            pdiff = diff/final_value*100
            print(f"Investing in {ticker} would have yield {sim_value:.2f}$. A Net difference of {diff:.2f}$ ({pdiff:.2f}%)")
        plot_time_series(data, compare, cash_history)
        

def history_and_stats(client, account_name, account_id, compare):
    history = PortfolioHistory(client, account_name, account_id)

    print(f"Account {account_name}:")
    cash_history = []
    for _, action, day, value in history.get_all_in_out(today = True):
        match action:
            case "deposit":
                print(f"[{day}] Deposit of {value:.2f}$")
                cash_history += [(day, value)]
            case "withdrawal":
                print(f"[{day}] Withdrawal of {value:.2f}$")
                cash_history += [(day, -value)]
            case "final":
                print(f"[{day}] Final value: {value:.2f}$")

    final_value, _, _ = parse_portfolio(client.get_portfolio(account_id=account_id))
    print("\nWARNING! There is a discrepancy between calculated net_value and reported current net_value")
    print("This happens because public.com reports the value in real time while stats looks at closing price")
    print("The difference is usually small but need to be considered when larger than normal")
    if abs(final_value - value)/final_value > Decimal("0.005"):
        print(f"Value discrepancy: {final_value:.2f}$ {value:.2f}$\n")
    print()
    final_value = value

    # IRR/MWRR
    irr = calculate_irr(history)
    print("Internal Rate of Return: %.2f%%"%(irr*100))

    # TWRR
    twrr, atwrr = calculate_twrr_atwrr(history)
    print("Time Weighted Rate of Return: %.2f%%"%(twrr*100))
    print("Annualized Time Weighted Rate of Return: %.2f%%\n\n"%(atwrr*100))

    if compare:
        data = {d: {"Portfolio": v} for d,v in history.get_net_value_end_of_week()}
        start = min(data.keys())
        cash_history = [(start, Decimal("0.00"))] + cash_history + [(history.today, Decimal("0.00"))]
        acc = Decimal("0.00")
        cash_history = [(d, acc := acc + v) for d,v in cash_history]
        for ticker in compare:
            sim_value = simulate_etf(history, ticker)
            for d,v in simulate_etf_end_of_week(history, ticker):
                data[d][ticker] = v
            diff = final_value - sim_value
            pdiff = diff/final_value*100
            print(f"Investing in {ticker} would have yield {sim_value:.2f}$. A Net difference of {diff:.2f}$ ({pdiff:.2f}%)")
    plot_time_series(data, compare, cash_history)


@command
def stats(client, account, compare, group):
    """Show account deposit history and calculate performance statistics
    -c --compare: compares against target ETF. Can use name from config or multiple accepted as comma-separated list
    -g --group: Show the transactions and statistics for a group of accounts all together
    """
    
    price_history.set_client(client) # Set the client when starting

    try:
        compare = get_comparison(compare)
    except TickerNotFoundException as e:
        print(e.message)
        return

    if group:
        ids = get_group(group)
        if ids == []:
            print(f"ERROR: Group {group} not found")
            return
        history_and_stats_group(client, group, ids, compare)
    elif account:
        account_id = get_account(account)
        if account_id is None:
            print(f"ERROR: Account {account} not found")
            return
        history_and_stats(client, account, account_id, compare)
    else:
        for name, aid in get_accounts():
            history_and_stats(client, name, aid, compare)
