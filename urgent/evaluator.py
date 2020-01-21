from __future__ import annotations
from urgent.scope import Scope, Sym, Undef
from typing import *
import urgent.ast as ast
import remu_operator
from collections import namedtuple


class _VM(namedtuple('VM', ['name', 'args'])):
    pass


class VM:
    name: str
    args: Tuple[...]

    def __new__(cls, name: str, *args):
        return _VM(name, args)


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


def mk_dispatch(dispatches):
    def apply(f):
        d = f.__annotations__
        assert len(d) is 1
        dispatches[eval(next(iter(d.values())))] = f
        return f

    return apply


class Visitor:
    dispatches: Dict[type, Callable]

    def eval(self, expr) -> Visitor:
        return self.dispatches[expr.__class__](self, expr)


state_dispatches = {}
state_add = mk_dispatch(state_dispatches)

ModuleSym = Sym


class Loader:
    module_symbols: Dict[Sym, Dict[str, Sym]]
    op_precedences: Dict[Sym, int]
    op_assoc: Dict[Sym, int]
    labels: int
    patterns: Dict[Sym, Sym]
    pattern_ary: Dict[Sym, int]

    def __init__(self):
        self.module_symbols = {}
        self.op_precedences = {}
        self.op_assoc = {}
        self.labels = 0
        self.patterns = {}
        self.pattern_ary = {}

    def load_module(self, names: List[str]) -> Sym:
        raise NotImplementedError

    def new_label(self):
        i = self.labels
        self.labels += 1
        return "Label.{}".format(i)

    def gen_sym(self):
        i = self.labels
        self.labels += 1
        return "sym.{}".format(i)


