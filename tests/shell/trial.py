class A:
    a = 10
    b = {"a": a, "b": 20}


class B(A):
    pass


b = B()
print(b.a)
print(b.b)
