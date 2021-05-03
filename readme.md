## Keeper Bot

This is the repo that contains the scripts needed to run a keeper bot. 

The Keeper bot performs an important function in the APEX architecture, as it executes the orders of traders and updates their trailing order prices. In exchange, Keeper bots get paid a fee known as the "bot fee". Read more [here](docs.apex.win)

Anyone can run a Keeper bot. It is a completely permissionless system. All you need to do is get some xDai and run this script. 


## Set up. 

1. Install [brownie](https://eth-brownie.readthedocs.io/en/stable/)
2. Set up brownie to interact with xdai with the command `brownie networks add Ethereum xdai host=https://dai.poa.network chainid=100 explorer=https://blockscout.com/poa/xdai`
3. Generate a fresh ethereum address with the command `brownie accounts generate BOT`. This will ask you to create a password to lock the account.
4. [Acquire xDai](https://docs.apex.win/apex-docs/user-guide/acquiring-xdai) to pay for your bots transaction fees.
5. Simply run `brownie run keeper` in the console and use your password from step 3.
