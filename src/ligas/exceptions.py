
from requests import exceptions
from utils import logger

class FbrefRequestsHTTPError(exceptions.HTTPError):
    """ Raised when FBref returns HTTP status 404, invalid url
    """

    def __init__(self) -> None:
        super().__init__()


    def __str__(self) -> str:
        return logger.info("FBref returned a 429 status, fbref url is invalid")
    

class FBrefRateLimitException(Exception):
    """ Raised when FBref returns HTTP status 429, rate limit request
    """
    def __init__(self) -> None:
        super().__init__()

    def __str__(self) -> str:
        return "FBref returned a 429 status, Too Many Requests. See " +\
            "https://www.sports-reference.com/bot-traffic.html for more details." 