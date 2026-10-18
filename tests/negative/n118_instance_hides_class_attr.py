# expect: hides class attribute
class Config:
    debug = False

    def __init__(self) -> None:
        self.level = 1


c = Config()
c.debug = True
