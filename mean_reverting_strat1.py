import json
import bittrex

with open("api_key.json", 'r') as fp:
	api_key = json.load(fp)

default_version = "v1.1"

# strategy parameters
market = "ETH-XRP"
price_delta = .000006
max_quantity = 300
n_levels = 6

max_iters = 60*24
display_freq = 10

btrx = bittrex.Bittrex(api_key=api_key["api_key"], 
					   api_secret=api_key["api_secret"], 
					   calls_per_second=1/60, 
					   api_version=default_version)


# get existing orders to be ignored by strategy
existing_orders = btrx.get_open_orders(market=market)["result"]
ignore_orders = [x["OrderUuid"] for x in existing_orders]

initial_price = btrx.get_ticker(market)["result"]["Last"]

# place initial orders
for i in range(n_levels):
	btrx.buy_limit(market=market,
					quantity=max_quantity//n_levels,
					rate=initial_price - (n_levels-i)*price_delta
		)

	btrx.sell_limit(market=market,
					quantity=max_quantity//n_levels,
					rate=initial_price + (n_levels-i)*price_delta
		)

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

while True:
	for order in missing_orders:
		current_ticker = btrx.get_ticker(market)["result"]

		if order["OrderType"] == "LIMIT_SELL":
			print("Sell order filled:")
			print("price:", order["Limit"])
			btrx.buy_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=min(current_ticker["Ask"], order["Limit"] - price_delta)
				)
		elif order["OrderType"] == "LIMIT_BUY":
			print("Buy order filled:")
			print("price:", order["Limit"])
			btrx.sell_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=max(current_ticker["Bid"], order["Limit"] + price_delta)
				)
		else:
			print("Got unexpected OrderType! : " + order["OrderType"])

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
		order_prices = sorted([order["Limit"] for order in orders])
		print(order_prices)
		order_types = sorted([order["OrderType"] for order in orders])
		print(order_types)

	if n_iters > max_iters:
		break
	new_orders = []

for order in orders:
	btrx.cancel(order["OrderUuid"])