import click
from brownie import Contract, accounts, chain, interface, network
import requests
import urllib.request, json
import time
from enum import Enum
import logging

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
            time.sleep()
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


def get_amms():
    output = []
    logging.info("getting amms ser")
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

        MAX_TRIES = 3
        tries = 0
        resp = None

        while True:
            resp = requests.post(PERP_SUBGRAPH, json={"query": query})
            error_happened = 'FALSE'
            try:
                data = resp.json()
                received_data = resp.json()['data']['amm']
                error_happened = 'FALSE'
            except:
                logging.error("Error getting orders fren... trying again ser")
                error_happened = 'TRUE'

            if (resp.status_code == 500 or error_happened == 'TRUE') and tries < MAX_TRIES :
                tries += 1
                continue
            break

        if(error_happened == 'FALSE'):
            price = amm.price
            if(data is not None):
                if(float(data['data']['amm']['baseAssetReserve'])>0):
                    amm.price = float(data['data']['amm']['quoteAssetReserve'])/float(data['data']['amm']['baseAssetReserve'])
                else:
                    # print('Could not get data for %s from the graph, attempting smart contract call..' % amm.name)
                    amm.price = amm.contract.getSpotPrice()[0]/1e18
                if(amm.price != price):
                    logging.info('Price updated for %s from $%.2f to $%.2f' % (amm.name, price, amm.price))
        else:
            logging.error('NO DATA RECEIVED FOR', query)

def quick_check_can_execute_order(order):

    print("Checking if we can execute... ")

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
    logging.info('Executing order %s' % order.orderId)
    try:
        LOB.execute(order.orderId, {'from': user})
    except Exception as e: 
        print(e)
        logging.error(e)



## missing: update price ping


def main():
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='apex.log',
                    filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    user = get_account()
    assets = get_amms()
    logging.info('Connected with: %s' % user)
    network.gas_price(1000000000)
    timer = 0
    while True:
        orders = get_orders(assets)
        get_prices(assets)
        logging.info('%s outstanding orders' % len(orders))
        for order in orders:
            if quick_check_can_execute_order(order):
                execute_order(order, user)
        time.sleep(60)
