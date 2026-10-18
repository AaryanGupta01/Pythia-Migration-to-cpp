# expect: UnboundLocalError
count = 0
def bump() -> None:
    count += 1
bump()
