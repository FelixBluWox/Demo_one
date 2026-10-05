from os import getenv
from dotenv import load_dotenv
from traceback import format_exception
from colorama import Style, Fore, Back, init
import logging, sys, codecs, json, codecs
from functools import lru_cache as cache
init()











def error_form(error, title="Oh no, something happend", info=None):
    traceback = "Error:\n" + '\n'.join(map(str, format_exception(type(error), error, error.__traceback__)))
    details = '\n'.join(map(str, error.args))
    message = f"""{Back.YELLOW}{Fore.BLACK}{Style.BRIGHT}
    {title} Error: {type(error).__name__}\t{Back.RESET}{Fore.LIGHTYELLOW_EX}

    {info}
    
    {type(error).__name__} Details: \n{details}

    TRACEBACK:{Fore.RESET}{Style.NORMAL}{Fore.YELLOW}
    
    {traceback}{Style.RESET_ALL}
    """
    return message

with codecs.open("./logs/debug.log", "w") as f:
    pass
with codecs.open("./logs/info.log", "w") as f:
    pass
with codecs.open("./logs/warn.log", "w") as f:
    pass


formatter = logging.Formatter('[%(levelname)s][%(name)s]: %(message)s')

stdout_info_handler = logging.StreamHandler(sys.stdout)
stdout_info_handler.setLevel(logging.INFO)
stdout_info_handler.setFormatter(formatter)

stdout_warn_handler = logging.StreamHandler(sys.stdout)
stdout_warn_handler.setLevel(logging.WARN)
stdout_warn_handler.setFormatter(formatter)

stdout_debug_handler = logging.StreamHandler(sys.stdout)
stdout_debug_handler.setLevel(logging.DEBUG)
stdout_debug_handler.setFormatter(formatter)

file_debug_handler = logging.FileHandler(filename='./logs/debug.log', encoding='utf-8', mode='w')
file_debug_handler.setLevel(logging.DEBUG)
file_debug_handler.setFormatter(formatter)

file_info_handler = logging.FileHandler(filename='./logs/info.log', encoding='utf-8', mode='w')
file_info_handler.setLevel(logging.INFO)
file_info_handler.setFormatter(formatter)

file_warn_handler = logging.FileHandler(filename='./logs/warn.log', encoding='utf-8', mode='w')
file_warn_handler.setLevel(logging.WARN)
file_warn_handler.setFormatter(formatter)

class Wox_log(logging.Logger):
    def __init__(self, name, color=None, std_handler=stdout_info_handler, file_handlers=[file_debug_handler, file_info_handler, file_warn_handler]) -> None:
        super().__init__(name)
        self.color = color
        self.setLevel(logging.DEBUG)
        self.addHandler(std_handler)
        for handler in file_handlers:
            self.addHandler(handler)
    
    def debug(self, msg):
        if self.color:
            print(self.color, end ="")
        else:
            print(Fore.MAGENTA, Style.DIM, end ="")
        super().debug(msg)
        print(Style.RESET_ALL, end ="")

    def info(self, msg):
        if self.color:
            print(self.color, end ="")
        super().info(msg)
        print(Style.RESET_ALL, end ="")
    
    def warning(self, msg):
        if self.color:
            print(self.color, end ="")
        else:
            print(Fore.YELLOW, end ="")
        super().warning(msg)
        print(Style.RESET_ALL, end ="")
    
    def critical(self, msg):
        if self.color:
            print(self.color, end ="")
        else:
            print(Fore.LIGHTYELLOW_EX, end ="")
        super().critical(msg)
        print(Style.RESET_ALL, end ="")
    
    def error(self, msg):
        if self.color:
            print(self.color, end ="")
        else:
            print(Fore.LIGHTRED_EX, end ="")
        super().error(msg)
        print(Style.RESET_ALL, end ="")
    
    def exception(self, msg):
        if self.color:
            print(self.color, end ="")
        else:
            print(Fore.LIGHTRED_EX, Style.BRIGHT, end ="")
        super().exception(msg)
        print(Style.RESET_ALL, end ="")
    
    def fwrn(self, error, title="Oh no, something happend", info=None):
        traceback = "Error:\n" + '\n'.join(map(str, format_exception(type(error), error, error.__traceback__)))
        details = '\n'.join(map(str, error.args))
        print(Back.YELLOW, Fore.BLACK, Style.BRIGHT, end ="")
        super().error(f"{title} Error: {type(error).__name__}")
        print(Back.RESET, Fore.LIGHTYELLOW_EX, end ="")
        super().error(f"{info}\n\n{type(error).__name__} Details: \n{details}\n\nTRACEBACK:")
        print(Fore.RESET, Style.NORMAL, Fore.YELLOW, end ="")
        super().error(traceback)
        print(Style.RESET_ALL, end ="")
    
    def ferr(self, error, title="Oh no, something happend", info=None):
        traceback = "Error:\n" + '\n'.join(map(str, format_exception(type(error), error, error.__traceback__)))
        details = '\n'.join(map(str, error.args))
        print(Back.YELLOW, Fore.BLACK, Style.BRIGHT, end ="")
        super().error(f"{title} Error: {type(error).__name__}")
        print(Back.RESET, Fore.YELLOW, end ="")
        super().error(f"{info}\n\n{type(error).__name__} Details: \n{details}\n\nTRACEBACK:")
        print(Fore.RESET, Style.NORMAL, Fore.LIGHTRED_EX, end ="")
        super().error(traceback)
        print(Style.RESET_ALL, end ="")
    
    def fexc(self, error, title="Oh no, something happend", info=None):
        traceback = "Error:\n" + '\n'.join(map(str, format_exception(type(error), error, error.__traceback__)))
        details = '\n'.join(map(str, error.args))
        print(Back.LIGHTRED_EX, Fore.BLACK, Style.BRIGHT, end ="")
        super().critical(f"{title} Error: {type(error).__name__}")
        print(Back.RESET, Fore.LIGHTRED_EX, end ="")
        super().critical(f"{info}\n\n{type(error).__name__} Details: \n{details}\n\nTRACEBACK:")
        print(Fore.RESET, Style.NORMAL, Fore.RED, end ="")
        super().critical(traceback)
        print(Style.RESET_ALL, end ="")


        




