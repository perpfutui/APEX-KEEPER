import click
from brownie import Contract, accounts, chain, interface, network
import requests
import urllib.request, json
import time
from enum import Enum
import logging
import traceback

from .decorators import *

PERP_SUBGRAPH_PRICE = "https://api.thegraph.com/subgraphs/name/abdullathedruid/perp-limit"
APEX_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/abdullathedruid/apex-keeper"


@exit_after(30)
def update_trigger(LOB, order_id, _reserveIndex, user):
    try:
        LOB.pokeContract(order_id,_reserveIndex, {'from': user})
    except Exception as e:
        logging.error(e)
        logging.error(traceback.format_exc())

def get_trailing_orders():
    logging.info("fetching trailing orders ser")
    #Will need updating when > 1000 trailing orders
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
        }
        """ % (amm,snapshotCreated,price)
    resp = requests.post(PERP_SUBGRAPH_PRICE, json={"query": query})
    data = resp.json()
    if data is not None:
        if(len(data['data']['reserveSnapshottedEvents'])>0):
            df = data['data']['reserveSnapshottedEvents'][0]
            return(df)
        else:
            return False
    else:
        return False

def trailing_order_update(LOB, assets,orders,user):
    try:
        # filter all orders to trailing orders only
        trigger_order_list = [(order.orderId, order.orderSize,order.asset.address) for order in orders if order.orderType in (4,5)]
        all_trailing_orders = get_trailing_orders()

        ## get the detail
        ## to do: add the data to the trigger_order_list, let get_trailing_orders take it as an argument

        for trigger_order in trigger_order_list:
            logging.info(trigger_order[0])
            current_id = str(trigger_order[0])
            order_details = [(t_ord['snapshotCreated'],t_ord['witnessPrice'], t_ord['snapshotTimestamp']) for t_ord in all_trailing_orders if t_ord['id'] == current_id]
            order_snapshotCreated = order_details[0][0]
            price = order_details[0][1]
            last_updated = order_details[0][2]
            max_or_min = trigger_order[1]
            amm = trigger_order[2]
            current_size = trigger_order[1]
            new_price = get_trade_prices(trigger_order_list[0][2], order_snapshotCreated, max_or_min,price)
            if new_price:
                # get trade price for amm & after block and get min or max price reserve index
                if new_price['reserveIndex'] > order_snapshotCreated and price != new_price['price'] and (int(last_updated)+15*60) < time.time():
                    logging.info("calling function to update order #%s price ser" % current_id)
                    try:
                        update_trigger(LOB, trigger_order[0],new_price['reserveIndex'],user)
                    except KeyboardInterrupt:
                        print('trying next one... ')

    except Exception as error:
        print("Error updating trigger orders fren... trying again ser")
        logging.error(error)
        logging.error(traceback.format_exc())
        time.sleep(1)
