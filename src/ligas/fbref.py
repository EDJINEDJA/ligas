
from pathlib import Path
import os
import random
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import threading
import time 

from .exceptions import (FbrefRequestException, FbrefRateLimitException, 
        FbrefInvalidLeagueException, FbrefInvalidYearException)
from .entity_config import Head2Head, SeasonUrls,CurrentSeasonUrls, TopScorers, BestScorer
from .utils import compositions
from .utils import browserHeaders
from .utils import browser

from .logger import logger
validLeagues = [league for league in compositions.keys()]

class fbref():
    def __init__(self, wait_time :int =5) -> None:
        self.baseurl = 'https://fbref.com/'
        self.wait_time = wait_time
        webBrowser = random.choice(browser)
        self.header = browserHeaders.get(webBrowser)

    
    # ====================================== request http ==========================================#
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
    
    # ====================================== Waiting time to avoid rate limit error ====================#
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
                A dictionary in the format {year: URL, ...}, where URLs should be prefixed with "https://fbref.com" 
                to form a complete link.
        """

        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
        
        

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
    
    #====================================== LeagueInfos ==========================================#
    
    def LeagueInfos(self, year : str, league: str) -> dict:
        """
        Retrieves league information for a given year and league name.

        Args:
            year (str): Desired year, which must not exceed the current year.
                        Example: "2023-2024"

        Returns:
            league_info (dict): 
                A dictionary in the format {info_header: info}, where `info_header` 
                represents the title of the information, and `info` is the corresponding detail.
        """


        if not isinstance(year, str):
            raise TypeError('`year` must be a string eg: 2024-2025')
        
        if not isinstance(league, str):
            raise TypeError('`league` must be a string eg: Champions League .')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)
        
        cuurentYear = datetime.now().year
        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        urls = self.get_valid_seasons(league)
        url = urls.seasonUrls[year]
        
        response = requests.get(os.path.join(self.baseurl,url[1:]))
        soup = BeautifulSoup(response.content, 'html.parser')
        r = soup.find('div', attrs={ 'id':'meta'})
        
        leagueInfos = {
                        p.find('strong').text.strip(':'): 
                        (p.find('a').text if p.find('a') is not None else p.find('span').text 
                         if p.find('span') is not None else p.get_text(strip=True).replace(p.find('strong').text, '').strip())
                        for p in r.find_all('p')
                        if p.find('strong') is not None
                    }
        
        return leagueInfos
        
    #====================================== get_top_scorers ==========================================#
    
    def get_top_scorers(self, league: str) -> TopScorers:
        """
            years, club name, links to stats, 
        """
        return NotImplementedError
    
    #====================================== topScorer ==========================================#

    def topScorer(self, league : str) -> BestScorer:
        """
            Scraped the best scorer stats
            Args:
                league (str): getting valid league id
            Returns:
                BestScorer : stats of the best scorer of the season 
        """
        return NotImplementedError
    


