import json
import collections
import bittrex

with open("api_key.json", 'r') as fp:
	api_key = json.load(fp)

default_version = "v1.1"

# strategy parameters
market = "ETH-XRP"
price_delta = .00005
max_quantity = 600
n_levels = 3

max_iters = 60*24
display_freq = 10

btrx = bittrex.Bittrex(api_key=api_key["api_key"], 
					   api_secret=api_key["api_secret"], 
					   calls_per_second=1/60, 
					   api_version=default_version)

level_quantity = max_quantity//n_levels
# get existing orders to be ignored by strategy
existing_orders = btrx.get_open_orders(market=market)["result"]
ignore_orders = [x["OrderUuid"] for x in existing_orders]

ticker = btrx.get_ticker(market)["result"]
initial_price = ticker["Last"]

profit_per_flip = price_delta * (level_quantity) - (.005*(level_quantity)*initial_price)
print("Approximate profit per flip: "+str(profit_per_flip)+" "+market.split("-")[0]+".")


# place initial orders
for i in range(n_levels):
	btrx.buy_limit(market=market,
					quantity=level_quantity,
					rate=min(ticker["Ask"], initial_price - (n_levels-i)*price_delta)
		)

	btrx.sell_limit(market=market,
					quantity=level_quantity,
					rate=max(ticker["Bid"], initial_price + (n_levels-i)*price_delta)
		)
	ticker = btrx.get_ticker(market)["result"]

# identify which orders are for this strategy
new_orders = btrx.get_open_orders(market=market)["result"]
orders = [order for order in new_orders if order["OrderUuid"] not in ignore_orders]
order_uuids = [order["OrderUuid"] for order in orders]

# make sure we have our orders
if len(order_uuids) != 2 * n_levels:
	print("WARNING: got " + str(len(order_uuids)) + " orders. Expected " + str(2*n_levels)+".")
	print("Aborting before entering strategy...")
	for order in orders:
		btrx.cancel(order["OrderUuid"])
	assert False
else:
	print("Initial orders placed... entering strategy.")

# initialize stuff
n_iters = 0
missing_orders = []
missing_uuids = []
new_orders = []
n_buy_orders = n_levels
n_sell_orders = n_levels
majority_order = None
n_flips = 0
profit = 0

while True:
	for order in missing_orders:
		current_ticker = btrx.get_ticker(market)["result"]

		if order["OrderType"] == "LIMIT_SELL":
			print("Sell order filled:")
			print("price:", order["Limit"])
			btrx.buy_limit(market=market,
							quantity=level_quantity,
							rate=min(current_ticker["Ask"], order["Limit"] - price_delta)
				)
			n_sell_orders -= 1
			n_buy_orders += 1
			if majority_order == "LIMIT_BUY": 
				n_flips += 1
				profit += price_delta*level_quantity - .0025*level_quantity*(2*order["Limit"]-price_delta)

		elif order["OrderType"] == "LIMIT_BUY":
			print("Buy order filled:")
			print("price:", order["Limit"])
			btrx.sell_limit(market=market,
							quantity=level_quantity,
							rate=max(current_ticker["Bid"], order["Limit"] + price_delta)
				)
			n_sell_orders += 1
			n_buy_orders -= 1
			if majority_order == "LIMIT_SELL": 
				n_flips += 1
				profit += price_delta*level_quantity - .0025*level_quantity*(2*order["Limit"]+price_delta)

		else:
			print("Got unexpected OrderType! : " + order["OrderType"])
		
		if n_buy_orders > n_sell_orders: 
			majority_order = "LIMIT_BUY"
		elif n_buy_orders < n_sell_orders:
			majority_order = "LIMIT_SELL"
		else:
			majority_order = None

	sub_iters = 0
	while len(new_orders) != len(missing_orders):
		sub_iters += 1
		new_order_call = btrx.get_open_orders(market=market)
		new_orders = [order for order in new_order_call["result"] if order["OrderUuid"] not in ignore_orders
																	and order["OrderUuid"] not in order_uuids]
		if sub_iters > 20:
			print("Failed to get new orders... got " + str(len(new_orders))+", expected "+str(len(missing_orders)))
			break

	orders = [order for order in orders if order["OrderUuid"] not in missing_uuids]
	orders += new_orders
	order_uuids = [order["OrderUuid"] for order in orders] 
	assert len(orders) == 2 * n_levels

	btrx.wait()

	new_order_call = btrx.get_open_orders(market=market)
	new_orders = [order for order in new_order_call["result"] if order["OrderUuid"] not in ignore_orders]
	new_order_uuids = [order["OrderUuid"] for order in new_orders]

	missing_uuids = [uuid for uuid in order_uuids if uuid not in new_order_uuids]
	missing_orders = [order for order in orders if order["OrderUuid"] in missing_uuids]

	n_iters += 1
	if n_iters % display_freq == 0:
		print("Completed iteration " + str(n_iters))
		print("number of successful flips:", n_flips)
		print("resulting profit:", profit)
		print("remaining orders:")
		order_prices = sorted([order["Limit"] for order in orders])
		print(order_prices)
		order_types = sorted([order["OrderType"] for order in orders])
		print(order_types)

	if n_iters > max_iters:
		break
	new_orders = []

for order in orders:
	btrx.cancel(order["OrderUuid"])