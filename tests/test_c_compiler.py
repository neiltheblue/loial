import ctypes
import subprocess
import pytest
import os
import pathlib
from pytest_mock import mocker
from loial.builders.cc_builder import CC_Builder, CC_Config, AsPointer, AsRef, cc_build


@pytest.fixture(autouse=True)
def auto():
    temp_search_path = CC_Builder.config.cache_search_path
    CC_Builder.cache_search_path = ['./.cache']
    yield
    CC_Builder.clean_cache()
    CC_Builder.config.cache_search_path = temp_search_path
    CC_Builder.config.cache = None
    CC_Builder.config.delete_on_exit = False


def test_build_dont_replace_function_body():
    @cc_build('''
    int fun0() {
        return 10;
    }
    ''',  replace=False)
    def fun0():
        return 1

    assert fun0() == 1


def test_build_replace_function_body():
    @cc_build('''
    int fun1() {
        return 10;
    }
    ''')
    def fun1():
        return 1

    assert fun1() == 10


def test_build_replace_function_body_so_exists():
    @cc_build('''
    int fun1() {
        return 10;
    }
    ''')
    def fun1():
        return 1

    assert fun1.callable.compiled

    @cc_build('''
    int fun1() {
        return 10;
    }
    ''')
    def fun1():
        return 1

    assert not fun1.callable.compiled
    assert fun1() == 10


def test_build_replace_function_body_so_replace():
    @cc_build('''
    int fun1() {
        return 10;
    }
    ''')
    def fun1():
        return 1

    assert fun1.callable.compiled

    @cc_build('''
    int fun1() {
        return 20;
    }
    ''')
    def fun1():
        return 1

    assert fun1.callable.compiled
    assert fun1() == 20


def test_build_replace_function_body_single_int_args():
    @cc_build('''
    int fun2(int a) {
        return a * 10;
    }
    ''')
    def fun2(a):
        return a

    assert fun2(3) == 30


def test_build_replace_function_body_multiple_int_args():
    @cc_build('''
    int fun3(int a, int b, int c) {
        return a + b + c;
    }
    ''')
    def fun3(a, b, c):
        return a*b*c

    assert fun3(1, 2, 3) == 6


def test_build_replace_function_body_multiple_int_kwargs():
    @cc_build('''
    int fun4(int a, int b, int c, int d, int e) {
        return ((a + b + c)*d)/e;
    }
    ''')
    def fun4(a, b, c, d, e):
        return (a*b*c+d)*e

    assert fun4(1, 2, 3, e=2, d=10) == 30


def test_build_replace_function_body_multiple_int_kwargs_with_defaults():
    @cc_build('''
    int fun5(int a, int b, int c, int d, int e) {
        return ((a + b + c)*d)/e;
    }
    ''')
    def fun5(a, b, c, d, e=2):
        return (a*b*c+d)*e

    assert fun5(1, 2, 3, d=10) == 30


def test_build_compiler_error():
    @cc_build('''
        junk
    ''')
    def bad(a, b, c, d):
        return (a+b+c)*d

    assert bad(1, 2, 3, d=10) == 60


def test_build_replace_function_body_missing_args():
    @cc_build('''
    int missing(int a, int b, int c, int d) {
        return a + b + c;
    }
    ''')
    def missing(a, b, c, d):
        return a*b*c

    with pytest.raises(ValueError) as excinfo:
        missing(1, 2, 3)

    assert "Missing required argument: d" in str(excinfo.value)


def test_body_auto_delete():
    CC_Config(delete_on_exit=True)

    @cc_build('''
    int delete_me() {
        return 10;
    }
    ''', CC_Config(delete_on_exit=True))
    def delete_me():
        return 1

    so_file = delete_me.callable.so_file
    delete_me.callable.__del__()
    assert not os.path.exists(so_file)


def test_body_default_delete():
    CC_Builder.config.delete_on_exit = True

    @cc_build('''
    int delete_me() {
        return 10;
    }
    ''')
    def delete_me():
        return 1

    so_file = delete_me.callable.so_file
    delete_me.callable.__del__()
    assert not os.path.exists(so_file)


def test_cache_path():
    cache = '.cache'
    try:
        CC_Builder.config.cache = None
        CC_Builder.config.cache_search_path = [f'{cache}/test_cache1']
        assert CC_Builder.config.cache == pathlib.Path(f'{cache}/test_cache1')
    finally:
        CC_Builder.clean_cache()

    try:
        CC_Builder.config.cache = None
        CC_Builder.config.cache_search_path = [None, f'{cache}/test_cache2']
        assert CC_Builder.config.cache == pathlib.Path(f'{cache}/test_cache2')
    finally:
        CC_Builder.clean_cache()

    CC_Builder.config.cache = None
    CC_Builder.config.cache_search_path = [None]
    assert isinstance(CC_Builder.config.cache, pathlib.Path)


