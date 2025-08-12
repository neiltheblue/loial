import pytest
from loial import build

def test_build_no_args_leaves_function_unchanged():
    @build()
    def foo(x):
        return x + 1
    assert foo(2) == 3

def test_build_replace_default_replaces_function_body():
    @build(code="return x * 10")
    def bar(x):
        return x + 1
    assert bar(3) == 30

def test_build_replace_true_replaces_function_body():
    @build(code="return x * 10", replace=True)
    def bar(x):
        return x + 1
    assert bar(3) == 30

def test_build_replace_false_leaves_function_unchanged():
    @build(code="return x * 10", replace=False)
    def baz(x):
        return x + 2
    assert baz(4) == 6

def test_build_with_unknown_type_leaves_function_unchanged():
    @build(code="return x * 10", code_type="Unknown", replace=True)
    def qux(x):
        return x + 3
    assert qux(5) == 8

def test_build_replace_true_with_kwargs():
    @build(code="return x + y", replace=True)
    def add(x, y=0):
        return x - y
    assert add(2, y=5) == 7
    assert add(2) == 2

def test_build_compile_error():
    @build(code="all bad", replace=True)
    def bad(x, y=0):
        return x + y
    assert bad(2, 5) == 7
