from enum import Enum

class OrderType(Enum):
    MARKET = 0
    LIMIT = 1
    STOPMARKET = 2
    STOPLIMIT = 3
    TRAILINGSTOPMARKET = 4
    TRAILINGSTOPLIMIT = 5