class State(Visitor):
    dispatches = state_dispatches

    @classmethod
    def top(cls):
        return State(Scope.top(), Loader(), [])

    def __init__(self, scope: Scope, loader: Loader, code: list):
        self.scope = scope
        self.code: List[VM] = code
        self.loader = loader
        self.wait_for_op_binding: Dict[str, Tuple[int, int]] = {}

    def last_instr(self):
        for i in reversed(self.code):
            if i.name != "loc":
                return i

    def emit(self, vm):
        self.code.append(vm)

    def new(self, scope: Scope = None):
        return State(scope or self.scope, self.loader, self.code)

    @state_add
    def v_module(self, a: ast.Module):
        for each in a.stmts:
            self.eval(each)

    @state_add
    def v_let(self, a: ast.Let):
        emit = self.emit
        is_rec = a.is_rec
        if is_rec:
            for loc, name, expr in a.binds:
                sym = self.scope.shadow(name)
                emit(VM("loc", loc[0]))
                emit(VM("set", sym))
            for loc, name, expr in a.binds:
                self.new(self.scope.sub_scope()).eval(expr)
                sym = self.scope.require(name)
                emit(VM("set", sym))
        else:
            binds = []
            for loc, name, expr in a.binds:
                self.new().eval(expr)
                binds.append((loc, name))
            binds.reverse()
            for loc, name in binds:
                emit(VM("loc", loc[0]))
                sym = self.scope.shadow(name)
                emit(VM("set", sym))

    @state_add
    def v_do(self, a: ast.Do):
        self.emit(VM("loc", a.loc[0]))
        self.eval(a.expr)

    def get_module_sym_from_qualified_names(self, names: List[str]):
        ns = names[::-1]
        sym = self.scope.require(ns.pop())
        module_symbols = self.loader.module_symbols
        if sym not in module_symbols:
            raise Undef
        while ns:
            names = module_symbols[sym]
            sym = names.get(ns.pop())
            if not sym or sym not in module_symbols:
                raise Undef
        return sym

    @state_add
    def v_open(self, a: ast.Open):
        module_ids = a.module_ids
        try:
            sym = self.get_module_sym_from_qualified_names(module_ids)
        except Undef:
            sym = self.loader.load_module(module_ids)

        names: Dict[str, Sym] = self.loader.module_symbols[sym]
        for n, sym in names.items():
            self.scope.shadow(n, sym)
        self.emit(VM("loc", a.loc[0]))

    @state_add
    def v_import(self, a: ast.Import):
        module_ids = a.module_ids
        try:
            sym = self.get_module_sym_from_qualified_names(module_ids)
        except Undef:
            sym = self.loader.load_module(module_ids)

        self.scope.shadow(module_ids[-1], sym)
        self.emit(VM("loc", a.loc[0]))

    @state_add
    def v_infix(self, a: ast.Infix):
        n = a.bop
        loc = a.loc
        sym = self.scope.require(n)
        if sym in self.loader.op_precedences:
            raise Exception("redefinition of operator properties")
        self.loader.op_precedences[sym] = a.precedence
        self.loader.op_assoc[sym] = a.is_right_assoc
        self.emit(VM("loc", loc[0]))

    @state_add
    def v_if(self, a: ast.If):
        emit = self.emit
        label_t = self.loader.new_label()
        label_end = self.loader.new_label()
        emit(VM("loc", a.loc[0]))
        self.eval(a.cond)
        emit(VM("goto-if", label_t))
        self.eval(a.fc)
        emit(VM("goto", label_end))
        emit(VM("label", label_t))
        self.eval(a.tc)
        emit(VM("label", label_end))

    @state_add
    def v_in(self, a: ast.In):
        self.eval(a.stmt)
        self.new().eval(a.expr)

    @state_add
    def v_bin(self, a: ast.Bin):
        seq = [a.head]

        def cons(f):
            return lambda arg1, arg2: (f, arg1, arg2)

        loc_maps = {}
        for loc, a, b in a.tl:
            sym = self.scope.require(a)
            loc_maps[sym] = loc[0]
            sym = remu_operator.Operator(sym)
            seq.extend([sym, b])

        # noinspection PyTypeChecker
        tps = remu_operator.binop_reduce(
            cons,
            seq,
            precedences=self.loader.op_precedences,
            associativities=self.loader.op_assoc)

        emit = self.emit

        def eval_binops(tps):
            if not isinstance(tps, tuple):
                return self.eval(tps)
            f, arg1, arg2 = tps
            emit(VM("loc", loc_maps[f]))
            emit(VM("var", f))
            eval_binops(arg1)
            emit(VM("call", 1))
            eval_binops(arg2)
            emit(VM("call", 1))

        eval_binops(tps)

    @state_add
    def v_call(self, a: ast.Call):
        self.eval(a.f)
        self.eval(a.arg)
        return VM("call", 1)

    @state_add
    def v_unit(self, a: ast.Tuple):
        self.emit(VM("loc", a.loc[0]))
        if not a.elts:
            return self.emit(VM("push", ()))
        # should be is
        if len(a.elts) == 1:
            return self.eval(a.elts[0])

        for each in a.elts:
            self.eval(each)
        self.emit(VM("tuple", len(a.elts)))

    @state_add
    def v_list(self, a: ast.List):
        for each in a.elts:
            self.eval(each)
        self.emit(VM("list", len(a.elts)))

    @state_add
    def v_var(self, a: ast.Var):
        self.emit(VM("loc", a.loc[0]))
        self.emit(VM("var", a.id))

    @state_add
    def v_func(self, a: ast.Fun):
        self.emit(VM("loc", a.loc[0]))
        code = self.code
        self.code = []
        sub = self.new(self.scope.sub_scope(hold_bound=True))
        emit = self.emit
        n = self.loader.gen_sym()
        label_matched = self.loader.new_label()
        label_unmatch = self.loader.new_label()
        emit(VM("loc", a.loc[0]))

        sub.scope.allow_reassign = True
        PatternCompilation(sub.scope, self, label_unmatch).eval(a.pat)
        sub.scope.allow_reassign = False

        emit(VM("label", label_matched))
        sub.eval(a.body)
        emit(VM("goto", "urgent.funcend"))
        emit(VM("label", label_unmatch))
        emit(VM("exc", "Function argument not match."))
        emit(VM("label", "urgent.funcend"))
        emit(VM("return"))

        code, self.code = self.code, code
        emit(VM("function", a.loc[2], sub.scope, n, code))

    @state_add
    def v_lit(self, a: ast.Lit):
        self.emit(VM("push", a.value))

    @state_add
    def v_field(self, a: ast.Field):
        self.eval(a.base)
        i = self.last_instr()
        self.emit(VM("loc", a.loc[0]))
        if i and i.name == 'var':
            sym: Sym = i.args[0]
            if sym in self.loader.module_symbols:
                names = self.loader.module_symbols[sym]
                if a.attr not in names:
                    raise Exception('Module {} has no attribute.'.format(
                        sym.name, a.attr))
                sym = names[a.attr]
                return self.emit(VM("var", sym))
        self.emit(VM("attr", a.attr))

    @state_add
    def v_extern(self, a: ast.Extern):
        self.emit(VM("loc", a.loc[0]))
        self.emit(VM("extern", a.s))


