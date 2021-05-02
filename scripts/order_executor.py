from enum import Enum
from brownie import Contract
import json
import logging
import requests
import time

PERP_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/perpetual-protocol/perp-position-subgraph"
APEX_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/abdullathedruid/apex-keeper"

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

class OrderType(Enum):
    MARKET = 0
    LIMIT = 1
    STOPMARKET = 2
    STOPLIMIT = 3
    TRAILINGSTOPMARKET = 4
    TRAILINGSTOPLIMIT = 5

class Order:
    orderId: int
    trader: str
    asset: Asset
    limitPrice: float
    stopPrice: float
    orderSize: float
    collateral: float
    leverage: float
    slippage: float
    tipFee: float
    expiry: float
    reduceOnly: bool

    def __str__(self):
        disprice = 0
        if self.orderType == OrderType.LIMIT.value:
            disprice = self.limitPrice
        elif self.orderType == OrderType.STOPMARKET.value or self.orderType == OrderType.STOPLIMIT.value:
            disprice = self.stopPrice
        return "Order [%s] %s %.5f %s @ $%.2f" % (self.orderId, 'BUY' if self.orderSize>0 else 'SELL', abs(self.orderSize), self.asset.name, disprice)

    def __init__(self, assets, id, trader, asset, limitPrice, stopPrice, orderSize, orderType,
        collateral, leverage, slippage, tipFee, expiry, reduceOnly, stillValid):
        self.orderId = int(id)
        self.trader = trader
        self.asset = next(x for x in assets if x.address.lower() == asset.lower())
        self.limitPrice = float(limitPrice)/1e18
        self.stopPrice = float(stopPrice)/1e18
        self.orderSize = float(orderSize)/1e18
        self.orderType = int(orderType)
        self.collateral = float(collateral)/1e18
        self.leverage = float(leverage)/1e18
        self.slippage = float(slippage)/1e18
        self.tipFee = float(tipFee)/1e18
        self.expiry = expiry
        self.reduceOnly = reduceOnly
        self.stillValid = stillValid

def get_orders(assets):
    query = """
    {
      orders(first: 1000, orderBy: tipFee, orderDirection:desc, where:{filled:false, stillValid:true}) {
        id
        trader
        asset
        limitPrice
        stopPrice
        orderSize
        orderType
        collateral
        leverage
        slippage
        tipFee
        expiry
        reduceOnly
        stillValid
      }
    }"""

    MAX_TRIES = 3
    logging.info("getting teh orders SER")
    tries = 0
    resp = None
    while True:
        resp = requests.post(APEX_SUBGRAPH, json={"query": query})
        error_happened = 'FALSE'
        try:
            data = resp.json()
            received_data = resp.json()['data']['orders']
            error_happened = 'FALSE'
        except:
            logging.error("Error getting orders fren... trying again ser")
            error_happened = 'TRUE'

        if (resp.status_code == 500 or error_happened == 'TRUE') and tries < MAX_TRIES :
            tries += 1
            time.sleep(1)
            continue
        break

    if(error_happened == 'TRUE'):
        logging.error("Gave up with query. Sad!")
        return None
    output = []
    # print(data)
    orders = data['data']['orders']
    for order in orders:
        output.append(Order(assets,**order))
    return output

def quick_check_can_execute_order(order,account_balances):

    logging.info("Checking if we can execute order id %s ser ..." % order.orderId)

    trader_account_balance = int([account['balance'] for account in account_balances if account['owner'] == order.trader][0])

    if order.stillValid == False:
        return False

    if float(order.expiry) < time.time():
        return False

    if order.collateral > (trader_account_balance/1e18):
        return False

    if order.orderType == OrderType.LIMIT.value:
        if order.orderSize > 0: #limit buy
            if order.asset.price > order.limitPrice:
                return False
        elif order.orderSize < 0: #limit sell
            if order.asset.price < order.limitPrice:
                return False
        else:
            return False

    if order.orderType == OrderType.STOPMARKET.value or order.orderType == OrderType.TRAILINGSTOPMARKET.value:
        if order.orderSize > 0: #stop buy
            if order.asset.price < order.stopPrice:
                return False
        elif order.orderSize < 0: #stop sell
            if order.asset.price > order.stopPrice:
                return False
        else:
            return False

    if order.orderType == OrderType.STOPLIMIT.value or order.orderType == OrderType.TRAILINGSTOPLIMIT.value:
        if order.orderSize > 0: #stoplimit buy
            if order.asset.price < order.stopPrice:
                return False
            if order.asset.price > order.limitPrice:
                return False
        elif order.orderSize < 0: #stoplimit sell
            if order.asset.price > order.stopPrice:
                return False
            if order.asset.price < order.limitPrice:
                return False
        else:
            return False

    return True

def execute_order(order, user):
    logging.info('Executing order %s' % order.orderId)
    try:
        LOB.execute(order.orderId, {'from': user})
    except Exception as e:
        print(e)
        logging.error(e)


def get_account_balances():
    query = """{
          smartWallets(orderBy:balance, orderDirection: desc, first:10) {
            owner
            balance
          }
        }"""
    resp = requests.post(APEX_SUBGRAPH, json={"query": query})
    data = resp.json()
    df = data['data']['smartWallets']
    return(df)
