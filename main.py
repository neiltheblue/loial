from loial import build
from loial.builders.c_builder import CC_Config

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

# pass by pointer
# pass array
# try passing in a byte pack as a struct

config=CC_Config()
config.delete_on_exit=True
@build(r'''
#include <math.h>
#include <stdio.h>
int my_c_fun(int a, int b) {
    printf("sqrt(%d) = %f\n", a, sqrt(a));
	return a * b;
}
''', code_type='CC', replace=True, config=config)
def my_c_fun(a,b):
    return a + b

print(f'function output is: "{my_c_fun(2, 10)}" \n')
