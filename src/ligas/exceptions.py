
from requests import exceptions
from ligas import logger

class FbrefRequestException(exceptions.RequestException):
    """ 
        Raised this exception when FBref returns bad HTTP status.
        (4xx or 5xx) 
    """

    def __init__(self) -> None:
        super().__init__()


    def __str__(self) -> str:
        return logger.info("Bad responses (4xx or 5xx)")
    

class FbrefRateLimitException(Exception):
    """ 
        Raised Raised this exception when FBref returns HTTP status 429, rate limit request
    """
    def __init__(self) -> None:
        super().__init__()

    def __str__(self) -> str:
        return logger.info("Rate limit error: FBref returned a 429 status, Too Many Requests." +\
                           "for more detail please see https://www.sports-reference.com/bot-traffic.html.") 