from brownie import Contract, accounts, chain, interface, network
import requests
import urllib.request, json
import time
from enum import Enum
import logging
from .order_executor import *
from .update_trigger import *

LOB = Contract.from_abi('LimitOrderBook', address='0x02e7B722E178518Ae07a596A7cb5F88B313c453a', abi=json.load(open('interfaces/LimitOrderBook.json','r')))

def get_account():
    return accounts.load('BOT')

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
        account_balances = get_account_balances()
        # trailing_order_update(assets,orders,user)
        logging.info('%s outstanding orders' % len(orders))
        for order in orders:
            if quick_check_can_execute_order(order,account_balances):
                execute_order(order, user)
        time.sleep(60)
