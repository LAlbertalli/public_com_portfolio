import decimal
from decimal import Decimal

import yfinance as yf


def yf_fetch_history_for_symbol(symbol, date):
	ticker = yf.Ticker(symbol)
	history = ticker.history(start = date)['Close']
	quotes = [
		(
			t.date(), 
			Decimal(c).quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
		) for t,c in history.to_dict().items()]
	quotes = sorted(quotes, key = lambda x:x[0])
	return quotes