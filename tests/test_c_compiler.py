import ctypes
import subprocess
import pytest
import os
import pathlib

from pytest_mock import mocker
from loial.builders.c_builder import CC_Builder, CC_Config
from loial import build


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
    @build('''
    int fun0() {
        return 10;
    }
    ''', code_type='CC', replace=False)
    def fun0():
        return 1

    assert fun0() == 1


def test_build_replace_function_body():
    @build('''
    int fun1() {
        return 10;
    }
    ''', code_type='CC')
    def fun1():
        return 1

    assert fun1() == 10


def test_build_replace_function_body_so_exists():
    @build('''
    int fun1() {
        return 10;
    }
    ''', code_type='CC')
    def fun1():
        return 1

    assert fun1.callable.compiled

    @build('''
    int fun1() {
        return 10;
    }
    ''', code_type='CC')
    def fun1():
        return 1

    assert not fun1.callable.compiled
    assert fun1() == 10


def test_build_replace_function_body_so_replace():
    @build('''
    int fun1() {
        return 10;
    }
    ''', code_type='CC')
    def fun1():
        return 1

    assert fun1.callable.compiled

    @build('''
    int fun1() {
        return 20;
    }
    ''', code_type='CC')
    def fun1():
        return 1

    assert fun1.callable.compiled
    assert fun1() == 20


def test_build_replace_function_body_single_int_args():
    @build('''
    int fun2(int a) {
        return a * 10;
    }
    ''', code_type='CC')
    def fun2(a):
        return a

    assert fun2(3) == 30


def test_build_replace_function_body_multiple_int_args():
    @build('''
    int fun3(int a, int b, int c) {
        return a + b + c;
    }
    ''', code_type='CC')
    def fun3(a, b, c):
        return a*b*c

    assert fun3(1, 2, 3) == 6


def test_build_replace_function_body_multiple_int_kwargs():
    @build('''
    int fun4(int a, int b, int c, int d, int e) {
        return ((a + b + c)*d)/e;
    }
    ''', code_type='CC')
    def fun4(a, b, c, d, e):
        return (a*b*c+d)*e

    assert fun4(1, 2, 3, e=2, d=10) == 30


def test_build_replace_function_body_multiple_int_kwargs_with_defaults():
    @build('''
    int fun5(int a, int b, int c, int d, int e) {
        return ((a + b + c)*d)/e;
    }
    ''', code_type='CC')
    def fun5(a, b, c, d, e=2):
        return (a*b*c+d)*e

    assert fun5(1, 2, 3, d=10) == 30


def test_build_compiler_error():
    @build('''
        junk
    ''', code_type='CC')
    def bad(a, b, c, d):
        return (a+b+c)*d

    assert bad(1, 2, 3, d=10) == 60


def test_build_replace_function_body_missing_args():
    @build('''
    int missing(int a, int b, int c, int d) {
        return a + b + c;
    }
    ''', code_type='CC')
    def missing(a, b, c, d):
        return a*b*c

    with pytest.raises(ValueError) as excinfo:
        missing(1, 2, 3)

    assert "Missing required argument: d" in str(excinfo.value)


def test_body_auto_delete():
    conf = CC_Config()
    conf.delete_on_exit = True

    @build('''
    int delete_me() {
        return 10;
    }
    ''', code_type='CC', config=conf)
    def delete_me():
        return 1

    so_file = delete_me.callable.so_file
    delete_me.callable.__del__()
    assert not os.path.exists(so_file)


def test_body_default_delete():
    CC_Builder.config.delete_on_exit = True

    @build('''
    int delete_me() {
        return 10;
    }
    ''', code_type='CC')
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
    @build(r'''
    #include <stdio.h>
    int typed(short a, float b, float c) {
        
        printf("sizes:%d %d %d\n", sizeof(a), sizeof(b), sizeof(c));
        printf("values:%d %d %d\n", a, b, c);
        return a + b + c;
    }
    ''', code_type='CC')
    def typed(a: ctypes.c_short, b: ctypes.c_float, c: ctypes.c_float, d: ctypes.c_float = 2.0):
        return a*b*c

    assert typed(1, 2.0, c=3.0) == 6
    

def test_build_no_replace_function_typed_args():
    @build(r'''
    #include <stdio.h>
    int typed(short a, float b, float c) {
        
        printf("sizes:%d %d %d\n", sizeof(a), sizeof(b), sizeof(c));
        printf("values:%d %d %d\n", a, b, c);
        return a + b + c;
    }
    ''', code_type='CC', replace=False)
    def typed(a: ctypes.c_short, b: ctypes.c_float, c: ctypes.c_float, d: ctypes.c_float = 2.0):
        return a*b*c*2

    assert typed(1, 2.0, c=3.0) == 12

def test_build_replace_compiler(mocker):

    spy = mocker.spy(subprocess, 'run')

    conf = CC_Config()
    conf.compiler = 'gcc'

    @build(r'''
    int comp(int a, int b, int c) {
        return a + b + c;
    }
    ''', code_type='CC', config=conf)
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

    @build(r'''
    int comp(int a, int b, int c) {
        return a + b + c;
    }
    ''', code_type='CC', config=conf)
    def comp(a, b, c):
        return a*b*c

    assert comp(1, 2, 3) == 6
    spy.assert_called_once()
    assert spy.call_args_list[0].args[0][len(conf.compier_opts)] == '-time'
    
    
def test_build_replace_function_name(mocker):

    conf = CC_Config()
    conf.function='main'

    @build(r'''
    int main(int a, int b, int c) {
        return a + b + c;
    }
    ''', code_type='CC', config=conf)
    def not_main(a, b, c):
        return a*b*c

    assert not_main(1, 2, 3) == 6


def test_build_replace_function_return_type():
    @build(r'''
    #include <stdio.h>
    float freturn(int a, int b, int c) {
        return (a + b + c)/2.0;
    }
    ''', code_type='CC')
    def freturn(a, b, c) -> ctypes.c_float:
        return a*b*c

    assert freturn(1, 2, 3) == 3.0
    
    
def test_build_no_replace_function_return_type():
    @build(r'''
    #include <stdio.h>
    float freturn(int a, int b, int c) {
        return (a + b + c)/2.0;
    }
    ''', code_type='CC', replace=False)
    def freturn(a, b, c) -> ctypes.c_float:
        return a*b*c

    assert freturn(1, 2, 3) == 6
