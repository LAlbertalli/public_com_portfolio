from commands import CheckPointer
from helper.arghelper import exec_command, parse_args
from helper.config_helper import validate_allocations
from helper.public_api import get_client


def main():
    args = parse_args()

    checkpoints = CheckPointer.try_load()
    if checkpoints and args.action != "recover":
        print("There is a pending rebalancing transaction. Run with action 'recover' to continue")
        return

    if not validate_allocations():
        return

    client = get_client()
    if client is None:
        return

    return exec_command(args.action, args, locals())


if __name__ == "__main__":
    main()