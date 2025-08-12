from loial import build

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

# add to git
# test c include files
# test c include libs
# add c compiler args
# try passing in a byte pack as a struct

@build('''
int my_c_fun(int a, int b) {
	return a * b;
}
''', code_type='CC', replace=True, builder_opts={'delete_on_exit':True})
def my_c_fun(a,b):
    return a + b

print(f'function output is: "{my_c_fun(2, 10)}" \n')
