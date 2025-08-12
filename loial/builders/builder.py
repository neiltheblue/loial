class BaseBuilder:
    ''' Base class for code compilers. It is not meant to be instantiated directly.'''
    
    def __init__(self, code, config=None):
        ''' Initializes the compiler with the provided code and options.
        
        Args:
            code (str): The code to be compiled.
            config (object): The optional class specific config instance
        '''
        self.code = code
    
    def compile(self, fun):
        ''' Compiles the provided code into a function body.
        
        Args:
            fun: The function to compile the code for.
        
        Returns:
            self: The instance of the compiler with compiled code.
        '''
        pass
