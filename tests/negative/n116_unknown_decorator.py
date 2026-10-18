# expect: decorator @functools.lru_cache
import math


class Fib:
    @functools.lru_cache
    def fib(self, n: int) -> int:
        return n
