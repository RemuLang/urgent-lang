from urgent.cli import get_code_for_repl, Compiler

comp = Compiler("./bootstrap.toml")


get_code_for_repl("""
do 0 match 0 => 2, 1 => 2
""", comp)

