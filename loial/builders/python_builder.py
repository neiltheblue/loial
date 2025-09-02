from .builder import BaseBuilder
import inspect
import logging

logger = logging.getLogger(__name__)


class Python_Builder(BaseBuilder):
    ''' Python Compiler for dynamically compiling code into a function body.'''

    def __init__(self, code, config=None):
        BaseBuilder.__init__(self, code, config)

    def compile(self, fun):
        if not self.code:
            return None
        source = f'def __{fun.__name__}{inspect.signature(fun)}:'
        for line in self.code.splitlines():
            source += f'\t{line}\n'
        source += f'__return_value__=__{fun.__name__}(*args, **kwargs)'
        try:
            self.compiled = compile(source, '<string>', 'exec')
        except Exception as e:
            logger.error(f'Error compiling code, using defaut: {e}')
            return None
        else:
            return self

    def __call__(self, *args, **kwargs):
        locals = {'args': args, 'kwargs': kwargs}
        exec(self.compiled, {}, locals)
        return locals['__return_value__']
