from brownie import Contract
import json

class Asset:
    name: str
    address: str
    contract: Contract
    price: float

    def __str__(self):
        return "%s [%s] price is $%.2f" % (self.name, self.address, self.price)

    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.contract = Contract.from_abi(name, address=address, abi=json.load(open('interfaces/Amm.json','r')))
        self.price = 0
