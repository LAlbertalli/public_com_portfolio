import argparse
import inspect
from functools import wraps

COMMANDS = {}

def parse_doc_string(doc_string):
    help_txt = ""
    opt_args = []
    for l in doc_string.splitlines():
        l=l.strip()
        if l[0] == "-":
            idx = l.index(":")
            args = tuple(sorted(
                l[:idx].split(" "), 
                key = lambda x:len(x),
                ))
            arg_help = l[idx+1:].strip()
            # Validate
            registered_opt_args = {
                a: (n, args) for n,f in COMMANDS.items() 
                    for args,_ in f["opt_args"] for a in args
            }
            match len(args):
                case 0:
                    raise Exception("Something wrong. Should never raise!")
                case 1:
                    arg = args[0]
                    if arg in registered_opt_args:
                        other = registered_opt_args[arg][1]
                        if len(other) == 2:
                            raise Exception("Optional argument %s already registered with different command as (%s, %s)"%(arg,*other))
                case 2:
                    arg1 = args[0]
                    arg2 = args[1]
                    other = None
                    if arg1 in registered_opt_args:
                        other = registered_opt_args[arg1][1]
                        if len(other) == 1:
                            raise Exception("Optional argument %s, %s already registered with different command as %s"%(arg1, arg2,other[0]))
                    if arg2 in registered_opt_args:
                        other = registered_opt_args[arg2][1]
                        if len(other) == 1:
                            raise Exception("Optional argument %s, %s already registered with different command as %s"%(arg1, arg2,other[0]))
                    if other and args != other:
                        raise Exception("Optional argument (%s, %s) incompatible with already registered (%s,%s)"%(arg1, arg2,*other))
                case _:
                    raise Exception("Supported only up to 2 name for optional arg") 
            opt_args += [(args, arg_help)]
        else:
            help_txt += '\n' + l
        return help_txt, opt_args

def command(func):
    global COMMANDS #noqa: PLW0602
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    name = func.__name__
    if name in COMMANDS:
        raise Exception("Command %s already registered" % name)
    
    help_txt, opt_args = parse_doc_string(func.__doc__)
    params = inspect.signature(func).parameters
    COMMANDS[name] = {
        "f": func, 
        "help": help_txt, 
        "params": params,
        "opt_args": opt_args,
    }
    return wrapper

def parse_args():
    parser = argparse.ArgumentParser(
        description='Help me monitor my portfolio on Public.com and keep it balanced',
        formatter_class = argparse.RawTextHelpFormatter
        )
    help_txt = "Action to execute:\n"
    opt_args = {}
    for c in COMMANDS:
        help_txt+="    - %s: %s\n"%(c, COMMANDS[c]["help"])
        if COMMANDS[c]["opt_args"]:
            for args, arg_help in COMMANDS[c]["opt_args"]:
                if args in opt_args:
                    opt_args[args] += [(c, arg_help)]
                else:
                    opt_args[args] = [(c, arg_help)]
    parser.add_argument("action", choices=[c for c in COMMANDS], 
        default = 'show', 
        help = help_txt,
        nargs = '?')
    
    # Global optional params
    parser.add_argument("-r", "--run", action = 'store_true',
        help = "For rebalance, actually use the public apis to run the planned actions")
    parser.add_argument("-a", '--account', 
        help = "Limit to the specified account")

    # Local optional params
    for args, defs in opt_args.items():
        help_str = ""
        for c, arg_help in defs:
            help_str += "[Only %s] %s\n"%(c, arg_help)
        parser.add_argument(*args, help = help_str)

    parsed = parser.parse_args()
    # Validate local args
    action = parsed.action
    for args, defs in opt_args.items():
        dest = args[-1][2:] if args[-1][1] == "-" else args[-1][1:]
        if getattr(parsed, dest) and not any(c == action for c,_ in defs):
            parser.error("%s can be used only with commands %s"%(args[-1], [c for c,_ in defs]))

    return parsed


def exec_command(command, in_args, loc_arg):
    f = COMMANDS[command]["f"]
    args = []
    for i in COMMANDS[command]["params"]:
        try:
            args += [getattr(in_args, i)]
        except AttributeError:
            args += [loc_arg[i]]
    return f(*args)
