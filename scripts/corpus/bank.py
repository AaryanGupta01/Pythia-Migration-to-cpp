class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
        self.history = []

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amount
        self.history.append(("deposit", amount))

    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        self.history.append(("withdraw", amount))

    def __str__(self):
        return f"{self.owner}: ${self.balance:.2f}"


acct = BankAccount("Alice", 100)
acct.deposit(50)
try:
    acct.withdraw(500)
except ValueError as e:
    print("Error:", e)
acct.withdraw(30)
print(acct)
for kind, amount in acct.history:
    print(f"  {kind:<10}{amount:>8.2f}")
