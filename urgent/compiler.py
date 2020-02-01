from __future__ import annotations
from typing import *
from urgent.scope import Scope, Sym, Undef
from urgent.config import Config
from collections import namedtuple
from contextlib import contextmanager
import urgent.ast as ast
import remu_operator


class Instruction:
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def __repr__(self):
        return repr((self.name, *self.args))


class VM:
    name: str
    args: Tuple[...]

    def __new__(cls, name: str, *args):
        return Instruction(name, args)


_op_prefix = 'operator.'


def to_operator_mangled_name(n: str):
    return _op_prefix + n


def to_operator_name_unmangle(n: str):
    return n[len(_op_prefix):]


T = TypeVar('T')


class Numbering(dict):
    def __missing__(self, key):
        v = self[key] = len(self)
        return v


def mk_dispatch(dispatches):
    def apply(f):
        d = f.__annotations__
        assert len(d) is 1
        meth = list(d.values())[0]
        if isinstance(meth, str):
            meth = eval(meth)
        dispatches[meth] = f
        return f

    return apply


class Report(Exception):
    location: ast.Location
    exc: Exception

    def __init__(self, loc, exc):
        self.location = loc
        self.exc = exc

    def __repr__(self):
        exc = self.exc
        return f'{exc.__class__.__name__}: {self.exc}{_show_error_loc(self.location)}'


def _show_error_loc(loc: ast.Location):
    if not loc:
        return '.'
    return ' at {}, line {}, column {}.'.format(loc[2], loc[0] + 1, loc[1])


class Visitor:
    dispatches: Dict[type, Callable]
    _loc: Optional[ast.Location] = None

    def eval(self, expr):
        if hasattr(expr, 'loc'):
            self._loc = expr.loc
        try:
            ret = self.dispatches[expr.__class__](self, expr)
            return ret
        except Report:
            raise
        except Exception as e:
            raise Report(self._loc, e)

    def show_error_loc(self, loc: ast.Location = None):
        loc = loc or self._loc
        return _show_error_loc(loc)


state_dispatches = {}
state_add = mk_dispatch(state_dispatches)


