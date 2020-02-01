"""
A basic manner for loading urgent modules.
"""
from __future__ import annotations
from typing import *
from pathlib import Path
from urgent.parser_wrap import parse
from urgent.ast import Module
from warnings import warn
import toml
import os

__all__ = ['Config']

_template_toml = """
[basic]
out="a.pyc"
src=[]
version = [0, 0, 1]
"""


class Config:
    # name of output .pyc(standalone)
    out: str
    src_dirs: List[str]
    version: List[int]

    def load_modules(self):
        modules = {}
        for dir in self.src_dirs:
            load_modules_from_src_dir(dir, modules)
        return modules

    @classmethod
    def parse(cls, src, path: Path):
        conf = parse_config(src)
        dir = conf.path = path.parent
        conf.src_dirs = [str(dir / each) for each in conf.src_dirs]
        return conf

    @classmethod
    def create(cls, path: Path):
        if not path.exists():
            path.parent.mkdir(parents=True)
            with path.open('w') as f:
                f.write(_template_toml)

    @classmethod
    def load(cls, path):
        path = Path(path).expanduser()
        cls.create(path)
        with path.open() as f:
            return cls.parse(f.read(), path)


def parse_config(src):
    """TODO: validate and error message
    """
    config_dict = toml.loads(src)['basic']
    conf = Config()
    conf.out = config_dict.get('out', 'a.pyc')
    conf.src_dirs = config_dict['src']
    conf.version = config_dict.get('version', [0, 1, 0])
    return conf


def load_modules_from_src_dir(dir, modules):
    for each in Path(dir).iterdir():
        if each.suffix == '.ugt':
            with each.open() as f:
                fname = str(each.absolute())
                ast: Module = parse(f.read(), fname)
                quals = tuple(ast.quals)
                if quals in modules:
                    warn(
                        "Module {} at {} seems already defined, but now a duplicate one got raised, overloading..."
                        .format(
                            '.'.join(quals),
                            str(each.absolute()),
                        ))
                modules[quals] = ast

    return modules