def test_build_replace_function_typed_args():
    @cc_build(r'''
    #include <stdio.h>
    int typed(short a, float b, float c) {
        
        printf("sizes:%d %d %d\n", sizeof(a), sizeof(b), sizeof(c));
        printf("values:%d %d %d\n", a, b, c);
        return a + b + c;
    }
    ''')
    def typed(a: ctypes.c_short, b: ctypes.c_float, c: ctypes.c_float, d: ctypes.c_float = 2.0):
        return a*b*c

    assert typed(1, 2.0, c=3.0) == 6


def test_build_no_replace_function_typed_args():
    @cc_build(r'''
    #include <stdio.h>
    int typed(short a, float b, float c) {
        
        printf("sizes:%d %d %d\n", sizeof(a), sizeof(b), sizeof(c));
        printf("values:%d %d %d\n", a, b, c);
        return a + b + c;
    }
    ''', replace=False)
    def typed(a: ctypes.c_short, b: ctypes.c_float, c: ctypes.c_float, d: ctypes.c_float = 2.0):
        return a*b*c*2

    assert typed(1, 2.0, c=3.0) == 12


def test_build_replace_compiler(mocker):

    spy = mocker.spy(subprocess, 'run')

    @cc_build(r'''
    int comp(int a, int b, int c) {
        return a + b + c;
    }
    ''', CC_Config(compiler='gcc'))
    def comp(a, b, c):
        return a*b*c

    assert comp(1, 2, 3) == 6
    assert comp.callable.config.compiler == 'gcc'
    spy.assert_called_once()
    assert spy.call_args_list[0].args[0][0] == 'gcc'


def test_build_replace_compiler_opts(mocker):

    spy = mocker.spy(subprocess, 'run')

    conf = CC_Config()
    conf.compier_opts.append('-time')

    @cc_build(r'''
    int comp(int a, int b, int c) {
        return a + b + c;
    }
    ''', config=conf)
    def comp(a, b, c):
        return a*b*c

    assert comp(1, 2, 3) == 6
    spy.assert_called_once()
    assert spy.call_args_list[0].args[0][len(conf.compier_opts)] == '-time'


def test_build_replace_function_name(mocker):

    @cc_build(r'''
    int main(int a, int b, int c) {
        return a + b + c;
    }
    ''', CC_Config(function='main'))
    def not_main(a, b, c):
        return a*b*c

    assert not_main(1, 2, 3) == 6


def test_build_replace_function_return_type():
    @cc_build(r'''
    float freturn(int a, int b, int c) {
        return (a + b + c)/2.0;
    }
    ''')
    def freturn(a, b, c) -> ctypes.c_float:
        return a*b*c

    assert freturn(1, 2, 3) == 3.0


def test_build_no_replace_function_return_type():
    @cc_build(r'''
    float freturn(int a, int b, int c) {
        return (a + b + c)/2.0;
    }
    ''', replace=False)
    def freturn(a, b, c) -> ctypes.c_float:
        return a*b*c

    assert freturn(1, 2, 3) == 6


def test_build_replace_function_pass_args_byref():

    @cc_build('''
    int ref(int* a, int b) {
        return *a * b;
    }
    ''')
    def ref(a: ctypes.c_int, b):
        return a+b

    a = 3
    b = 10
    assert ref(AsRef(a), b) == 30
    

def test_build_replace_function_pass_args_by_auto_ref():

    @cc_build('''
    int ref(int* a, int b) {
        return *a * b;
    }
    ''', CC_Config(refs={'a'}))
    def ref(a: ctypes.c_int, b):
        return a+b

    a = 3
    b = 10
    assert ref(a, b) == 30
    
    
def test_build_no_replace_function_pass_args_byref():

    @cc_build('''
    int ref(int* a, int b) {
        return *a * b;
    }
    ''', replace=False)
    def ref(a: ctypes.c_int, b):
        return a()+b

    a = 3
    b = 10
    assert ref(AsRef(a), b) == 13


def test_build_replace_function_pass_args_pointer():

    @cc_build('''
    int ptr(int* a, int b) {
        *a=99;
        return *a * b;
    }
    ''')
    def ptr(a: ctypes.c_int, b):
        return a+b

    a = AsPointer(3)
    b = 10
    assert ptr(a, b) == 990
    assert a.value == 99
    

def test_build_no_replace_function_pass_args_pointer():

    @cc_build('''
    int ptr(int* a, int b) {
        *a=99;
        return *a * b;
    }
    ''', replace=False)
    def ptr(a: ctypes.c_int, b):
        a.value=10
        return a()+b

    a = AsPointer(3)
    b = 10
    assert ptr(a, b) == 20
    assert a.value == 10

