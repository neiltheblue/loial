from .builders import *
import logging

logger = logging.getLogger(__name__)


class Wrapper:
    ''' Wrapper class to execute the compiled code.'''

    def __init__(self, callable):
        self.callable = callable

    def __call__(self, *args, **kwargs):
        return self.callable(*args, **kwargs)


def build(code=None, code_type='Python', config=None, replace=True):
    ''' Decorator to build a function dynamically with provided code.

        Args:            
            code (str): Code to be executed in the function body.            
            code_type (str): Type of the code, default is 'Python'.
            config (class): Options for the builder. This instance type is builder specific
            replace (bool): If True, replaces the function body with the provided code.

        Returns:
            function: A wrapper function that executes the provided code.
        '''

    compiler = None
    if replace:
        for subclass in BaseBuilder.__subclasses__():
            if subclass.__name__.startswith(f'{code_type}_'):
                logger.debug(f'Using compiler: {subclass.__name__}')
                compiler = subclass(code, config)

    if not compiler:
        logger.debug(f'Not replacing code')

    def fun_wrapper(fun):
        ''' Decorator function that wraps the original function.

            Args:
                fun (function): The original function to be wrapped.

            Returns:
                function: A wrapper function that executes the provided code.
            '''

        callable = callable if compiler and (
            callable := compiler.compile(fun)) else fun
        logger.debug(f'Using callable: {callable}')

        return Wrapper(callable)

    return fun_wrapper
