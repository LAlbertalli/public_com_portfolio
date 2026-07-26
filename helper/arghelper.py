import argparse, inspect

from functools import wraps

COMMANDS = {}


def command(func):
    global COMMANDS
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    name = func.__name__
    help_txt = func.__doc__
    params = inspect.signature(func).parameters
    COMMANDS[name] = {
        "f": func, 
        "help": help_txt, 
        "params": params
    }
    return wrapper

def parse_args():
    global COMMANDS
    parser = argparse.ArgumentParser(
        description='Help me monitor my portfolio on Public.com and keep it balanced',
        formatter_class = argparse.RawTextHelpFormatter
        )
    help_txt = "Action to execute:\n"
    for c in COMMANDS:
        help_txt+="    - %s: %s\n"%(c, COMMANDS[c]["help"])
    parser.add_argument("action", choices=[c for c in COMMANDS], 
        default = 'show', 
        help = help_txt,
        nargs = '?')
    parser.add_argument("-r", "--run", action = 'store_true',
        help = "For rebalance, actually use the public apis to run the planned actions")

    parser.add_argument("-a", '--account', 
        help = "Limit to the specified account")

    return parser.parse_args()


def exec_command(command, loc_arg):
    global COMMANDS
    f = COMMANDS[command]["f"]
    args = []
    for i in COMMANDS[command]["params"]:
        args+=[loc_arg[i]]
    return f(*args)
