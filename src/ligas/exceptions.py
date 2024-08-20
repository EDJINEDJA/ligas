
from requests import exceptions
from typing import Sequence
from ligas import logger
import logging

class FbrefRequestException(exceptions.RequestException):
    """ 
        Raised this exception when FBref returns bad HTTP status.
        (4xx or 5xx) 
    """

    def __init__(self) -> None:
        super().__init__()


    def __str__(self) -> str:
        return "Bad responses (4xx or 5xx)"
    

class FbrefRateLimitException(Exception):
    """ 
        Raised this exception when FBref returns HTTP status 429, rate limit request
    """
    def __init__(self) -> None:
        super().__init__()

    def __str__(self) -> str:
        return "Rate limit error: FBref returned a 429 status, Too Many Requests." +\
                           "for more detail please see https://www.sports-reference.com/bot-traffic.html."
    
class FbrefInvalidLeagueException(Exception):
    """
        Raised this exception when invalid league is provided by the client
    """

    def __init__(self, league : str, module : str, leagues : Sequence[str]) -> None:
        self.league = league
        self.leagues = leagues
        self.module = module
        super().__init__()

        

    def __str__(self)->str:

        return f"InvalidLeague: {self.league} not exist for {self.module} , please find the right league in " +\
                           f"{self.leagues}"