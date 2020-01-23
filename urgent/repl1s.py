"""
A very basic REPL implemented in 1s.
"""
from pygments.lexers.html import RegexLexer
from pygments import token
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.lexers import PygmentsLexer
from urgent.cli import get_code_for_repl
from urgent.compiler import Compiler, Report
import re
import dis
import traceback

keywords = [
    'let', 'def', 'match', 'rec', 'open', 'infixl', 'infixr', 'import', 'in',
    'data'
]
operators = ['->', '.', '?', '=>']
completer = WordCompleter(keywords)


class UrgentLexer(RegexLexer):
    name = 'hmf'

    tokens = {
        'root': [
            *[(re.escape(k), token.Keyword) for k in keywords],
            *[(re.escape(o), token.Operator) for o in operators],
            (r"#([^\\#]+|\\.)*?#", token.Literal), (r"\d+", token.Number),
            (r"[-$\.a-zA-Z_\u4e00-\u9fa5][\-\!-$\.a-zA-Z0-9_\u4e00-\u9fa5]*",
             token.Name), (r'''"([^\\"]+|\\.)*?"''', token.String),
            (r'\s+', token.Whitespace)
        ]
    }


def repl(debug=False, project: str = ""):
    session = PromptSession(completer=completer,
                            lexer=PygmentsLexer(UrgentLexer),
                            history=InMemoryHistory())

    compiler = Compiler(project)
    ctx = {}
    tracing_limit = 2 if debug else 0
    while True:
        inp: str = session.prompt('Urgent> ')
        inp = inp.strip()
        if inp.lower() == ':q':
            return
        elif inp.lower() == ':sc':
            print(compiler.main.scope.boundvars)
            continue
        try:
            code = get_code_for_repl(inp, compiler)
            if debug:
                dis.dis(code)
            print('=>', eval(code, ctx, ctx))
        except SyntaxError:
            traceback.print_exc(limit=tracing_limit)
        except Report as e:
            if debug:
                traceback.print_exc(limit=tracing_limit)
            print(repr(e), '\n')
            continue
