import glob
import pathlib
import shutil
import tempfile
import subprocess
import ctypes
import inspect
import os
import logging
from pathlib import Path
from .builder import BaseBuilder

logger = logging.getLogger(__name__)


class CC_Config():
    """
    Configuration class for managing the cache directory used by C_Builder.
    To case an argument to a specific c type, provide a hint in method signature:

        def dun(a: ctypes.c_float, b: ctypes.c_float = 2.0):

    Attributes:
        cache_search_path (list): List of directory paths (as strings) to search for or create as the cache location.
        cache (Path or None): The resolved cache directory path, or None if not yet set.
        compiler (str): The compiler app. [cc]
        compiler_opts ([str]): Compiler options. ["-fPIC", "-shared", "-xc"]
        delete_on_exit (bool): The default delete_on_exit value if not set per build. [False]
        function (str): The function name to call, if None then the name of the funciton being replaced is used. [None]

    """

    def __init__(self):
        self.cache_search_path = [
            f'{Path.home()}/.loial', './loial']
        self.compier_opts = ["-fPIC", "-shared", "-xc"]
        self.__cache = None
        self.delete_on_exit = False
        self.compiler = 'cc'
        self.function = None

    @property
    def cache(self):
        ''' Get the cache location for compiled code.'''
        if not self.__cache:
            for search_path in self.cache_search_path:
                try:
                    os.makedirs(search_path, exist_ok=True)
                    self.__cache = Path(search_path)
                    logger.debug(f'Setting cache path to: {search_path}')
                    break
                except Exception as e:
                    logger.debug(
                        f'Error creating cache directory {search_path}: {e}')
            else:
                self.__cache = pathlib.Path(
                    tempfile.TemporaryDirectory(prefix='loial_').name)
                logger.debug(
                    f'Using temporary directory for cache: {self.__cache}')
        return self.__cache

    @cache.setter
    def cache(self, value):
        ''' Set the cache locaion for compiled code.'''
        self.__cache = value


class CC_Builder(BaseBuilder):
    ''' CC Compiler for dynamically compiling code into a function body.

            Compiler Opts:
            delete_on_exit (bool): - If True, deletes the compiled shared object file on exit. [Default set by config]
    '''

    config = CC_Config()

    def __init__(self, code, config=None):
        self.config = config if config else CC_Builder.config
        BaseBuilder.__init__(self, code, config)

    def clean_cache():
        ''' Clean up the cache directory.'''
        cache_path = CC_Builder.config.cache
        if cache_path and cache_path.exists():
            try:
                logger.debug(f"Removing cache directory: {cache_path}")
                shutil.rmtree(cache_path, ignore_errors=True)
            except OSError as e:
                logger.error(
                    f"Error removing cache directory: {cache_path}", exc_info=True)
            CC_Builder.config.cache = None

    def compile(self, fun):
        self.fun = fun
        self.so_file = f"{CC_Builder.config.cache}/{self.fun.__module__}.{self.fun.__name__}_{abs(hash(self.code))}.so"
        logger.debug(f'Shared object file: {self.so_file}')
        for existing in glob.glob(f"./{self.fun.__module__}.{self.fun.__name__}_*.so"):
            if existing != self.so_file:
                logger.debug(f'Removing existing shared object: {existing}')
                os.remove(existing)

        if not os.path.exists(self.so_file):
            try:
                out = subprocess.run([self.config.compiler] + self.config.compier_opts + ["-o", self.so_file,  "-"],
                                     text=True, capture_output=True,
                                     input=self.code, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(
                    f'Error compiling C code: {e.stderr}', exc_info=True)
                logger.debug(f'{"=" * 10}\n{self.code}')
                return None
            else:
                logger.debug(
                    f'Compiled C code to shared object: {self.so_file}\n{out.stdout}')
            self.compiled = True
        else:
            self.compiled = False

        self.main = ctypes.CDLL(self.so_file)
        return self

    def __call__(self, *args, **kwargs):
        fun_name = self.config.function if self.config.function else self.fun.__name__
        all_args = self.build_args(*args, **kwargs)
        logger.debug(f'Calling function: {fun_name} with args: {all_args}')
        fun = getattr(self.main, fun_name)
        sig = inspect.signature(self.fun)
        if sig.return_annotation != inspect._empty:
            fun.restype = sig.return_annotation
        return fun(*tuple(all_args))

    def build_args(self, *args, **kwargs):
        sig = inspect.signature(self.fun)
        param_names = list(sig.parameters.keys())
        all_args = []
        for i, name in enumerate(param_names[:len(args)]):
            # annotation = sig.parameters[name].annotation
            all_args.append(self.type_arg(args[i], sig, name))
        for i, name in enumerate(param_names[len(args):]):
            if name in kwargs:
                all_args.append(self.type_arg(kwargs.get(name), sig, name))
            else:
                default = sig.parameters[name].default
                if default is inspect.Parameter.empty:
                    raise ValueError(f'Missing required argument: {name}')
                all_args.append(self.type_arg(default, sig, name))
        return (all_args)

    def type_arg(self, arg, sig, name):
        param = sig.parameters[name]
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            return arg
        else:
            return annotation(arg)

    def clean(self):
        ''' Clean up the compiled shared object file.'''
        try:
            if self.so_file and os.path.exists(self.so_file):
                logger.debug(f"Removing file: {self.so_file}")
                os.remove(self.so_file)
        except OSError as e:
            logger.debug(f"Error removing file: {self.so_file}", exc_info=True)
        self.so_file = None

    def __del__(self):
        ''' Destructor to clean up the compiled shared object file.'''
        if self.config.delete_on_exit:
            self.clean()
