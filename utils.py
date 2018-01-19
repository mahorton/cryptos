import collections
import json

import bittrex

api_key = "xxx"
secret = "xxx"
default_version = "v1.1"

btrx = bittrex.Bittrex(api_key=api_key, 
					   api_secret=secret, 
					   calls_per_second=1, 
					   api_version=default_version)

t_cost = .0025
markets = []
market_dicts = btrx.get_markets()["result"]
for m in market_dicts:
	markets.append(m["MarketName"])


def cancel_all(market=None):
	"""
	Cancels all your open orders for given market(s). If no markets 
	are passed, cancels all open orders.
	"""
	orders = btrx.get_open_orders(market=market)["result"]
	if orders is None: return
	for order in orders:
		btrx.cancel(order["OrderUuid"])


def _get_user_confirmation(message=""):
	yes = {'yes','y', 'ye'}
	no = {'no','n'}
	#print(message)

	choice = input(message).lower()
	if choice in yes:
	   return True
	elif choice in no:
	   return False
	else:
	   sys.stdout.write("Please respond with 'yes' or 'no'")


def _get_market(buy_coin, sell_coin):
	# returns the market name for a buy and sell coin along with a trade direction
	market = False
	for m in markets:
		if buy_coin in m and sell_coin in m:
			market = m
			break

	#assert market, "no market name containin both "+buy_coin+" and "+sell_coin+"."
	if not market: 
		print("no market name containin both "+buy_coin+" and "+sell_coin+".")
		return False, False

	if market.split("-")[0] == buy_coin:
		return market, "sell"
	else:
		return market, "buy"


def get_distribution(filename=None, verbose=True, btc_threshold=1e-8):
	"""
	Saves your balance distribution. 
	"""
	balances = btrx.get_balances()["result"]
	new_balances = collections.defaultdict(dict)

	total_btc_value = 0

	for coin in balances:
		if coin["Balance"] > btc_threshold:
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
	"""
	if amount is None:
		amount = btrx.get_balance(starting_coin)["result"]["Available"]
	
	with open(filename, 'r') as fp:
		distribution = json.load(fp)

	for coin, prop in distribution.items():

		market, direction = get_market(coin, starting_coin)
		if not market:
			continue

		if direction == "buy"
			price = btrx.get_ticker(market)["result"]["Ask"]
			btrx.buy_limit(market=market, 
								#order_type="MARKET",
								quantity=amount*prop/price,
								rate=price
								)
		else:
			price = btrx.get_ticker(market)["result"]["Bid"]
			assert False
			### This still needs fixing I think... too buzzed to think about it
			btrx.sell_limit(market=market, 
								#order_type="MARKET",
								quantity=amount*prop,
								rate=price
								)





def all_in(buy_coin, sell_coins="all", persistant=False, cancel=True, remember_prev_proportions=False):
	"""
	Cancel all orders (if `cancel` is True) for currencies passed into `sell_coin` and then 
	trades all available funds for those currencies for `buy_coin.` If 
	nothing is passed into `sell_coin`, all your currencies will be exchanged 
	for `buy_coin` at market price. USE WITH CAUTION.
	"""
	if sell_coins == "all":
		sell_coins = []
		balances = btrx.get_balances()["result"]
		for coin in balances:
			if coin["Balance"] > 0:
				sell_coins.append(coin["Currency"])

	if type(sell_coins) is not list:
		sell_coins = [sell_coins,]

	# call `get_distributions()` to save previous distribution as .json file
	if remember_prev_proportions:
		get_distribution("dist_before_all_in.json", verbose=False)

	# requre user confirmation here
	if not _get_user_confirmation("Confirm market trade " + str(sell_coins) + " for " + buy_coin +". (Enter yes or no) "):
		return "Trade Canceled."

	if persistant and buy_coin != "BTC":
		no_markets = []	
		for sell_coin in sell_coins:
			market, direction = _get_market(buy_coin, sell_coin)
			if not market:
				no_markets.append(sell_coin)
		# recurse once to sell all coins without market into BTC before continuing
		all_in("BTC", sell_coins=no_markets, persistant=False, cancel=cancel, remember_prev_proportions=False)
		sell_coins = list(set(sell_coins + ["BTC",]))
		# wait for trade to hopefully finish... 
		btrx.wait()

	# start selling
	for sell_coin in sell_coins:
		print("Trading out " + sell_coin + " ... ")
		# first cancel existing orders
		if cancel:
			for m in market_currencies:
				cancel_all(m + "-" + sell_coin)

		# identify market and the direction of trade. ignore if market not found 
		market, direction = _get_market(buy_coin, sell_coin)
		if not market:
			continue

		if direction == "sell":
			balance = btrx.get_balance(sell_coin)["result"]["Available"]
			print("previous balance:",balance)
			#btrx.api_version = "v2.0"
			rate = btrx.get_ticker(market)["result"]["Bid"]
			print("selling at rate:", rate)
			btrx.sell_limit(market=market, 
							#order_type="MARKET",
							quantity=balance,
							rate=rate
							)
			#btrx.api_version = default_version
		else:
			balance = btrx.get_balance(sell_coin)["result"]["Available"]
			print("previous balance:", balance)
			rate = btrx.get_ticker(market)["result"]["Ask"]
			print("buying at rate:", rate)
			btrx.buy_limit(market=market, 
							#order_type="MARKET",
							quantity=balance/rate - (balance/rate)*t_cost,
							rate=rate
							)
			
	# 		