class State(Visitor):
    dispatches = state_dispatches

    @classmethod
    def top(cls, compiler: Compiler):
        return State(Scope.top(), compiler, compiler.code)

    def __init__(self, scope: Scope, compiler: Compiler, code: list):
        self._loc = None
        self.scope = scope
        self.code: List[VM] = code
        self.compiler = compiler
        self.path = ""

    def last_instr(self):
        for i in reversed(self.code):
            if i.name != "loc":
                return i

    def emit(self, vm):
        self.code.append(vm)

    def mk_new(self, scope: Scope = None):
        return State(scope, self.compiler, self.code)

    def mk_sub(self, scope: Scope = None):
        return State(scope or self.scope.sub_scope(), self.compiler, self.code)

    @state_add
    def v_module(self, a: ast.Module):
        self.path = qualname = '.'.join(a.quals)
        for each in a.stmts:
            self.eval(each)

        bounds = self.scope.boundvars
        if not bounds:
            names, syms = [], []
        else:
            names, syms = zip(*[each for each in self.scope.boundvars.items()])

        sym = self.scope.shadow(a.quals[-1])

        self.emit(
            VM("push",
               f"runtime representation of module {qualname}, names: {names}"))
        self.emit(VM("set", sym))
        self.compiler.module_symbols[sym] = {
            **self.scope.boundvars,
            **self.scope.aliases
        }
        self.compiler.evaluated_modules[qualname] = sym

        return sym

    @state_add
    def v_let(self, a: ast.Let):
        emit = self.emit
        is_rec = a.is_rec
        if is_rec:
            for loc, name, expr in a.binds:
                sym = self.scope.shadow(name)
                emit(VM("loc", loc[0]))
                emit(VM("push", ()))
                emit(VM("set", sym))
            for loc, name, expr in a.binds:
                self.mk_sub().eval(expr)
                sym = self.scope.require(name)
                emit(VM("set", sym))
        else:
            binds = []
            for loc, name, expr in a.binds:
                self.mk_sub().eval(expr)
                i = self.last_instr()
                if i and i.name == 'var':
                    sym: Sym = i.args[0]
                    binds.append((loc, name, sym))
                else:
                    binds.append((loc, name, None))

            binds.reverse()
            for loc, name, alias in binds:
                emit(VM("loc", loc[0]))
                if alias:
                    self.scope.shadow(name, alias)
                    emit(VM("pop"))
                else:
                    sym = self.scope.shadow(name)
                    emit(VM("set", sym))

    @state_add
    def v_data(self, c: ast.Data):
        emit = self.emit
        emit(VM("loc", c.loc[0]))
        for each in c.cons:
            self.eval(each)

    @state_add
    def v_cons(self, c: ast.Cons):
        def remove_dup(n, slots):
            while n in slots:
                n += '_'
            return n

        slots = c.slots
        slots = [
            each if each != '_' else remove_dup('elt{}'.format(i), slots)
            for i, each in enumerate(slots)
        ]

        loc = c.loc
        n = c.id

        cons_sym = self.scope.enter(n)
        data_sym = self.scope.enter('data.' + n)
        emit = self.emit
        emit(VM("load_global", "namedtuple"))
        emit(VM("push", n))
        emit(VM("push", tuple(slots)))
        emit(VM("call", 2))

        if not slots:
            fun = ast.PyCall(ast.SVar(loc, data_sym), [])
        else:
            vars = [ast.Var(loc, slot_n) for slot_n in slots]
            fun = ast.PyCall(ast.SVar(loc, data_sym), vars)
            for var in reversed(vars):
                fun = ast.Fun(loc, var, ast.TCO(fun))
                fun.name = n

        emit(VM("set", data_sym))

        self.eval(fun)

        emit(VM("set", cons_sym))

        comp = self.compiler
        comp.patterns[cons_sym] = data_sym
        comp.pattern_ary[cons_sym] = len(slots)

    @state_add
    def v_svar(self, a: ast.SVar):
        self.emit(VM("loc", a.loc[0]))
        self.emit(VM("var", a.sym))

    @state_add
    def v_pycall(self, a: ast.PyCall):
        self.eval(a.f)
        for arg in a.args:
            self.eval(arg)
        self.emit(VM("call", len(a.args)))

    @state_add
    def v_list(self, a: ast.List):
        lst = ast.Var(a.loc, "Nil")
        cons = ast.Var(a.loc, "Cons")
        for each in reversed(a.elts):
            lst = ast.Call(ast.Call(cons, each), lst)
        return self.eval(lst)

    @state_add
    def v_do(self, a: ast.Do):
        self.emit(VM("loc", a.loc[0]))
        self.eval(a.expr)
        self.emit(VM("pop"))

    def get_module_sym_from_qualified_names(self, names: List[str]):
        ns = names[::-1]
        sym = self.scope.require(ns.pop())
        module_symbols = self.compiler.module_symbols
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
            sub = self.mk_new(Scope.top())
            sym = self.compiler.load_module(module_ids, sub)

        names: Dict[str, Sym] = self.compiler.module_symbols[sym]
        for n, sym in names.items():
            self.scope.shadow(n, sym)
        self.emit(VM("loc", a.loc[0]))

    @state_add
    def v_import(self, a: ast.Import):
        module_ids = a.module_ids
        try:
            sym = self.get_module_sym_from_qualified_names(module_ids)
        except Undef:
            sub = self.mk_new(Scope.top())
            sym = self.compiler.load_module(module_ids, sub)

        self.scope.shadow(module_ids[-1], sym)
        self.emit(VM("loc", a.loc[0]))

    @state_add
    def v_infix(self, a: ast.Infix):
        n = a.bop
        loc = a.loc
        sym = self.scope.enter(to_operator_mangled_name(n))
        if sym in self.compiler.op_precedences:
            raise Exception("redefinition of operator properties")
        self.compiler.op_precedences[sym] = a.precedence
        self.compiler.op_assoc[sym] = a.is_right_assoc
        self.emit(VM("loc", loc[0]))
        self.emit(VM("push", ()))
        self.emit(VM("set", sym))

    @state_add
    def v_if(self, a: ast.If):
        emit = self.emit
        label_t = self.compiler.new_label()
        label_end = self.compiler.new_label()
        emit(VM("loc", a.loc[0]))
        self.eval(a.cond)
        emit(VM("goto_if", label_t))
        self.eval(a.fc)
        emit(VM("goto", label_end))
        emit(VM("label", label_t))
        self.eval(a.tc)
        emit(VM("label", label_end))

    @state_add
    def v_in(self, a: ast.In):
        sub1 = self.mk_sub()
        sub1.eval(a.stmt)
        sub2 = sub1.mk_sub()
        sub2.eval(a.expr)

    def solve_bin_ops(self, hd, tl):
        def cons(f):
            return lambda arg1, arg2: ast.Call(
                ast.Call(ast.Var(loc_map[f], name_map[f]), arg1), arg2)

        seq = [hd]
        name_map = {}
        loc_map = {}
        for loc, a, b in tl:
            operator_name = to_operator_mangled_name(a)
            operator_sym = self.scope.require(operator_name)
            name_map[operator_sym] = a
            loc_map[operator_sym] = loc
            op = remu_operator.Operator(operator_sym)
            seq.extend([op, b])
        # noinspection PyTypeChecker
        return remu_operator.binop_reduce(
            cons,
            seq,
            precedences=self.compiler.op_precedences,
            associativities=self.compiler.op_assoc)

    @state_add
    def v_match(self, a: ast.Match):
        self.eval(a.val_to_match)
        compiler = self.compiler
        n_cases = len(a.cases)
        labels = [compiler.new_label() for _ in range(n_cases)]
        label_success = compiler.new_label()

        emit = self.emit
        sub = self.mk_sub()
        sub.scope.allow_reassign = True

        for (loc, pat, expr), label_fail in zip(a.cases, labels):
            emit(VM("loc", loc[0]))
            emit(VM("dup"))
            PatternCompilation(sub.scope, sub, label_fail).eval(pat)
            emit(VM("pop"))
            sub.eval(expr)
            emit(VM("goto", label_success))
            emit(VM("label", label_fail))

        emit(
            VM(
                "exc", "Pattern matching failed at {}.".format(
                    self.show_error_loc(a.loc))))
        emit(VM("label", label_success))
        sub.scope.allow_reassign = False

    @state_add
    def v_bin(self, a: ast.Bin):
        self.v_call(self.solve_bin_ops(a.head, a.tl))

    @state_add
    def v_call(self, a: ast.Call):
        # this is not tail call
        self.emit(VM("load_global", "tco"))

        self.eval(a.arg)
        self.eval(a.f)
        self.emit(VM("tuple", 2))

        self.emit(VM("call", 1))

    @state_add
    def v_tco(self, a: ast.TCO):
        emit = self.emit
        expr = a.expr
        if isinstance(expr, ast.Bin):
            expr = self.solve_bin_ops(expr.head, expr.tl)
        if isinstance(expr, ast.Call):
            # tail call
            emit(VM("push", False))
            self.eval(expr.arg)
            self.eval(expr.f)
            emit(VM("tuple", 2))
            emit(VM("tuple", 2))
        elif isinstance(expr, ast.If):
            # propagate
            self.eval(
                ast.If(expr.loc, expr.cond, ast.TCO(expr.tc),
                       ast.TCO(expr.fc)))
        elif isinstance(expr, ast.Match):
            # propagate
            self.eval(
                ast.Match(expr.loc, expr.val_to_match,
                          [(loc, pat, ast.TCO(value))
                           for loc, pat, value in expr.cases]))

        elif isinstance(expr, ast.In):
            # propagate
            self.eval(ast.In(expr.stmt, ast.TCO(expr.expr)))
        else:
            # non-tailcall evaluation.
            emit(VM("push", True))
            self.eval(a.expr)
            emit(VM("tuple", 2))

    @state_add
    def v_tuple(self, a: ast.Tuple):
        self.emit(VM("loc", a.loc[0]))
        if not a.elts:
            return self.emit(VM("push", ()))

        if len(a.elts) == 1:
            return self.eval(a.elts[0])

        for each in a.elts:
            self.eval(each)
        self.emit(VM("tuple", len(a.elts)))

    @state_add
    def v_var(self, a: ast.Var):
        self.emit(VM("loc", a.loc[0]))
        sym = self.scope.require(a.id)
        self.emit(VM("var", sym))

    @state_add
    def v_func(self, a: ast.Fun):
        self.emit(VM("loc", a.loc[0]))
        code = self.code
        self.code = []
        sub = self.mk_sub(self.scope.sub_scope(hold_bound=True))
        emit = self.emit
        n = self.compiler.gen_sym()

        label_matched = self.compiler.new_label()
        label_unmatch = self.compiler.new_label()
        emit(VM("loc", a.loc[0]))
        n = sub.scope.enter(n)
        emit(VM("var", n))
        sub = sub.mk_sub()
        sub.scope.allow_reassign = True
        PatternCompilation(sub.scope, self, label_unmatch).eval(a.pat)
        sub.scope.allow_reassign = False

        emit(VM("label", label_matched))

        sub.eval(a.body)
        emit(VM("goto", "urgent.funcend"))
        emit(VM("label", label_unmatch))
        emit(VM("exc", "Function argument not match."))
        emit(VM("label", "urgent.funcend"))
        emit(VM("ret"))

        code, self.code = self.code, code
        emit(VM("function", a.name, a.loc[2], sub.scope, n, code))

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
            if sym in self.compiler.module_symbols:
                names = self.compiler.module_symbols[sym]
                if a.attr not in names:
                    raise Exception('Module {} has no attribute {}.'.format(
                        sym.name, a.attr))
                sym = names[a.attr]
                i.name = "loc"
                i.args = a.loc[0],
                return self.emit(VM("var", sym))
        self.emit(VM("attr", a.attr))

    @state_add
    def v_extern(self, a: ast.Extern):
        self.emit(VM("loc", a.loc[0]))
        self.emit(VM("extern", a.s))

    @state_add
    def v_and(self, a: ast.And):
        emit = self.emit
        label = self.compiler.new_label()
        emit(VM("loc", a.loc[0]))
        self.eval(a.lhs)
        emit(VM("dup"))
        emit(VM("goto_if_not", label))
        emit(VM("pop"))
        self.eval(a.rhs)
        emit(VM("label", label))

    @state_add
    def v_or(self, a: ast.Or):
        emit = self.emit
        label = self.compiler.new_label()
        emit(VM("loc", a.loc[0]))
        self.eval(a.lhs)
        emit(VM("dup"))
        emit(VM("goto_if", label))
        emit(VM("pop"))
        self.eval(a.rhs)
        self.emit(VM("label", label))


