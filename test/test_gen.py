from urgent.parser_wrap import parse
from urgent.compiler import Compiler, Instruction
from pprint import pprint
ast = parse("""
module A.I

let x = 1

infixl + 5

let + = 20

let z = 2
let g = 1
do z + g

let + = x -> y -> 0
let f = (1, a) -> a

let g = f

let aa = g (1, 2)

let v = (1 or 2) -> 1

do 1 match
    1 => 2
    
""")

comp = Compiler()
comp.compile_module(ast)


pprint(comp.code)