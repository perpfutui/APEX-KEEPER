import click
from brownie import Contract, accounts, chain, interface, network
import requests
import urllib.request, json
import time
from enum import Enum
import logging

## function to update trigger order

LOB = Contract.from_abi('LimitOrderBook', address='0x02e7B722E178518Ae07a596A7cb5F88B313c453a', abi=json.load(open('interfaces/LimitOrderBook.json','r')))

PERP_SUBGRAPH_PRICE = "https://api.thegraph.com/subgraphs/name/abdullathedruid/perp-limit"
APEX_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/abdullathedruid/apex-keeper"


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
    contract: "TEST FOR NOW"
    price: float

    def __str__(self):
        return "%s [%s] price is $%.2f" % (self.name, self.address, self.price)

    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.contract = "TEST FOR NOW"
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


        for x in range(0, 4):  # try 4 times
            str_error = None
            try:
                resp = requests.post(PERP_SUBGRAPH, json={"query": query})
                data = resp.json()
                str_error = None
            except Exception as e:
                str_error = e
                data = None
                pass
            #if str_error:
            #    sleep(2)  # wait for 2 seconds before trying to fetch the data again
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


def update_trigger(order_id, _reserveIndex, user):
	LOB.pokeContract(order_id,_reserveIndex, {'from': user})

def get_trailing_orders():
    print("fetching trailing orders ser")
    
    query = """
    {
    trailingOrders(first: 1000) {
    id
    witnessPrice
    snapshotTimestamp
    snapshotCreated
    snapshotLastUpdated
      }
    }
    """
    ## to do: make error resistant
    resp = requests.post(APEX_SUBGRAPH, json={"query": query})
    data = resp.json()
    df = data['data']['trailingOrders']
    return(df)
   
def get_trade_prices(amm, snapshotCreated, max_or_min,price):
    
    # if the trade is less than 
    # greater than or less than current_price
    if(max_or_min > 0):
        query = """	{
        reserveSnapshottedEvents(first: 1,orderBy: price, orderDirection: asc, where:{amm:"%s", reserveIndex_gt: "%s", price_lte: "%s"}) {
        id
        amm
        blockNumber
        blockTimestamp
        reserveIndex
        price
        }
        }
        """ % (amm,snapshotCreated,price)

    if(max_or_min < 0):
        query = """	{
        reserveSnapshottedEvents(first: 1,orderBy: price, orderDirection: desc, where:{amm:"%s", reserveIndex_gt: "%s", price_gte: "%s"}) {
        id
        amm
        blockNumber
        blockTimestamp
        reserveIndex
        price
        }

        """ % (amm,snapshotCreated,price)
    resp = requests.post(PERP_SUBGRAPH_PRICE, json={"query": query})
    data = resp.json()
    df = data['data']['reserveSnapshottedEvents'][0]
    return(df)


def get_account():
    return accounts.load('BOT')


def trailing_order_update(assets,orders):
    try:
        # filter all orders to trailing orders only
        trigger_order_list = [(order.orderId, order.orderSize,order.asset.address) for order in orders if order.orderType in (4,5)]
        all_trailing_orders = get_trailing_orders()

        ## get the detail
        ## to do: add the data to the trigger_order_list, let get_trailing_orders take it as an argument

        for trigger_order in trigger_order_list:
            print(trigger_order[0])
            current_id = str(trigger_order[0])
            order_details = [(t_ord['snapshotCreated'],t_ord['witnessPrice'], t_ord['snapshotTimestamp']) for t_ord in all_trailing_orders if t_ord['id'] == current_id]
            order_snapshotCreated = order_details[0][0]
            price = order_details[0][1]
            last_updated = order_details[0][2]
            max_or_min = trigger_order[1]
            amm = trigger_order[2]
            current_size = trigger_order[1]
            new_price = get_trade_prices(trigger_order_list[0][2], order_snapshotCreated, max_or_min,price)
            # get trade price for amm & after block and get min or max price reserve index
            if new_price['reserveIndex'] > order_snapshotCreated and price != new_price['price'] and (last_updated+15*60) < time.time:
                print("call function to update price ser")
                update_trigger(trigger_order[0],new_price['reserveIndex'],user)
    except Exception as error:
        print("Error updating trigger orders fren... trying again ser")
        print(error)
        time.sleep(1)

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



#user = get_account()
#assets = get_amms()
#orders = get_orders(assets)
#network.gas_price(1000000000)
#trailing_order_update(assets,orders)






