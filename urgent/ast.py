from __future__ import annotations
from dataclasses import dataclass
from urgent.scope import Sym
import typing as t

Location = t.Tuple[int, int, str]
DEREF = "!"
WILDCARD = '_'

@dataclass
class Do:
    loc: Location
    expr: Expr


@dataclass
class Open:
    loc: Location
    module_ids: t.List[str]


@dataclass
class Cons:
    loc: Location
    id: str
    slots: t.List[str]


@dataclass
class Infix:
    loc: Location
    is_right_assoc: bool
    bop: str
    precedence: int


@dataclass
class Let:
    loc: Location
    is_rec: bool
    binds: t.List[t.Tuple[Location, str, Expr]]


@dataclass
class Import:
    loc: Location
    module_ids: t.List[str]


@dataclass
class Match:
    loc: Location
    val_to_match: Expr
    cases: t.List[t.Tuple[Location, Expr, Expr]]


@dataclass
class If:
    loc: Location
    cond: Expr
    tc: Expr
    fc: Expr


@dataclass
class Fun:
    loc: Location
    pat: Expr
    body: Expr


@dataclass
class Bin:
    head: Expr
    tl: t.List[t.Tuple[str, Expr]]


@dataclass
class Call:
    f: Expr
    arg: Expr


@dataclass
class PyCall:
    f: Expr
    args: t.List[Expr]


@dataclass
class List:
    loc: Location
    elts: t.List[Expr]


@dataclass
class Data:
    loc: Location
    cons: t.List[Cons]


@dataclass
class Tuple:
    loc: Location
    elts: t.List[Expr]


@dataclass
class In:
    stmt: Stmt
    expr: Expr


@dataclass
class Lit:
    loc: Location
    value: object


@dataclass
class Var:
    loc: Location
    id: str


@dataclass
class SVar:
    # symbolic variable, used for compiler
    loc: Location
    sym: Sym


@dataclass
class Field:
    loc: Location
    base: Expr
    attr: str


@dataclass
class Coerce:
    loc: Location
    expr: Expr


@dataclass
class Extern:
    loc: Location
    s: str


@dataclass
class And:
    loc: Location
    lhs: Expr
    rhs: Expr


@dataclass
class Or:
    loc: Location
    lhs: Expr
    rhs: Expr


@dataclass
class TCO:
    expr: Expr


Stmt = t.Union[Do, Open, Data, Infix, Let]

Expr = t.Union[And, Or, Extern, Coerce, Field, Var, Import, Match, If, Fun,
               Bin, Call, List, Tuple, Lit, SVar, PyCall, TCO]


@dataclass
class Module:
    quals: t.List[str]
    stmts: t.List[Stmt]
