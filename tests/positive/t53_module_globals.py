# PySub 1.3: module-level variables visible inside functions, `global`, shared module state
MOD = 10 ** 9 + 7
DIGITS = ["zero", "one", "two", "three"]
GRAPH: dict[int, list[int]] = {1: [2, 3], 2: [4], 3: [4], 4: []}
counter = 0
memo: dict[int, int] = {}
log: list[str] = []


def spell(n: int) -> str:
    return DIGITS[n]


def mulmod(a: int, b: int) -> int:
    return a * b % MOD


def reachable(start: int) -> list[int]:
    seen: list[int] = [start]
    stack: list[int] = [start]
    while len(stack) > 0:
        node = stack.pop()
        for nxt in GRAPH[node]:
            if nxt not in seen:
                seen.append(nxt)
                stack.append(nxt)
    return seen


def tick() -> int:
    global counter
    counter += 1
    log.append("tick " + str(counter))
    return counter


def fib(n: int) -> int:
    if n < 2:
        return n
    if n in memo:
        return memo[n]
    r = fib(n - 1) + fib(n - 2)
    memo[n] = r
    return r


def reset() -> None:
    global counter, log
    counter = 100
    log = ["reset"]


def uses_late() -> int:
    return LATE * 2


print(spell(2), mulmod(123456789, 987654321), reachable(1))
tick()
tick()
print(counter, log, fib(80), len(memo))
reset()
tick()
print(counter, log)
LATE = 21
print(uses_late())
del_me = 5


def shadow(counter: int) -> int:
    del_me = counter + 1
    return del_me


print(shadow(7), counter, del_me)


def too_early() -> int:
    return NOT_YET + 1


print(too_early())
NOT_YET = 1
