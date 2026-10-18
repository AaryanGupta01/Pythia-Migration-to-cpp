# @staticmethod, @classmethod (cls(...), cls.X), @property (+ setter), class attributes read through the
# class, self and instances, and written through the class


class Temperature:
    unit = "C"
    created = 0
    ABS_ZERO: float = -273.15

    def __init__(self, celsius: float) -> None:
        self._c = celsius
        Temperature.created += 1

    @property
    def celsius(self) -> float:
        return self._c

    @celsius.setter
    def celsius(self, value: float) -> None:
        if value < Temperature.ABS_ZERO:
            raise ValueError("below absolute zero")
        self._c = value

    @property
    def fahrenheit(self) -> float:
        return self._c * 9 / 5 + 32

    @staticmethod
    def c_to_f(c: float) -> float:
        return c * 9 / 5 + 32

    @classmethod
    def from_fahrenheit(cls, f: float) -> "Temperature":
        return cls((f - 32) * 5 / 9)

    @classmethod
    def describe_class(cls) -> str:
        return f"unit={cls.unit} created={cls.created}"

    def label(self) -> str:
        return f"{self.celsius:.1f}{self.unit} ({self.c_to_f(self._c):.1f}F)"


class Counter:
    total = 0
    step: int = 2

    def __init__(self) -> None:
        self.hits = 0

    def bump(self) -> int:
        self.hits += self.step
        Counter.total += self.step
        return self.hits


t = Temperature(25.0)
print(t.celsius, t.fahrenheit, Temperature.c_to_f(100.0), t.unit, Temperature.unit)
t.celsius = 30.0
t.celsius += 1.5
print(t.label(), t.celsius)
u = Temperature.from_fahrenheit(212.0)
print(round(u.celsius, 6), Temperature.describe_class())
Temperature.unit = "deg"
print(t.label(), Temperature.created, t.created)
a, b = Counter(), Counter()
print(a.bump(), a.bump(), b.bump(), Counter.total, a.total, b.step)
Counter.step = 10
print(a.bump(), Counter.total)
try:
    t.celsius = -300.0
except ValueError as e:
    print("error:", e)
print(t.celsius)
