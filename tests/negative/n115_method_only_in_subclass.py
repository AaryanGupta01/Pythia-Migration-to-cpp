# expect: has no method 'bark'
class Animal:
    def __init__(self, name: str) -> None:
        self.name = name


class Dog(Animal):
    def bark(self) -> str:
        return "woof"


a: Animal = Dog("rex")
print(a.bark())
