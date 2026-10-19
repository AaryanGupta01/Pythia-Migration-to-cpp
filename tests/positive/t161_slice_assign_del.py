# PySub 1.4: slice assignment and del of list items
a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
a[2:4] = [20, 30, 40]
print(a)
a[:2] = []
print(a)
a[1:1] = [7, 7]
print(a)
a[-2:] = [1]
print(a)
a[10:20] = [5]
print(a)
a[1:] = a
print(len(a))
del a[0]
print(a[:3])
del a[1:3]
print(a[:3])
del a[-1]
print(len(a))
xs: list[int] = [1, 2, 3]
try:
    del xs[7]
except IndexError as e:
    print(e)