pat_dispatches = {}
pat_add = mk_dispatch(pat_dispatches)


class PatternCompilation(Visitor):
    dispatches = pat_dispatches

    def __init__(self, scope: Scope, state: State, label_unmatch):
        self.scope = scope
        self.emit = state.emit
        self.state = state
        self.label_unmatch = label_unmatch
        self.predict = None

    @contextmanager
    def fail_to_specific_label(self, label_name: str):
        lu = self.label_unmatch
        try:
            yield
        finally:
            self.label_unmatch = lu

    def check_class(self, class_name: str):
        emit = self.emit
        emit(VM("dup"))
        emit(VM("attr", "__class__"))
        emit(VM("load_global", class_name))
        emit(VM("neq"))
        emit(VM("goto_if", self.label_unmatch))

    def check_len_eq(self, n: int):
        emit = self.emit
        emit(VM("dup"))
        emit(VM("load_global", "len"))
        emit(VM("rot"))
        emit(VM("call", 1))

        emit(VM("push", n))

        emit(VM("neq"))

        emit(VM("goto_if", self.label_unmatch))

    @pat_add
    def v_list(self, a: ast.List):
        lst = ast.Var(a.loc, "Nil")
        cons = ast.Var(a.loc, "Cons")
        for each in reversed(a.elts):
            lst = ast.Call(ast.Call(cons, each), lst)
        return self.eval(lst)

    @pat_add
    def v_lit(self, a: ast.Lit):
        emit = self.emit

        emit(VM("loc", a.loc[0]))
        emit(VM("push", a.value))
        emit(VM("neq"))
        emit(VM("goto_if", self.label_unmatch))

    @pat_add
    def v_and(self, a: ast.And):
        self.emit(VM("loc", a.loc[0]))
        self.emit(VM("dup"))
        self.eval(a.lhs)
        self.eval(a.rhs)

    @pat_add
    def v_or(self, a: ast.Or):
        emit = self.emit
        emit(VM("loc", a.loc[0]))
        fail_here = self.state.compiler.new_label()
        succ_here = self.state.compiler.new_label()

        emit(VM("dup"))
        with self.fail_to_specific_label(fail_here):
            self.eval(a.lhs)
            emit(VM("pop"))
            emit(VM("goto", succ_here))

        emit(VM("label", fail_here))
        self.eval(a.rhs)
        emit(VM("label", succ_here))

    @pat_add
    def v_bin(self, a: ast.Bin):
        pat = self.state.solve_bin_ops(a.head, a.tl)
        self.v_call(pat)

    @pat_add
    def v_call(self, a: ast.Call):
        args = [a.arg]
        f = a.f
        while isinstance(f, ast.Call):
            args.append(f.arg)
            f = f.f
        args.reverse()
        # TODO: location
        f = self.eval(f)
        if not f:
            raise Exception("Not a recogniser!")
        data_cons, n = f
        if n != len(args):
            raise Exception("Deconstructor {} requires {} arguments.".format(
                data_cons, n))
        emit = self.emit
        emit(VM("dup"))
        emit(VM("attr", '__class__'))
        emit(VM("var", data_cons))
        emit(VM("neq"))
        emit(VM("goto_if", self.label_unmatch))
        emit(VM("unpack", n))
        for arg in args:
            loc = getattr(arg, 'loc', None)
            self.non_recogniser(arg, loc)

    def non_recogniser(self, a, loc):
        recog = self.eval(a)
        if recog:
            uncons, n = recog
            raise Exception(
                "Recogniser {} is {}-ary, but used as enumeration {}".format(
                    uncons.name, n, self.show_error_loc(loc)))

    @pat_add
    def v_tuple(self, a: ast.Tuple):
        if not a.elts:
            self.emit(VM("push", ()))
            self.emit(VM("neq"))
            self.emit(VM("goto_if", self.label_unmatch))
            return

        if len(a.elts) == 1:
            return self.eval(a.elts[0])

        emit = self.emit
        emit(VM("loc", a.loc[0]))

        self.check_class('tuple')
        self.check_len_eq(len(a.elts))
        emit(VM("unpack", len(a.elts)))

        for each in a.elts:
            self.non_recogniser(each, a.loc)
        return

    def process_recogniser(self, sym: Sym, loc):
        if sym not in self.state.compiler.patterns:
            raise Exception("{} is not a pattern {}.".format(
                sym.name, self.show_error_loc(loc)))
        n = self.state.compiler.pattern_ary[sym]
        if not n:
            self.emit(VM("var", sym))
            self.emit(VM("not_same"))
            self.emit(VM("goto_if", self.label_unmatch))
            return
        data_cons = self.state.compiler.patterns[sym]
        return data_cons, n

    @pat_add
    def v_func(self, a: ast.Fun):
        emit = self.emit
        self.state.eval(a.pat)
        emit(VM("load_global", "tco"))
        emit(VM("rot", 3))
        emit(VM("tuple", 2))
        emit(VM("call", 1))
        self.eval(a.body)

    @pat_add
    def v_tco(self, a: ast.TCO):
        return self.eval(a.expr)

    @pat_add
    def v_var(self, a: ast.Var):
        if a.id == '_':
            self.emit(VM("pop"))
            return
        n = a.id

        if n and n[0].isupper() or not n[0].isidentifier():
            # upper names and operators
            # deconstructor
            sym = self.state.scope.require(a.id)
            return self.process_recogniser(sym, a.loc)

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
            if sym in self.state.compiler.module_symbols:
                names = self.state.compiler.module_symbols[sym]
                if a.attr not in names:
                    raise Exception('Module {} has no attribute.'.format(
                        sym.name, a.attr))
                sym = names[a.attr]
                i.name = "loc"
                i.args = a.loc[0],
                return self.process_recogniser(sym, a.loc)

        raise Exception(
            "Invalid pattern .{} at {}, (line, column) = {}".format(
                a.attr, a.loc[2], a.loc[:2]))


