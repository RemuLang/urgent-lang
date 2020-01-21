from urgent.parser_wrap import parse
from urgent.evaluator import State
from pprint import pprint
ast = parse("""
module A.I

let x = 1

let + = 20
infixl + 5

let z = 2
let g = 1
do z + g

let + = x -> y -> 0

""")

st = State.top()
st.eval(ast)
pprint([e for e in st.code if e.name != 'loc'])