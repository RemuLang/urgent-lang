from sijuiacion_lang.lowering import Lower
from urgent.codegen import CodeGen
from urgent.evaluator import Compiler
from urgent.parser_wrap import parse

comp = Compiler()
lower = Lower({})

ast = parse("""
module At
let print = extern "print"
do print 1
let f = x -> (x, print x)
infixr <| 0
let <| = f -> x -> f x
do print <| f 1

do 114514 match
    a => print a
    
do (1, 2) match (a, b) => print (a, b)
do (1, (2, 5)) match (a, (b, c)) => print (a, b, c)
   
do False ?
    print "错了"
else
    print "好滴"
""")

comp.compile_module(ast)

cg = CodeGen()

python = cg.start(comp.code)
code, _ = lower.lower("module", "module.ugt", 1, "哥，真的急", [], [], python)
exec(code)
