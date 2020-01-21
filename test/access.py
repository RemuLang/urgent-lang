from timeit import timeit
import lupa
from lupa import LuaRuntime
lua = LuaRuntime(unpack_returned_tuples=True)
lua_func = lua.eval('function(x) return x + 1 end')
print(lua_func(1))


def f(_):
    return x + 1


for each in range(100000):
    globals()['x{}'.format(each)] = each
x = 2


def g(x=x):
    return x + 1


print(timeit("f(1)", globals=dict(f=f), number=10000000))
print(timeit("f(1)", globals=dict(f=g), number=10000000))
print(timeit("f(1)", globals=dict(f=lua_func), number=10000000))
