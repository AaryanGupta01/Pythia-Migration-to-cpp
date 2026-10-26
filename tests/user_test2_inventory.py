inventory = {
    "laptop": {"price": 50000, "stock": 5},
    "mouse": {"price": 500, "stock": 20},
    "keyboard": {"price": 1500, "stock": 10},
    "monitor": {"price": 12000, "stock": 3}
}

sales = []


def calculate_total(*prices, discount=0):
    total = sum(prices)
    return total - total * discount / 100


def create_product(name, price, stock=0, **details):
    product = {
        "price": price,
        "stock": stock,
        "details": details
    }
    return name, product


def sell_product(name, quantity=1):
    if name not in inventory:
        print("Product not found")
        return

    product = inventory[name]

    if quantity <= 0:
        print("Invalid quantity")
    elif product["stock"] < quantity:
        print("Insufficient stock")
    else:
        product["stock"] -= quantity
        amount = product["price"] * quantity
        sales.append((name, quantity, amount))
        print(f"Sold {quantity} {name}: Rs. {amount}")


def show_inventory():
    for name, product in sorted(inventory.items()):
        print(
            name,
            "Price:", product["price"],
            "Stock:", product["stock"]
        )


sell_product("mouse", 3)
sell_product("laptop", 2)
sell_product("monitor", 10)
sell_product("unknown", 1)

print("\nInventory:")
show_inventory()

print("\nSales:")
for name, quantity, amount in sales:
    print(name, quantity, amount)

print("Revenue:", sum(sale[2] for sale in sales))
print("Discounted total:", calculate_total(100, 200, 300, discount=10))

name, product = create_product(
    "headphones", 2000, 5, color="black", wireless=True
)
print(name, product)

categories = {"electronics", "accessories", "electronics"}
print(sorted(categories))

try:
    quantity = int("abc")
except ValueError:
    print("Invalid number entered")

print("Remaining products:", len(inventory))

