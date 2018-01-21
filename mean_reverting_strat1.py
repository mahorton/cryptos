import json

import bittrex

with open("api_key.json", 'r') as fp:
	api_key = json.load(fp)

default_version = "v1.1"

market = "ETH-ADA"
price_delta = .0002
max_quantity = 100
n_levels = 3

max_iters = 60*24

btrx = bittrex.Bittrex(api_key=api_key["api_key"], 
					   api_secret=api_key["api_secret"], 
					   calls_per_second=1, 
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
	btrx.wait()

	# request open order list, filter non-strategy orders
	order_call = btrx.get_open_orders(market=market)
	orders = []
	if order_call["success"]:
		new_orders = [order for order in order_call["result"] if order["OrderUuid"] not in ignore_orders]
		n_failed_order_calls = 0
	else:
		n_failed_order_calls += 1
		if n_failed_order_calls > 10:
			print("failed to retrieve orders 10 consecutive times... exiting strategy")
		break
	
	# completed orders will be missing.
	missing_orders = [order for order in new_orders if order["OrderUuid"] not in order_uuids]
	if len(missing_orders) == 0:
		continue

	current_ticker = btrx.get_ticker(market)["result"]

	for order in missing_orders:
		if order["OrderType"] == "LIMIT_SELL":
			btrx.buy_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=min(current_ticker["Ask"], order["Limit"] - price_delta)
				)
		else:
			btrx.sell_limit(market=market,
							quantity=max_quantity//n_levels,
							rate=max(current_ticker["Bid"], order["Limit"] + price_delta)
				)

	new_orders = btrx.get_open_orders(market=market)["result"]
	orders = [order for order in new_orders if order["OrderUuid"] not in ignore_orders]
	order_uuids = [order["OrderUuid"] for order in orders]

	assert len(order_uuids) == 2 * n_levels, "Number of strategy orders is off... got " + str(order_uuids)
	n_iters += 1

	if n_iters > max_iters:
		break