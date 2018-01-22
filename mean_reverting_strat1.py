import json
import bittrex

with open("api_key.json", 'r') as fp:
	api_key = json.load(fp)

default_version = "v1.1"

market = "ETH-ADA"
price_delta = .000004
max_quantity = 100
n_levels = 5

max_iters = 60*24
display_freq = 10

btrx = bittrex.Bittrex(api_key=api_key["api_key"], 
					   api_secret=api_key["api_secret"], 
					   calls_per_second=1/30, 
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

# exit condition
n_failed_order_calls = 0
n_iters = 0

while True:
	
	# request open order list, filter non-strategy orders
	order_call = btrx.get_open_orders(market=market)
	if order_call["success"]:
		new_orders = [order for order in order_call["result"] if order["OrderUuid"] not in ignore_orders]
		n_failed_order_calls = 0
	else:
		n_failed_order_calls += 1
		if n_failed_order_calls > 10:
			print("failed to retrieve orders 10 consecutive times... exiting strategy")
		break
	
	# completed orders will be missing.
	new_uuids = [order["OrderUuid"] for order in new_orders]
	missing_uuids = [uuid for uuid in order_uuids if uuid not in new_uuids]
	missing_orders = [order for order in orders if order["OrderUuid"] in missing_uuids]

	current_ticker = btrx.get_ticker(market)["result"]

	for order in missing_orders:

		if order["OrderType"] == "LIMIT_SELL":
			print("Sell order filled:")
			print(order)
			btrx.buy_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=min(current_ticker["Ask"], order["Limit"] - price_delta)
				)
		else:
			print("Buy order filled:")
			print(order)
			btrx.sell_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=max(current_ticker["Bid"], order["Limit"] + price_delta)
				)

	btrx.wait()

	if len(missing_orders) > 0:
		new_orders = btrx.get_open_orders(market=market)["result"]
		orders = [order for order in new_orders if order["OrderUuid"] not in ignore_orders]
		order_uuids = [order["OrderUuid"] for order in orders]

	#assert len(order_uuids) == 2 * n_levels, "Number of strategy orders is off... got " + str(len(order_uuids))
	if len(order_uuids) != 2 * n_levels: 
		print("WARNING: got " + str(len(order_uuids)) + " orders. Expected " + str(2*n_levels)+".")
		print("number of missing orders found:", len(missing_orders))

	n_iters += 1
	if n_iters % display_freq == 0:
		print("Completed iteration " + str(n_iters))
		order_prices = sorted([order["Limit"] for order in orders])
		print(order_prices)
		order_types = sorted([order["OrderType"] for order in orders])
		print(order_types)

	if n_iters > max_iters:
		break
