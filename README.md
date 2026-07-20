# Public.com Portfolio Manager
This is just a simple utility I wrote to manage my investments on [public.com](https://www.public.com).

Public is an online broker that offers several services. One very powerful feature is the ability 
to manage your portfolio of investments via APIs. Given the recent changes to IPO inclusion rules,
I decided to manage my retirement accounts more actively. That doesn't mean any risky or complex active
investment system. I just want to have a portfolio of passive investments, monitor them, and rebalance 
them from time to time.

I don't think this script is very useful to anyone other than me. But if you find it useful, feel free 
clone and reuse it

# How to use it?
This is a pretty simple command-line Python script. To use it, you just need to follow these 3 simple steps

## 1. Create a virtual environment and install the dependencies
The only requirement is the [public.com Python Library](https://github.com/PublicDotCom/publicdotcom-py) and 
its dependencies
``` bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Get a public.com API Key
If you already have an account on public.com, just log in and press `D`. This will open the developer console.
Click on "Create API Key"; it will open a new tab with the [API Key Page](https://public.com/settings/v2/api/api-keys) 
(or click the link here). Then press "+ New" in the Secret Key section and copy the secret shown. Save the secret key 
in a new file in the same directory as the script, named `.publicdotcom_key`.

## 3. Configure your portfolio allocation
Copy the `config.py.tpl` into `config.py`
``` bash
cp config.py.tpl config.py
```
Proceed to configure the accounts you have and their allocations. The template has comments to help. 
Better instructions soon.

## 4. Use it
**--- ! Caution ! ---**

I do not guarantee this works as intended. There can be bugs, so use caution

To use it, just call `python3 public.py`

It offers two main functionalities:
- The first one, `show`, is a quick summary of your current portfolio and how it has deviated from the target allocation.
- The second one, `rebalance`, calculates what ETF to buy and sell to rebalance your portfolio.

The rebalance function can write to public and execute the changes it calculates. Use the `-r` flag to 
actually do the rebalance. It has a pretty robust checkpointing functionality to recover in case of bugs on my side or 
on public.com side causes issues. You can use the `recover` functionality to recover from any issues. This should work most of the time. **Before any run, the tool checks for incomplete rebalances. If you are stuck in a situation where it cannot recover, fix the issue manually on public.com and then remove the `.checkpoint.json` file.**

`-h` will print the command help.

```
usage: public.py [-h] [-r] [-a ACCOUNT] [{show,rebalance,recover}]

Help me monitor my portfolio on Public.com and keep it balanced

positional arguments:
  {show,rebalance,recover}
                        Action to execute:
                            - show: Show the current portfolio
                            - rebalance: Rebalance the portfolio. Notice, without --run, it will only simulate the rebalance
                            - recover: It recovers a previously failed rebalance. Note: it will ignore any other flags

options:
  -h, --help            show this help message and exit
  -r, --run             For rebalance, actually use the public apis to run the planned actions
  -a, --account ACCOUNT
                        Limit to the specified account
```

# Contribute
The project is not ready to contribute yet. But if you really really really want to contribute, just send me a PR.

**Important:** I chose not to use AI on this project. Please respect this choice! Any PR that smells like AI slop will be refused.

# TODO
- Error handling when calling the public.com API is nonexistent. For reading (`show`), this is not a big concern. For writing, the checkpoint capabilities help a lot, but better recovery would help. The general approach: if the error is not recoverable because of API calling logic, don't intercept it. Let it fail! If the error is recoverable (e.g., temporarily unavailable, error 404 due to race conditions), then an error recovery should be attempted.
- The gain/loss calculation in show is pretty crude and doesn't reflect the impact of rebalancing. I should probably build better functionality in the future, especially something to calculate better performance metrics.
