
from pathlib import Path
import os
import random

import requests
import threading
import time 

from bs4 import BeautifulSoup
import threading
import time 

from .exceptions import FbrefRequestException, FbrefRateLimitException, FbrefInvalidLeagueException
from .entity_config import Head2Head, SeasonUrls,CurrentSeasonUrls, TopScorers, BestScorer
from .utils import compositions
from .utils import browserHeaders
from .utils import browser

from .logger import logger


class fbref():
    def __init__(self, wait_time :int =5) -> None:
        self.wait_time = wait_time
        webBrowser = random.choice(browser)
        self.header = browserHeaders.get(webBrowser)

    def _get(self, url : str) -> requests.Response:

        """
            call _get create an instance of requests
            Args:
                url (str): is the the endpoint of fbref website 
            Returns:
                object (requests.Response): return the response
        """
       
        
        response = requests.get(url=url, headers=self.header)
        wait_thread = threading.Thread(target=self._wait)
        wait_thread.start()

        status = response.status_code

        if status == 429:
            raise FbrefRateLimitException()
 
        if status in set([404, 504]) :
            raise  FbrefRequestException()
        
        return response
    
    def _wait(self):
        """
            Defining a waiting time for avoid rate limit 
        """
        time.sleep(self.wait_time)
    
    # ====================================== get_current_seasons ==========================================#
    def get_valid_seasons(self, league: str) -> SeasonUrls:
        """
        Retrieves all valid years and their corresponding URLs for a specified competition.

        Args:
            league : str
                The league for which to obtain valid seasons. Examples include "EPL" and "La Liga". 
                For a full list of options, import `compositions` from the FBref module and check the keys.

        Returns:
            Season and URLs : SeasonUrls[dict]
                A dictionary in the format {year: URL, ...}, where URLs should be prefixed with "https://fbref.com" to form a complete link.
        """

        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
        
        validLeagues = [league for league in compositions.keys()]

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        url = compositions[league]['history url']
        r = self._get(url)
        soup = BeautifulSoup(r.content, 'html.parser')

        seasonUrls = dict([
            (x.text, x.find('a')['href'])
            for x in soup.find_all('th', {'data-stat': True, 'class': True})
            if x.find('a') is not None
        ])

        return SeasonUrls(seasonUrls)
    
    def getCurrentSeasons(self, league: str) -> CurrentSeasonUrls:
        """
            year , ligue stats link
        """
        return NotImplementedError
    
    def get_top_scorers(self, league: str) -> TopScorers:
        """
            years, club name, links to stats, 
        """
        return NotImplementedError

    def topScorer(self, league : str) -> BestScorer:
        """
            Scraped the best scorer stats
            Args:
                league (str): getting valid league id
            Returns:
                BestScorer : stats of the best scorer of the season 
        """
        return NotImplementedError
    


