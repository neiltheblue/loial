import glob
import pathlib
import shutil
import tempfile
import subprocess
import ctypes
import inspect
import os
import logging
from copy import deepcopy
from pathlib import Path
from .builder import BaseBuilder

logger = logging.getLogger(__name__)


def cc_build(code=None,  config=None, replace=True):
    """ Helper decorator to default the code_type t0 'CC' """
    from ..builder import build
    return build(code, code_type='CC', config=config, replace=replace)


def c_struct(cls):
    """ Class decorator to add auto C struct support """
    cls_dict = cls.__dict__.copy()
    cls_dict['_fields_'] = [(name, cls.__annotations__[name])
                            for name in cls.__annotations__]
    return type(cls.__name__,  (C_Struct,) + cls.__bases__, cls_dict)


class C_Struct(ctypes.Structure):
    """ Class mix-in to generate C structs from ctype fields.

    A struct object can be passed in by subclassing CC_Struct and defining the attribute
    types in the class _fields_:

        class Record(CC_Struct):
        _fields_ = [("first", ctypes.c_int),
                    ("second", ctypes.c_bool)]

        @cc_build(r'''
            #include<stdio.h>
            '''
                + Record.define()
                + r'''

        int stru(Record r) {
            printf("first:%d (%lu)\n", r.first, sizeof(r.first));
            printf("second:%d (%lu)\n", r.second, sizeof(r.second));
            ...
            )
            ''')
        def stru(dom):
            ...

        dom = Record()
        dom.first = 3
        dom.second = True
        stru(dom)

    A class can be auto wrapped into a CC_Struct when attributes has annotations:

    @c_struct
    class LocalStruct():
        a: ctypes.c_int
        b: ctypes.c_float
        multi: LocalInnerStruct

    """

    def match_type(c_type):
        match c_type:
            case ctypes.c_bool:
                return '_Bool'
            case ctypes.c_char:
                return 'char'
            case ctypes.c_wchar:
                return 'wchar_t'
            case ctypes.c_byte:
                return 'char'
            case ctypes.c_ubyte:
                return 'unsigned char'
            case ctypes.c_short:
                return 'short'
            case ctypes.c_ushort:
                return 'unsigned short'
            case ctypes.c_int:
                return 'int'
            case ctypes.c_uint:
                return 'unsigned int'
            case ctypes.c_long:
                return 'long'
            case ctypes.c_ulong:
                return 'unsigned long'
            case ctypes.c_longlong:
                return 'long long'
            case ctypes.c_ulonglong:
                return 'unsigned long long'
            case ctypes.c_size_t:
                return 'size_t'
            case ctypes.c_ssize_t:
                return 'ssize_t'
            case ctypes.c_float:
                return 'float'
            case ctypes.c_double:
                return 'double'
            case ctypes.c_longdouble:
                return 'long double'
            case ctypes.c_char_p:
                return 'char *'
            case ctypes.c_wchar_p:
                return 'wchar_t *'
            case ctypes.c_void_p:
                return 'void *'
            case _:
                return c_type.__name__

    @classmethod
    def define(cls):
        return f'''
typedef struct {{
\t{';\n\t'.join((C_Struct.match_type(field[1])+' '+field[0] for field in cls._fields_))};
}} {cls.__name__};
'''


