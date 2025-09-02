import ctypes
import subprocess
import pytest
import os
import pathlib
from pytest_mock import mocker
from loial.builders.cc_builder import CC_Builder, CC_Config, AsPointer, AsRef, C_Struct, cc_build, c_struct


@pytest.fixture(autouse=True)
def auto():
    temp_search_path = CC_Config.cache_search_path
    CC_Config.cache_search_path = ['./.cache']
    yield
    CC_Config().clean_cache()
    CC_Config.cache_search_path = temp_search_path


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

    code = '''
    int fun1() {
        return 10;
    }
    '''

    @cc_build(code)
    def fun1():
        return 1

    assert fun1.callable.compiled

    @cc_build(code)
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
    try:
        CC_Config.delete_on_exit = True

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
    finally:
        CC_Config.delete_on_exit = False


def test_cache_path():
    cache = '.cache'
    config = CC_Config()
    try:
        config.cache = None
        config.cache_search_path = [f'{cache}/test_cache1']
        assert config.cache == pathlib.Path(f'{cache}/test_cache1')
    finally:
        config.clean_cache()

    try:
        config.cache = None
        config.cache_search_path = [None, f'{cache}/test_cache2']
        assert config.cache == pathlib.Path(f'{cache}/test_cache2')
    finally:
        config.clean_cache()

    config.cache = None
    config.cache_search_path = [None]
    assert isinstance(config.cache, pathlib.Path)


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
    conf.compiler_opts = list(conf.compiler_opts) + ['-time']

    @cc_build(r'''
    int comp(int a, int b, int c) {
        return a + b + c;
    }
    ''', config=conf)
    def comp(a, b, c):
        return a*b*c

    assert comp(1, 2, 3) == 6
    spy.assert_called_once()
    assert '-time' in spy.call_args_list[0].args[0]


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
        a.value = 10
        return a()+b

    a = AsPointer(3)
    b = 10
    assert ptr(a, b) == 20
    assert a.value == 10


def test_build_replace_function_body_array_int_args():
    @cc_build('''
    int arr(int a[], int b) {
        int i;
        int sum=0;
        for(i=0; i<b; i++)
        {
            sum = sum + a[i];
        }        
        return sum;
    }
    ''')
    def arr(a: ctypes.c_int, b):
        return max(a)

    assert arr([1, 2, 3], 3) == 6


def test_build_replace_function_body_struct_args():

    class Field(C_Struct):
        _fields_ = [("a", ctypes.c_int),
                    ("b", ctypes.c_int)]

    class Record(C_Struct):
        _fields_ = [("first", ctypes.c_int),
                    ("second", ctypes.c_bool),
                    ("third", ctypes.c_char),
                    ("fourth", ctypes.c_wchar),
                    ("fifth", ctypes.c_byte),
                    ("sixth", ctypes.c_ubyte),
                    ("seventh", ctypes.c_short),
                    ("eighth", ctypes.c_ushort),
                    ("nineth", ctypes.c_int),
                    ("tenth", ctypes.c_uint),
                    ("eleventh", ctypes.c_long),
                    ("twelth", ctypes.c_ulong),
                    ("thirteenth", ctypes.c_longlong),
                    ("fourteenth", ctypes.c_ulonglong),
                    ("fifteenth", ctypes.c_size_t),
                    ("sixteenth", ctypes.c_ssize_t),
                    ("seventeenth", ctypes.c_float),
                    ("eighteenth", ctypes.c_double),
                    ("nineteenth", ctypes.c_longdouble),
                    ("twenty", ctypes.c_char_p),
                    ("twentyone", ctypes.c_wchar_p),
                    ("twentytwo", ctypes.c_void_p),
                    ("field", Field),
                    ]

    @cc_build('''
    #include<stdio.h>     
    #include <wchar.h>                       
              '''
              + Field.define()
              + Record.define() +
              r'''
    
    int stru(Record r) {
        printf("first:%d (%lu)\n", r.first, sizeof(r.first));
        printf("second:%d (%lu)\n", r.second, sizeof(r.second));
        printf("third:%c (%lu)\n", r.third, sizeof(r.third));
        printf("fourth:%ld (%lu)\n", r.fourth, sizeof(r.fourth));
        printf("fifth:%d (%lu)\n", r.fifth, sizeof(r.fifth));
        printf("sixth:%d (%lu)\n", r.sixth, sizeof(r.sixth));
        printf("seventh:%d (%lu)\n", r.seventh, sizeof(r.seventh));
        printf("eighth:%d (%lu)\n", r.eighth, sizeof(r.eighth));                
        printf("nineth:%d (%lu)\n", r.nineth, sizeof(r.nineth));
        printf("tenth:%u (%lu)\n", r.tenth, sizeof(r.tenth));        
        printf("eleventh:%ld (%lu)\n", r.eleventh, sizeof(r.eleventh));
        printf("twelth:%lu (%lu)\n", r.twelth, sizeof(r.twelth));
        printf("thirteenth:%lld (%lu)\n", r.tenth, sizeof(r.thirteenth));
        printf("fourteenth:%llu (%lu)\n", r.fourteenth, sizeof(r.fourteenth));  
        
        printf("fifteenth:%zx (%lu)\n", r.fifteenth, sizeof(r.fifteenth));  
        printf("sixteenth:%zx (%lu)\n", r.sixteenth, sizeof(r.sixteenth));  
        printf("seventeenth:%f (%lu)\n", r.seventeenth, sizeof(r.seventeenth));  
        printf("eighteenth:%lf (%lu)\n", r.eighteenth, sizeof(r.eighteenth));  
        printf("nineteenth:%llf (%lu)\n", r.nineteenth, sizeof(r.nineteenth));          
        printf("twenty:%c (%lu)\n", *r.twenty, sizeof(r.twenty));   
        printf("twentyone:%ld (%lu)\n", *r.twentyone, sizeof(r.twentyone));  
        printf("twentytwo:%lu (%lu)\n", r.twentytwo, sizeof(r.twentytwo)); 
        printf("field:%d %d\n", r.field.a, r.field.b);                                                                                                       
        return r.field.a * r.field.b;
    }
    ''')
    def stru(dom):
        return str(dom)

    dom = Record()
    dom.first = 3
    dom.second = True
    dom.third = b'a'
    dom.fourth = 'b'
    dom.fifth = 127
    dom.sixth = 255
    dom.seventh = -1
    dom.eighth = -1
    dom.nineth = -2
    dom.tenth = -2
    dom.eleventh = -3
    dom.twelth = -3
    dom.thirteenth = -4
    dom.fourteenth = -4
    dom.fifteenth = 123
    dom.sixteenth = 124
    dom.seventeenth = 1.23
    dom.eighteenth = 4.32
    dom.nineteenth = 2.34
    dom.twenty = b'c'
    dom.twentyone = 'd'
    dom.twentytwo = 999
    field = Field()
    field.a = 2
    field.b = 10
    dom.field = field

    assert stru(dom) == 20


