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
from urgent.evaluator import Compiler
import re

keywords = ['let', 'def', 'match', 'rec', 'open', 'infixl', 'infixr', 'import', 'in']
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


session = PromptSession(completer=completer,
                        lexer=PygmentsLexer(UrgentLexer),
                        history=InMemoryHistory())

import dis

def repl(debug=False):
    compiler = Compiler()
    ctx = {}
    while True:
        inp: str = session.prompt('Urgent> ')
        inp = inp.strip()
        if inp.lower() == ':q':
            return
        elif inp.lower() == ':sc':
            print(compiler.main.scope.boundvars)
            return
        try:
            code = get_code_for_repl(inp, compiler)
            if debug:
                dis.dis(code)
            exec(code, ctx, ctx)
        except Exception as e:
            print(e.__class__, e, '\n')
            continue
