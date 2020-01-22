from timeit import timeit
from sijuiacion_lang.lowering import sij, Lower

defun = sij.Defun("", "", [], "", ["argf"], [
    sij.Load("argf"),
    sij.Label("loop"),
    sij.Unpack(2),
    sij.Call(1),
    sij.Unpack(2),
    sij.GotoNEq("loop"),
    sij.Return()
])

code, _ = Lower({}).lower("", "", 1, "", [], [], [defun, sij.Return()])

scheduler = eval(code)
print(scheduler)


def schd(f, arg):
    while True:
        token, a = f(arg)
        if token:
            return a
        f, arg = a


#
#
def rec1(x):
    if x is 0:
        return 0
    return rec1(x - 1) + x


#
#
def rec2(x):
    def apply(y):
        if x is 0:
            return True, y
        return False, (x + y, scheduler((x - 1, rec2)))

    return True, apply


import dis
dis.show_code(scheduler)
dis.show_code(schd)

#
#
# print(scheduler((0, scheduler((500, rec2)))))
print(timeit('rec1(500)', globals=globals(), number=500))
print(
    timeit('scheduler((0, scheduler((500, rec2))))',
           globals=globals(),
           number=500))
