from __future__ import annotations
from dataclasses import dataclass
import typing as t

Location = t.Tuple[int, int, str]



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
    slots: int


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
class List:
    loc: Location
    elts: t.List[Expr]


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


Stmt = t.Union[Do, Open, Cons, Infix, Let]

Expr = t.Union[Extern, Coerce, Field, Var, Import, Match, If, Fun, Bin,
               Call, List, Tuple, Lit]


@dataclass
class Module:
    quals: t.List[str]
    stmts: t.List[Stmt]
