# expect: mutable default
from dataclasses import dataclass


@dataclass
class Box:
    items: list[int] = []
