from urgent.cli import get_code, Compiler
from urgent.parser_wrap import parse

mod = parse("""
module Main
open Pre

let x =
    open Pre in
    let op2 = op
    let y = imp "operator"
    rec f = x ->
         op2.add.((x, 1), (y, 2))
    in f 1
    
do open Pre in print x
""")
code = get_code(mod, "a.ugt", "./bootstrap.toml")

exec(code)