pat_dispatches = {}
pat_add = mk_dispatch(pat_dispatches)


class PatternCompilation:
    loader: Loader
    dispatches = pat_dispatches

    def __init__(self, scope: Scope, state: State, label_unmatch):
        self.scope = scope
        self.emit = state.emit
        self.state = state
        self.label_unmatch = label_unmatch
        self.predict = None

    def eval(self, expr):
        return self.dispatches[expr.__class__](self, expr)

    def check_len_eq(self, n: int):
        emit = self.emit
        emit(VM("dup"))
        emit(VM("global", "len"))
        emit(VM("call", "1"))

        emit(VM("push", n))

        emit(VM("neq"))

        emit(VM("goto-if", self.label_unmatch))

    def show_error(self, loc: ast.Location):
        if not loc:
            return '.'
        return 'at {}, line {}, column {}.'.format(loc[2], loc[0], loc[1])

    @pat_add
    def v_lit(self, a: ast.Lit):
        emit = self.emit

        emit(VM("loc", a.loc[0]))
        emit(VM("push", a.value))
        emit(VM("eq", a.value))
        emit(VM("goto", self.label_unmatch))

    @pat_add
    def v_call(self, a: ast.Call):
        # TODO: location
        f = self.eval(a.f)
        if not f:
            raise Exception("Not a recogniser!")
        uncons, n = f
        assert n > 0
        emit = self.emit
        emit(VM("push", uncons))
        emit(VM("rot", 2))
        emit(VM("call", 1))
        emit(VM("unpack", n))
        if n == 1:
            return self.eval(a.arg)

        if not isinstance(a.arg, ast.Tuple):
            raise Exception(
                "Expect a tuple for deconstruction of recogniser {}.".format(
                    uncons.name))
        if len(a.arg.elts) != n:
            raise Exception("{} is a {}-ary recogniser, got {}, {}".format(
                uncons.name, n, len(a.arg.elts), self.show_error(a.arg.loc)))
        loc = a.arg.loc
        for each in a.arg.elts:
            self.non_recogniser(each, loc)

    def non_recogniser(self, a, loc):
        recog = self.eval(a)
        if recog:
            uncons, n = recog
            raise Exception(
                "Recogniser {} is {}-ary, but used as enumeration {}".format(
                    uncons.name, n, self.show_error(loc)))

    @pat_add
    def v_tuple(self, a: ast.Tuple):
        emit = self.emit
        emit(VM("loc", a.loc[0]))

        self.check_len_eq(len(a.elts))
        emit(VM("unpack", len(a.elts)))

        for each in a.elts:
            self.non_recogniser(each, a.loc)
        return

    def for_symbol(self, sym: Sym, loc):
        if sym not in self.state.loader.patterns:
            raise Exception("{} is not a pattern {}.".format(
                sym.name, self.show_error(loc)))
        uncons = self.state.loader.patterns[sym]
        n = self.state.loader.pattern_ary[sym]
        if not n:
            self.emit(VM("var", uncons))
            self.emit(VM("eq", 0))
            return
        return uncons, n

    @pat_add
    def v_var(self, a: ast.Var):
        n = a.id
        if n and n[1].isupper():
            sym = self.state.scope.require(a.id)
            return self.for_symbol(sym, a.loc)

        # bound to variable
        sym = self.scope.enter(n)
        self.emit(VM("set", sym))

    @pat_add
    def v_attr(self, a: ast.Field):

        self.state.eval(a.base)
        i = self.state.last_instr()
        self.emit(VM("loc", a.loc[0]))
        if i and i.name == 'var':
            sym: Sym = i.args[0]
            if sym in self.state.loader.module_symbols:
                names = self.state.loader.module_symbols[sym]
                if a.attr not in names:
                    raise Exception('Module {} has no attribute.'.format(
                        sym.name, a.attr))
                sym = names[a.attr]
                return self.for_symbol(sym, a.loc)

        raise Exception(
            "Invalid pattern .{} at {}, (line, column) = {}".format(
                a.attr, a.loc[2], a.loc[:2]))
