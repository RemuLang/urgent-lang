from urgent.repl_parser_wrap import parse_stmt
from urgent.parser_wrap import parse
from urgent.compiler import Compiler, VM
from urgent.ast import Module
from urgent.codegen import CodeGen, Numbering
from urgent.version import __version__
from sijuiacion_lang.lowering import Lower
from importlib._bootstrap_external import _code_to_hash_pyc
from importlib.util import source_hash
import marshal


def get_code(inp: Module, filename, project: str = ""):
    comp = Compiler(project)
    comp.compile_module(inp)
    cg = CodeGen()
    python = cg.start(comp.code)
    code, _ = Lower({}).lower('main', filename, 1, "", [], [], python)
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
    code, _ = Lower({}).lower(inp, '<repl>', 1, "", [], [], python)
    return code


def cc(path: str, out: str, project: str = "", raw_bytecode: bool = False):
    with open(path, 'r') as f:
        source = f.read()
        mod = parse(source, path)
        code = get_code(mod, path, project)

    with open(out, 'wb') as f:
        if raw_bytecode:
            f.write(marshal.dumps(code))
            return
        data = _code_to_hash_pyc(code, source_hash(source.encode('utf8')))
        f.write(data)


def run(path: str, project: str = ""):
    with open(path, 'r') as f:
        source = f.read()
        mod = parse(source, path)
        code = get_code(mod, path, project)
    exec(code)


def version():
    print(__version__)


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
    subs.add(version)
    subs.parse()
