import collections
import json

import bittrex

api_key = "xxx"
secret = "xxx"
version = "v1.1"

market_currencies = ["BTC", "ETH", "USDT"]

btrx = bittrex.Bittrex(api_key=api_key, 
					   api_secret=secret, 
					   calls_per_second=1, 
					   api_version=version)

def cancel_all(market=None):
	"""
	Cancels all your open orders for given market(s). If no markets 
	are passed, cancels all open orders.
	"""
	orders = btrx.get_open_orders(market=market)["result"]
	for order in orders:
		btrx.cancel(order["OrderUuid"])


def get_distribution(filename=None, verbose=True, btc_threshold=1e-8):
	"""
	Saves your balance distribution. 
	"""
	balances = btrx.get_balances()["result"]
	new_balances = collections.defaultdict(dict)

	total_btc_value = 0

	for coin in balances:
		if coin["Balance"] > 0:
			new_balances[coin["Currency"]]["Balance"] = coin["Balance"]
			btc_price = btrx.get_ticker("BTC-" + coin["Currency"])["result"]
			if btc_price is None:
				if coin["Currency"] == "BTC":
					btc_price = 1
				else:
					# assume it's tether...
					btc_price = btrx.get_ticker(coin["Currency"] + "-BTC")["result"]["Ask"]**-1
			else:
				btc_price = btc_price["Bid"]
			new_balances[coin["Currency"]]["BTC Price"] = btc_price
			total_btc_value += coin["Balance"] * btc_price 

	proportions = {}
	for key, dic in new_balances.items():
		btc_value = dic["Balance"] * dic["BTC Price"]
		if verbose: print(key + " : " + str(btc_value/total_btc_value))
		new_balances[key]["Proportion"] = btc_value/total_btc_value
		proportions[key] = btc_value/total_btc_value


	if filename:
		with open(filename, 'w') as fp:
			json.dump(proportions, fp)


def buy_distribution(filename, starting_coin="BTC", amount=None):
	"""
	buy `amount` worth of `starting_coin` distributed as seen in `filename`.
	## WARNING: WILL USE ALL AVAILABLE `starting_coin` IF NO `amount` IS ENTERED
	
	For this function, trading will be done at MARKET, but we could
	implement limit orders here as well

	currently does not support tether
	"""
	if amount is None:
		amount = btrx.get_balance(starting_coin)["result"]["Available"]
	
	with open(filename, 'r') as fp:
		distribution = json.load(fp)

	for coin, prop in distribution.items():
		if coin == "USDT": continue
		price = btrx.get_ticker(coin)["result"]["Ask"]
		btrx.trade_buy(market=starting_coin + "-" + coin, 
							order_type="MARKET",
							quantity=amount*prop/price,
							)


def all_in(buy_coin, sell_coin=None, remember_prev_proportions=True):
	"""
	Cancel all orders for currencies passed into `sell_coin` and then 
	trades all available funds for those currencies for `buy_coin.` If 
	nothing is passed into `sell_coin`, all your currencies will be exchanged 
	for `buy_coin` at market price. USE WITH CAUTION.
	"""
	if sell_coin is None:
		sell_coin = []
		balances = btrx.get_balances()["result"]
		for coin in balances:
			if coin["Balance"] > 0:
				sell_coin.append(coin["Currency"])

	if type(sell_coin) is not list:
		sell_coin = [sell_coin,]

	for coin in sell_coin:
		for m in market_currencies:
			cancel_all(m + "-" + sell_coin)

		### TODO there are cases that will break this
		if buy_coin in market_currencies:
			balance = btrx.get_balance(sell_coin)["result"]["Available"]
			btrx.trade_buy(market=buy_coin + "-" + sell_coin, 
							order_type="MARKET",
							quantity=balance,
							)
		
