from __future__ import annotations
from typing import *
from urgent.scope import Scope, Sym
from urgent.evaluator import Instruction
from sijuiacion_lang.lowering import sij
T = TypeVar('T')


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
    def __init__(self, numbering: Numbering = None):
        self.number = numbering if numbering is not None else Numbering()

    def s2n(self, s: Sym) -> str:
        return 'var.{}.{}'.format(s.name, self.number[s.uid])

    def eval(self, instr: Instruction):
        return getattr(self, instr.name)(*instr.args)

    def as_global(self, sym):
        return sij.GlobSet(self.s2n(sym))

    def from_global(self, s: str):
        assert isinstance(s, str)
        return sij.Glob(s)

    def start(self, instrs: List[Instruction], repl_mode=False):
        if repl_mode:
            many = self.eval_many(instrs)
            many.append(sij.Return())
            many.reverse()
            many.append(sij.Const(()))
            many.reverse()
            return many

        many = self.eval_many(instrs)
        many.append(sij.Const(None))
        many.append(sij.Return())
        return many

    def eval_many(self, instrs: List[Instruction]):
        seq = []
        for each in instrs:
            each = self.eval(each)
            if isinstance(each, list):
                seq.extend(each)
            else:
                seq.append(each)
        return seq

    def extern(self, foreign_code):
        return sij.Glob(foreign_code)

    def push(self, v):
        return sij.Const(v)

    def attr(self, attr: str):
        return sij.Attr(attr)

    def set(self, s: Sym):
        assert isinstance(s, Sym)
        if s.is_global:
            return sij.GlobSet(self.s2n(s))
        if s.is_cell.contents:
            return sij.RefSet(self.s2n(s))
        return sij.Store(self.s2n(s))

    def var(self, s: Sym):
        assert isinstance(s, Sym), (s, type(s))
        if s.is_global:
            return sij.Glob(self.s2n(s))
        if s.is_cell.contents:
            return sij.Deref(self.s2n(s))
        return sij.Load(self.s2n(s))

    def pop(self):
        return sij.Pop()

    def tuple(self, n):
        return sij.BuildTuple(n)

    def label(self, n):
        return sij.Label(n)

    def goto(self, n):
        return sij.Goto(n)

    def goto_if(self, n):
        return sij.GotoEq(n)

    def goto_if_not(self, n):
        return sij.GotoNEq(n)

    def eq(self):
        return sij.Cmp(sij.Compare.EQ)

    def neq(self):
        return sij.Cmp(sij.Compare.NE)

    def exc(self, s: str):
        assert isinstance(s, str)

        return [
            sij.Glob("Exception"),
            sij.Const(s),
            sij.Call(1),
            sij.SimpleRaise()
        ]

    def loc(self, i: int):
        assert isinstance(i, int)
        return sij.Line(i + 1)

    def ret(self):
        return sij.Return()

    def dup(self):
        return sij.DUP(1)

    def rot(self):
        return sij.ROT(2)

    def unpack(self, n: int):
        return sij.Unpack(n)

    def call(self, i: int):
        return sij.Call(i)

    def function(self, filename, scope: Scope, arg_sym: Sym, instrs):
        freevars = list(map(self.s2n, scope.freevars.values()))
        return sij.Defun("", filename, freevars, self.s2n(arg_sym),
                         [self.s2n(arg_sym)], self.eval_many(instrs))
