from __future__ import print_function
import sys
import threading

from enum import Enum
from brownie import Contract
import json
import logging
import requests
import time
import traceback

from .class_order import Order
from .class_ordertype import OrderType
from .decorators import *

PERP_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/perpetual-protocol/perp-position-subgraph"
APEX_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/abdullathedruid/apex-keeper"

def get_orders(assets):
    #This will need updating when there are > 1000 orders
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

    logging.debug("Checking if we can execute order id %s ser ..." % order.orderId)

    trader_account_balance = int([account['balance'] for account in account_balances if account['owner'] == order.trader][0])

    if order.stillValid == False:
        logging.debug('Order %s is invalid' % order.orderId)
        return False

    if int(order.expiry) < time.time() and int(order.expiry)!=0:
        logging.debug('Order %s has expired: Expiry: %s Time: %s' % (order.orderId, int(order.expiry), time.time()))
        return False

    if order.collateral > (trader_account_balance/1e6):
        logging.debug('User is too poor for order %s' % order.orderId)
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

def is_negative(num):
    if num < 0:
        return True
    return False

def full_check_can_execute_order(ClearingHouse, order, account_balances):
    traderWallet = [account['id'] for account in account_balances if account['owner'] == order.trader]
    traderPosition = ClearingHouse.getPosition(order.asset.address, traderWallet[0])
    traderPositionSize = traderPosition[0][0]/1e18

    if order.reduceOnly == True:
        if is_negative(order.orderSize) == is_negative(traderPositionSize):
            logging.error("Will not reduce order")
            return False
    return True

@exit_after(30)
def execute_order(LOB, order, user):
    logging.info('Executing order %s' % order.orderId)
    try:
        LOB.execute(order.orderId, {'from': user})
    except Exception as e:
        logging.error(e)
        logging.error(traceback.format_exc())


def get_account_balances():
    # We need to change this when there are more than 1000 wallets
    query = """{
          smartWallets(orderBy:balance, orderDirection: desc, first:1000) {
            id
            owner
            balance
          }
        }"""
    resp = requests.post(APEX_SUBGRAPH, json={"query": query})
    data = resp.json()
    df = data['data']['smartWallets']
    return(df)
