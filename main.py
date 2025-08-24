from loial import build
from loial.builders.cc_builder import CC_Config, cc_build

############################
## Exercise: Python Builder
############################

@build('''
print(f"running alternative code")
return a*b
''')
def my_py_fun(a, b):
    return a + b

print(f'function output is: "{my_py_fun('Ha!', 10)}" \n')

############################
## Exercise: C Builder
############################

# try generating struct from object instance
# test multiple return types

@cc_build(r'''
#include <math.h>
#include <stdio.h>
int my_c_fun(int a, int b) {
    printf("sqrt(%d) = %f\n", a, sqrt(a));
	return a * b;
}
''', CC_Config(delete_on_exit=True), replace=True)
def my_c_fun(a,b):
    return a + b

print(f'function output is: "{my_c_fun(2, 10)}" \n')
