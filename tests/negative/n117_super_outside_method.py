# expect: super() is supported only
class A:
    def __init__(self) -> None:
        self.x = 1

    @staticmethod
    def make() -> int:
        return super().make()
