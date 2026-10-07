import datetime
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
	if quotes[-1][0] != datetime.datetime.now(datetime.UTC).date():
		# We don't have data for today, trying from metadata
		date = ticker.history_metadata['regularMarketTime'].date()
		if date != quotes[-1][0]:
			# We have today data, appending it
			price = Decimal(
				ticker.history_metadata['regularMarketPrice']
				).quantize(Decimal('0.01'), rounding = decimal.ROUND_HALF_EVEN)
			quotes += [(date, price)]
	return quotes

def yf_validate_ticker(symbol):
	ticker = yf.Ticker(symbol)
	try:
		ticker.fast_info['currency']
		return True
	except KeyError:
		return False