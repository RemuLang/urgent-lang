from __future__ import annotations
import json
from typing import *
from urgent.scope import Scope, Sym
from dataclasses import dataclass
T = TypeVar('T')


class VM:
    name: str
    args: Tuple[...]

    def __init__(self, name: str, *args):
        self.name = name
        self.args = args


class Ref(Generic[T]):
    contents: T

    def __init__(self, v: T):
        self.contents = v


class MissingDict(dict):
    def __init__(self, f):
        super().__init__()
        self.gen_value = f

    def __missing__(self, key):
        value = self[key] = self.gen_value(key)
        return value


class Numbering(dict):
    def __missing__(self, key):
        v = self[key] = len(self)
        return v


class CodeGen:
    def __init__(self, filename: str):
        self.code = [
            'runtime operator', 'filename {}'.format(json.dumps(filename))
        ]
        self.layout = 0
        self.number = Numbering()

    def extern(module, foreign_code):
        module("const #{}#".format(
            json.decoder.py_scanstring(foreign_code, 1)[0]))

    def s2n(self, s: Sym) -> str:
        return '{}_{}'.format(s.name, id(self.number[s.uid]))

    def __call__(self, other: str):
        self.code.append('  ' * self.layout + other)

    def eval(self, node):
        if isinstance(node, Sym):
            instr = "deref" if node.is_cell.contents else "load"
            self("{} {}".format(instr, self.s2n(node)))
            return
        if isinstance(node, VM):
            return getattr(self, node.name, *node.args)

        self("const #{}#".format(repr(node)))

    def loc(module, location, contents = None):
        if location:
            line = location[0]
            module('line {}'.format(line))
        if contents is not None:
            module.eval(contents)

    def set(module, sym: Sym, expr):
        assert isinstance(sym, Sym)
        module.eval(expr)
        instr = "deref!" if sym.is_cell.contents else "store"
        module("{} {}".format(instr, module.s2n(sym)))

    def call(module, f, arg):
        module.eval(f)
        module.eval(arg)
        module("call 1")

    def prj(module, expr, i):
        module.eval(expr)
        module.eval(i)
        module("prj")

    def label(module, name):
        module("label {}".format(name))

    def goto(module, name):
        module("goto {}".format(name))

    def goto_if(module, name, cond):
        module.eval(cond)
        module("goto-if {}".format(name))

    def goto_if_not(module, name, cond):
        module.eval(cond)
        module("goto-if-not {}".format(name))

    def indir(module, expr):
        module.eval(expr)
        module("indir")

    def addr(module, name):
        module("blockaddr {}".format(name))

    def block(module, *elts):
        for each in elts:
            module.eval(each)

    def tuple(module, elts):
        for each in elts:
            module.eval(each)
        module("tuple {}".format(len(elts)))

    def list(module, elts):
        for each in elts:
            module.eval(each)
        module("list {}".format(len(elts)))

    def func(module, filename, scope: Scope, arg, expr):
        assert not freevars or isinstance(freevars[0], Sym)
        assert isinstance(arg, Sym)

        module("defun")
        module.layout += 2

        module("filename {}".format(json.dumps(filename)))
        module("free [{}]".format(' '.join(map(module.s2n, freevars))))
        module("args [{}] {{".format(module.s2n(arg)))
        module.eval(expr)
        module("label pround.return")
        module("return")
        module.layout -= 2
        module("}")

    def switch(module, target, cases, default):
        module.eval(target)
        module("switch")
        for i, n in cases:
            module("| {} => {}".format(i, n))
        if default:
            module("| _ => {}".format(default))

    def feed_code(self):
        self.code.append('print')
        self.code.append('const #None#')
        self.code.append('return')
        return '\n'.join(self.code)
