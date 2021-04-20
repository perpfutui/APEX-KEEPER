import click
from brownie import Contract, accounts, chain, interface, network
import requests
import urllib.request, json
import time
from enum import Enum

PERP_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/perpetual-protocol/perp-position-subgraph"
APEX_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/abdullathedruid/apex-keeper"

LOB = Contract.from_abi('LimitOrderBook', address='0x02e7B722E178518Ae07a596A7cb5F88B313c453a', abi=json.load(open('interfaces/LimitOrderBook.json','r')))

TIMER_BLOCK_RESET = 20

class OrderType(Enum):
    MARKET = 0
    LIMIT = 1
    STOPMARKET = 2
    STOPLIMIT = 3
    TRAILINGSTOPMARKET = 4
    TRAILINGSTOPLIMIT = 5

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

def get_account():
    return accounts.load('BOT')

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

    str_error = None

    for x in range(0, 4):  # try 4 times
        try:
            resp = requests.post(APEX_SUBGRAPH, json={"query": query})
            data = resp.json()
            str_error = None
        except Exception as str_error:
            data = None
            pass

        if str_error:
            sleep(2)  # wait for 2 seconds before trying to fetch the data again
        else:
            break

    output = []
    if(data is not None):
        # print(data)
        orders = data['data']['orders']
        for order in orders:
            output.append(Order(assets,**order))
    return output

def get_amms():
    output = []
    with urllib.request.urlopen('https://metadata.perp.exchange/production.json') as url:
        data = json.loads(url.read().decode())
        contracts = data['layers']['layer2']['contracts']
        for contract in contracts:
            if data['layers']['layer2']['contracts'][contract]['name'] == 'Amm':
                output.append(Asset(contract[0:-4], data['layers']['layer2']['contracts'][contract]['address']))
    return output

def get_prices(assets):
    for amm in assets:
        query = """{
          amm(id: "%s") {
            quoteAssetReserve
            baseAssetReserve
          }
        }""" % amm.address.lower()

        str_error = None
        
        for x in range(0, 4):  # try 4 times
            try:
                resp = requests.post(PERP_SUBGRAPH, json={"query": query})
                data = resp.json()
                str_error = None
            except Exception as str_error:
                data = None
                pass

            if str_error:
                sleep(2)  # wait for 2 seconds before trying to fetch the data again
            else:
                break

        if(data is not None):
            price = amm.price
            if(data is not None):
                if(float(data['data']['amm']['baseAssetReserve'])>0):
                    amm.price = float(data['data']['amm']['quoteAssetReserve'])/float(data['data']['amm']['baseAssetReserve'])
                else:
                    # print('Could not get data for %s from the graph, attempting smart contract call..' % amm.name)
                    amm.price = amm.contract.getSpotPrice()[0]/1e18
                if(amm.price != price):
                    print('Price updated for %s from $%.2f to $%.2f' % (amm.name, price, amm.price))
        else:
            print('NO DATA RECEIVED FOR', query)

def quick_check_can_execute_order(order):

    if order.stillValid == False:
        return False

    if float(order.expiry) < time.time():
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
    print('Executing order %s' % order.orderId)
    try:
        LOB.execute(order.orderId, {'from': user})
    except ValueError as err:
        print(err)


## missing: update price ping


def main():
    user = get_account()
    assets = get_amms()
    print('Connected with:',user)
    network.gas_price(1000000000)
    timer = 0
    while True:
        orders = get_orders(assets)
        get_prices(assets)
        print('%s outstanding orders' % len(orders))
        for order in orders:
            if quick_check_can_execute_order(order):
                execute_order(order, user)
        time.sleep(60)
