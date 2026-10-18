# expect: unions other than
from typing import Union
def f(x: Union[int, str]) -> int:
    return 1
print(f(1))
