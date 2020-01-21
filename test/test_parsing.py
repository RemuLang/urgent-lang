from urgent.parser_wrap import parse
from pprint import pprint
pprint(parse("""
open a.b
"""))


pprint(parse("""
def f = 1
def f = let g = 2 in c
"""))


pprint(parse("""
def f = 1
def f = 
    let g = 2
    let y = 2
    in g + y
"""))
