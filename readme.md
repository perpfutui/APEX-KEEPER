## Keeper Bot

This is the repo that contains the scripts needed to run a keeper bot. 

The Keeper bot performs an important function in the APEX architecture, as it executes the orders of traders and updates their trailing order prices. In exchange, Keeper bots get paid a fee known as the "bot fee". Read more [here](docs.apex.win)

Anyone can run a Keeper bot. It is a completely permissionless system. All you need to do is get some xDai and run this script. 


## Set up. 

1. [Acquire xDai](https://docs.apex.win/apex-docs/user-guide/acquiring-xdai) to pay for your bots transaction fees.
2. Install [brownie](https://eth-brownie.readthedocs.io/en/stable/)
3. Set up your account on brownie such that it can send xdai transactions on your [behalf](https://eth-brownie.readthedocs.io/en/stable/core-accounts.html#generating-adding-and-unlocking-accounts)
4. Simply run `brownie run keeper` in console