class Compiler:
    evaluated_modules: Dict[str, Sym]
    ast_modules: Dict[Tuple[str, ...], ast.Module]

    module_symbols: Dict[Sym, Dict[str, Sym]]
    op_precedences: Dict[Sym, int]
    op_assoc: Dict[Sym, int]
    namegen_cnt: int

    # constructor -> deconstructor.
    # if the deconstructor is None, it's a classic ADT.
    patterns: Dict[Sym, Optional[Sym]]

    pattern_ary: Dict[Sym, int]
    code: List[Instruction]
    main: State

    def __init__(self, project_file: str = None):
        self.module_symbols = {}
        self.op_precedences = {}
        self.op_assoc = {}
        self.namegen_cnt = 0
        self.patterns = {}
        self.pattern_ary = {}
        self.evaluated_modules = {}
        self.code = []
        self._loc = None

        project_file = project_file or '~/.urgent/main.toml'
        self.project_file = project_file
        conf = self.config = Config.load(project_file)
        conf.src_dirs += ['.']
        self.ast_modules = conf.load_modules()
        self.main = State.top(self)

    def load_module(self, names: List[str], state: State = None) -> Sym:
        qualname = '.'.join(names)
        mod_sym = self.evaluated_modules.get(qualname)
        if mod_sym:
            return mod_sym
        mod_ast = self.ast_modules[tuple(names)]

        mod_sym = self.compile_module(mod_ast, state)
        self.evaluated_modules['.'.join(names)] = mod_sym
        assert isinstance(mod_sym, Sym)
        return mod_sym

    def compile_module(self, mod: ast.Module, state: State = None):
        state = state or self.main
        return state.eval(mod)

    def new_label(self):
        i = self.namegen_cnt
        self.namegen_cnt += 1
        return "Label.{}".format(i)

    def gen_sym(self):
        i = self.namegen_cnt
        self.namegen_cnt += 1
        return "sym.{}".format(i)
