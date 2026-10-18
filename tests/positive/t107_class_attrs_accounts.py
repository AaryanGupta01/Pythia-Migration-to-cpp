# Class attributes read through self / instances / the class, redefined in subclasses (dispatch on the run-time
# class), instance attributes initialised from a class attribute, method chaining, bank-account style classes
from typing import Optional


class Animal:
    sound = "..."
    legs: int = 4
    population = 0

    def __init__(self, name: str) -> None:
        self.name = name
        self.population += 1          # instance field initialised from the class attribute
        self.population += 10

    def speak(self) -> str:
        return f"{self.name} says {self.sound} on {self.legs} legs"

    def clone(self) -> "Animal":
        return Animal(self.name + "2")


class Dog(Animal):
    sound = "woof"

    def fetch(self) -> str:
        return self.name + " fetches"


class Bird(Animal):
    sound = "tweet"
    legs = 2


class Parrot(Bird):
    def speak(self) -> str:
        return "Polly: " + super().speak()


zoo: list[Animal] = [Animal("generic"), Dog("rex"), Bird("tweety"), Parrot("polly")]
for a in zoo:
    print(a.speak(), a.population, a.sound, a.legs)
print(Animal.population, Dog.sound, Bird.legs, Parrot.sound, Parrot.legs)
d = Dog("fido")
c = d.clone()
print(c.speak(), isinstance(c, Dog), isinstance(d, Animal), type(c) == Animal, type(d) is Dog)
x: Optional[Animal] = None
print(isinstance(x, Animal), x is None)
x = zoo[1]
if isinstance(x, Dog):
    print(x.fetch())
by_name: dict[str, Animal] = {}
for a in zoo:
    by_name[a.name] = a
print(by_name["rex"].speak(), len(by_name))
pairs = [(1, zoo[0]), (2, zoo[1])]
for n, an in pairs:
    print(n, an.name)


class Account:
    interest: float = 0.02

    def __init__(self, owner: str, balance: float = 0.0) -> None:
        self.owner = owner
        self.balance = balance
        self.history: list[float] = []

    def deposit(self, amount: float) -> "Account":
        if amount <= 0:
            raise ValueError("deposit must be positive")
        self.balance += amount
        self.history.append(amount)
        return self

    def withdraw(self, amount: float) -> None:
        if amount > self.balance:
            raise ValueError(f"insufficient funds: {self.balance:.2f} < {amount:.2f}")
        self.balance -= amount
        self.history.append(-amount)

    def __str__(self) -> str:
        return f"{self.owner}: {self.balance:.2f}"


class Savings(Account):
    interest = 0.05

    def add_interest(self) -> None:
        self.deposit(self.balance * self.interest)


acc = Savings("ann", 100.0)
acc.deposit(50.0).deposit(25.5)
acc.add_interest()
print(acc, acc.history, Account.interest, acc.interest)
accounts: list[Account] = [acc, Account("bob")]
for ac in accounts:
    print(str(ac), f"[{ac}]")
try:
    accounts[1].withdraw(10.0)
except ValueError as e:
    print("error:", e)
print(accounts[1].history, len(accounts))


class Base:
    tag = "base"

    def __init__(self) -> None:
        self.tag = self.tag + "!"


class Derived(Base):
    tag = "derived"


print(Base().tag, Derived().tag, Base.tag, Derived.tag)