class AsPointer():
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class AsRef():
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class CC_Config():
    """
    Configuration class for managing the cache directory used by C_Builder.
    To cast an argument to a specific c type, provide a hint in method signature:

        def fun1(a: ctypes.c_float, b: ctypes.c_float = 2.0):
        ...

    To pass an argument by ref, a hint must be provided and the value wrapped in AsRef:

        @cc_build('''
        int ref(int* a, int b) {
            ...
        }
        ''')
        def ref(a: ctypes.c_int, b):
        ...

        ref(AsRef(3), 4)

    An alterntive it to add a config ref entry, and a hint must still be provided:

        @cc_build('''
        int ref(int* a, int b) {
            ...
        }
        ''', CC_Config(refs={'a'}))
        def ref(a: ctypes.c_int, b):
        ...

        ref(AsRef(3, 4)

    To pass an argument as a pointer it must be wraped in an AsPointer and a type hint must be provided:

        @cc_build('''
        int ref(int* a) {
            *a=99;
            ...
        }
        ''')
        def ref(a: ctypes.c_int, b):
            ...

        a = AsPointer(3)
        assert a.value==99

    To pass an array argument it must be passed as an instance of a list and a type hint must be provided:

    @cc_build('''
    int arr_fun(int a[]) {
        ...
    }
    ''')
    def arr_fun(a: ctypes.c_int):
        ...

    arr_fun([1, 2, 3])

    To define the function return type a hint should be applied in method signature:

        def fun2(a, b) -> ctypes.c_float:
        ...


    Attributes:
        cache_search_path (str,..): List of directory paths (as strings) to search for or create as the cache location.
        cache (Path or None): The resolved cache directory path, or None if not yet set.
        compiler (str): The compiler app. [cc]
        compiler_opts (str,..): Compiler options. ["-fPIC", "-shared", "-xc"]
        delete_on_exit (bool): The default delete_on_exit value if not set per build. [False]
        function (str): The function name to call, if None then the name of the funciton being replaced is used. [None]
        refs ([str,...]): The list of arguments to auto parse as references.
        includes ([str,...]): The list of include locations, by default the python source dir is added to this list.
    """

    cache_search_path = (os.path.join(Path.home(), '.loial'), Path('./loial'))
    compiler_opts = ('-fPIC', '-shared', '-xc')
    delete_on_exit = False
    compiler = 'cc'

    def __init__(self, **kwargs):
        self.cache_search_path = CC_Config.cache_search_path
        self.compiler_opts = CC_Config.compiler_opts
        self.delete_on_exit = CC_Config.delete_on_exit
        self.compiler = CC_Config.compiler

        self.function = None
        self.refs = []
        self.includes = []

        self.__cache = None

        for name in kwargs.keys():
            setattr(self, name, kwargs[name])

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
        
    def clean_cache(self):
        ''' Clean up the cache directory.'''
        cache_path = self.cache
        if cache_path and cache_path.exists():
            try:
                logger.debug(f"Removing cache directory: {cache_path}")
                shutil.rmtree(cache_path, ignore_errors=True)
            except OSError as e:
                logger.error(
                    f"Error removing cache directory: {cache_path}", exc_info=True)
            self.cache = None

class CC_Builder(BaseBuilder):
    ''' CC Compiler for dynamically compiling code into a function body. '''

    def __init__(self, code, config=None):
        self.config = config if config else CC_Config()
        logger.debug(f"Input code:\n{code}")
        BaseBuilder.__init__(self, code, config)


    @staticmethod
    def cc_compile(code, filename, config):
        try:
            inc = [i for p in config.includes for i in ['-I', str(p)]]
            out = subprocess.run([config.compiler]
                                 + inc
                                 + list(config.compiler_opts)
                                 + ["-o", filename,  "-"],
                                 text=True, capture_output=True,
                                 input=code, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(
                f'Error compiling code: {e.stderr}', exc_info=True)
            logger.debug(f'{"=" * 10}\n{code}')
            return None
        else:
            logger.debug(
                f'Compiled C code to: {filename}\n{out.stdout}')
            return filename

    def compile(self, fun):
        self.fun = fun
        self.so_file = f"{self.config.cache}/{self.fun.__module__}.{self.fun.__name__}_{abs(hash(self.code))}.so"
        logger.debug(f'Shared object file: {self.so_file}')
        for existing in glob.glob(f"./{self.fun.__module__}.{self.fun.__name__}_*.so"):
            if existing != self.so_file:
                logger.debug(f'Removing existing shared object: {existing}')
                os.remove(existing)

        self.compiled = False
        if not os.path.exists(self.so_file):
            parent = Path(self.fun.__code__.co_filename).parent.absolute()
            if not parent in self.config.includes:
                self.config.includes.append(parent)
            if CC_Builder.cc_compile(self.code, self.so_file, self.config):
                self.compiled = True
            else:
                return None

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
        rtn = fun(*tuple(all_args))
        for i, arg in enumerate(args):
            if isinstance(arg, AsPointer):
                arg.value = all_args[i].contents.value
        return rtn

    def build_args(self, *args, **kwargs):
        sig = inspect.signature(self.fun)
        param_names = list(sig.parameters.keys())
        all_args = []
        for i, name in enumerate(param_names[:len(args)]):
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
        if isinstance(arg, list):
            arr = annotation * len(arg)
            val = arr(*tuple([self.type_arg(v, sig, name) for v in arg]))
        else:
            val = arg.value if isinstance(arg, AsPointer) else arg
            if annotation is inspect.Parameter.empty:
                val = val
            else:
                if isinstance(val, AsRef):
                    val = ctypes.byref(annotation(val.value))
                elif name in self.config.refs:
                    val = ctypes.byref(annotation(val))
                else:
                    val = annotation(val)

            if isinstance(arg, AsPointer):
                val = ctypes.pointer(val)

        return val

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
