from brownie import *
import click
import json

pPERPAddress = '0xDAd6980598DbFa4A4b2FcF520a0CC92dc6533365'
pPERP = Contract.from_abi('pPERP', address=pPERPAddress, abi=json.load(open('interfaces/pPERP.json','r')))
SmartWalletFactory = Contract.from_abi('SWF', address='0x68410B166Deb9AB9Aff99d3efFE32bd2940c84eA', abi=json.load(open('interfaces/SmartWalletFactory.json','r')))


def get_account():
    return accounts.load(click.prompt("account", type=click.Choice(accounts.load())))

def main():
    user = get_account()
    print('Connected with account %s' % user)
    smartWalletAddress = SmartWalletFactory.getSmartWallet(user)
    print('Smart Wallet address: %s' % smartWalletAddress)
    balance = pPERP.balanceOf(smartWalletAddress)
    print('pPERP balance %s' % balance)
    smartWallet = Contract.from_abi('SW', address=smartWalletAddress, abi=json.load(open('interfaces/SmartWallet.json','r')) )
    callData = pPERP.transfer.encode_input(user, balance)
    print(callData)
    network.gas_price(1000000000)
    smartWallet.executeCall(pPERPAddress,callData, {"from":user})
