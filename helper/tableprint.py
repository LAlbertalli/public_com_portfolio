# Formatter helper functions
FORMAT = None

class TablePrintFormatNotSetException(Exception):
    pass

def choose_table_format(format):
    global FORMAT
    FORMAT = format


def string_format(name, length = 40):
    if len(name) > length:
        return name[:length]
    return name.ljust(length)


def number_format(number, symbol, length = 12):
    return (f"{number} {symbol}").rjust(length)


def print_divider():
    if FORMAT is None:
        raise TablePrintFormatNotSetException("Call choose_table_format before printing a table")
    div_len = sum(i for _,i,_ in FORMAT) + 3 * (len(FORMAT)-1) + 4
    print("-"* div_len)


def print_header(account):
    if FORMAT is None:
        raise TablePrintFormatNotSetException("Call choose_table_format before printing a table")
    print(f"\n\n Portfolio {account}\n")
    print_divider()
    print("| "+ " | ".join([string_format(i,j) for i,j,_ in FORMAT]) + " |")
    print_divider()


def print_row(row):
    if FORMAT is None:
        raise TablePrintFormatNotSetException("Call choose_table_format before printing a table")
    print("| " + " | ".join(f(r) for r,(_,_,f) in zip(row,FORMAT)) + " |")
