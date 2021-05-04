import click
from brownie import Wei, Contract, accounts, chain, interface, network
import json

LOB = Contract.from_abi('LimitOrderBook', address='0x02e7B722E178518Ae07a596A7cb5F88B313c453a', abi=json.load(open('interfaces/LimitOrderBook.json','r')))

def get_account():
    return accounts.load('main')

def main():
    user = get_account()
    network.gas_price("1.0 gwei")
    LOB.addTrailingStopMarketOrderAbs(
        '0x0f346e19F01471C02485DF1758cfd3d624E399B4',
        [Wei("1000 ether")],
        [Wei("0.00001 ether")],
        [Wei("1 ether")],
        [Wei("10 ether")],
        [Wei("0.01 ether")],
        False,
        0,
        {'from': user.address}
    )
