from urgent.repl_parser_wrap import parse_stmt
from urgent.evaluator import Compiler, VM
from urgent.codegen import CodeGen, Numbering
from sijuiacion_lang.lowering import Lower
from importlib._bootstrap_external import _code_to_hash_pyc
from importlib.util import source_hash


def get_code(inp: str, project: str = ""):
    comp = Compiler(project)
    comp.load_module(['Main'])
    cg = CodeGen()
    python = cg.start(comp.code)
    code, _ = Lower({}).lower('main', inp, 1, "", [], [], python)
    return code


__repl_numbering = Numbering()


def get_code_for_repl(inp: str, comp: Compiler):
    comp.code.clear()
    expr = parse_stmt(inp, '<repl>')
    comp.main.eval(expr)
    cg = CodeGen(numbering=__repl_numbering)
    code = comp.main.code
    for each in comp.main.scope.boundvars.values():
        code.append(VM("var", each))
        code.append(VM("as_global", each))

    python = cg.start(comp.code, repl_mode=True)
    for each in comp.main.scope.boundvars.values():
        each.is_global = True
    code, _ = Lower({}).lower('<repl>', inp, 1, "", [], [], python)
    return code


def cc(path: str, out: str, project: str = ""):
    with open(path, 'r') as f:
        source = f.read()
        code = get_code(source, project)

    with open(out, 'wb') as f:
        data = _code_to_hash_pyc(code, source_hash(source))
        f.write(data)


def run(path: str, project: str = ""):
    with open(path, 'r') as f:
        source = f.read()
        code = get_code(source, project)
    exec(code)


def main():
    import argser
    subs = argser.SubCommands()
    subs.add(run)
    subs.add(cc)
    try:
        from urgent.repl1s import repl
        subs.add(repl)
    except ImportError:
        pass
    subs.parse()
