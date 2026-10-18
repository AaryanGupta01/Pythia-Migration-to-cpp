# expect: '<' not supported between instances of 'P' and 'P'
class P:
    def __init__(self, x: int) -> None:
        self.x = x


ps = [P(2), P(1)]
ps.sort()