def test_build_replace_function_body_auto_struct_args():

    class SuperClass():
        pass

    @c_struct
    class LocalInnerStruct(SuperClass):
        c: ctypes.c_short

    @c_struct
    class LocalStruct():
        a: ctypes.c_int
        b: ctypes.c_float
        multi: LocalInnerStruct

    @cc_build('''
    #include<stdio.h>     
              '''
              + LocalInnerStruct.define()
              + LocalStruct.define() +
              r'''
    
    int loca(LocalStruct s) {
        printf("a:%d (%lu)\n", s.a, sizeof(s.a));
        printf("b:%f (%lu)\n", s.b, sizeof(s.b));
        return (s.a * s.b) * s.multi.c;
    }
    ''')
    def loca(loc) -> ctypes.c_float:
        return str(loc)

    loc = LocalStruct()
    loc.a = 3
    loc.b = 3.5
    loc.multi = LocalInnerStruct()
    loc.multi.c = 5

    assert loca(loc) == 52.5


def test_build_replace_function_body_include_header():
    @cc_build('''
    #include "values.h"
    #include "more_values.h"
    
    int inc1(int a) {
        return a * VALUE * XTR_VALUE;
    }
    ''', CC_Config(includes=[os.path.join(pathlib.Path(__file__).parent, 'headers')]))
    def inc1(a):
        return a

    assert inc1(3) == 24


def test_build_replace_function_body_multiple_src():

    src_file2 = os.path.join(CC_Config().cache, 'src2.c')
    with open(src_file2, 'w') as out:
        out.write('''
                  int ten(int a);
                  
                  int ten(int a)
                  {
                      return a * 10;
                  }
                  ''')

    src_file3 = os.path.join(CC_Config().cache, 'src3.c')
    with open(src_file3, 'w') as out:
        out.write('''
                  int dub(int a);
                  
                  int dub(int a)
                  {
                      return a * 2;
                  }
                  ''')

    @cc_build('''              
    int ten(int a);        
    int dub(int a);      
              
    int src1(int a) {
        return dub(ten(a));
    }
    ''', CC_Config(src=[src_file2, src_file3]))
    def src1(a):
        return a

    assert src1(3) == 60
    

def test_build_replace_function_body_src_file():

    src_file1 = os.path.join(CC_Config().cache, 'src1.c')
    with open(src_file1, 'w') as out:
        out.write('''
                    int ten(int a);        
                    int dub(int a);      
                            
                    int src1(int a) {
                        return dub(ten(a));
                    }
                  ''')

    src_file2 = os.path.join(CC_Config().cache, 'src2.c')
    with open(src_file2, 'w') as out:
        out.write('''
                  int ten(int a);
                  
                  int ten(int a)
                  {
                      return a * 10;
                  }
                  ''')

    src_file3 = os.path.join(CC_Config().cache, 'src3.c')
    with open(src_file3, 'w') as out:
        out.write('''
                  int dub(int a);
                  
                  int dub(int a)
                  {
                      return a * 2;
                  }
                  ''')

    @cc_build(config=CC_Config(src=[src_file1, src_file2, src_file3]))
    def src1(a):
        return a

    assert src1(3) == 60
    
