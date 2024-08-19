
from ligas.exceptions import FbrefRequestException, FbrefRateLimitException
from ligas.entity_config import Head2Head
import requests
import threading
import time 

from pathlib import Path
import os
import random

headersKey = ["Chrome", "Edge", "Firefox", "IE", "Other"]
browser_headers = {
    "Chrome": {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
    },
    "Edge": {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-GB,en;q=0.9,en-US;q=0.8",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36 Edg/95.0.1020.44"
    },
    "Firefox": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0"
    },
    "IE": {
        "Accept": "text/html, application/xhtml+xml, image/jxr, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-GB",
        "Connection": "Keep-Alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko"
    }
}


ligaslinks = {
    # Men's club international cups
    'Copa Libertadores': {
        'history url': 'https://fbref.com/en/comps/14/history/Copa-Libertadores-Seasons',
        'finders': ['Copa-Libertadores']},
    'Champions League': {
        'history url': 'https://fbref.com/en/comps/8/history/Champions-League-Seasons',
        'finders': ['European-Cup', 'Champions-League']},
    'Europa League': {
        'history url': 'https://fbref.com/en/comps/19/history/Europa-League-Seasons',
        'finders': ['UEFA-Cup', 'Europa-League']},
    'Europa Conference League': {
        'history url': 'https://fbref.com/en/comps/882/history/Europa-Conference-League-Seasons',
        'finders': ['Europa-Conference-League']},
    # Men's national team competitions
    'World Cup': {
        'history url': 'https://fbref.com/en/comps/1/history/World-Cup-Seasons',
        'finders': ['World-Cup']},
    'Copa America': {
        'history url': 'https://fbref.com/en/comps/685/history/Copa-America-Seasons',
        'finders': ['Copa-America']},
    'Euros': {
        'history url': 'https://fbref.com/en/comps/676/history/European-Championship-Seasons',
        'finders': ['UEFA-Euro', 'European-Championship']},
    # Men's big 5
    'Big 5 combined': {
        'history url': 'https://fbref.com/en/comps/Big5/history/Big-5-European-Leagues-Seasons',
        'finders': ['Big-5-European-Leagues']},
    'EPL': {
        'history url': 'https://fbref.com/en/comps/9/history/Premier-League-Seasons',
        'finders': ['Premier-League', 'First-Division']},
    'Ligue 1': {
        'history url': 'https://fbref.com/en/comps/13/history/Ligue-1-Seasons',
        'finders': ['Ligue-1', 'Division-1']},
    'Bundesliga': {
        'history url': 'https://fbref.com/en/comps/20/history/Bundesliga-Seasons',
        'finders': ['Bundesliga']},
    'Serie A': {
        'history url': 'https://fbref.com/en/comps/11/history/Serie-A-Seasons',
        'finders': ['Serie-A']},
    'La Liga': {
        'history url': 'https://fbref.com/en/comps/12/history/La-Liga-Seasons',
        'finders': ['La-Liga']},
    # Men's domestic leagues - 1st tier
    'MLS': {
        'history url': 'https://fbref.com/en/comps/22/history/Major-League-Soccer-Seasons',
        'finders': ['Major-League-Soccer']},
    'Brazilian Serie A': {
        'history url': 'https://fbref.com/en/comps/24/history/Serie-A-Seasons',
        'finders': ['Serie-A']},
    'Eredivisie': {
        'history url': 'https://fbref.com/en/comps/23/history/Eredivisie-Seasons',
        'finders': ['Eredivisie']},
    'Liga MX': {
        'history url': 'https://fbref.com/en/comps/31/history/Liga-MX-Seasons',
        'finders': ['Primera-Division', 'Liga-MX']},
    'Primeira Liga': {
        'history url': 'https://fbref.com/en/comps/32/history/Primeira-Liga-Seasons',
        'finders': ['Primeira-Liga']},
    'Belgian Pro League': {
        'history url': 'https://fbref.com/en/comps/37/history/Belgian-Pro-League-Seasons',
        'finders': ['Belgian-Pro-League', 'Belgian-First-Division']},
    'Argentina Liga Profesional': {
        'history url': 'https://fbref.com/en/comps/21/history/Primera-Division-Seasons',
        'finders': ['Primera-Division']},
    # Men's domestic league - 2nd tier
    'EFL Championship': {
        'history url': 'https://fbref.com/en/comps/10/history/Championship-Seasons',
        'finders': ['First-Division', 'Championship']},
    'La Liga 2': {
        'history url': 'https://fbref.com/en/comps/17/history/Segunda-Division-Seasons',
        'finders': ['Segunda-Division']},
    '2. Bundesliga': {
        'history url': 'https://fbref.com/en/comps/33/history/2-Bundesliga-Seasons',
        'finders': ['2-Bundesliga']},
    'Ligue 2': {
        'history url': 'https://fbref.com/en/comps/60/history/Ligue-2-Seasons',
        'finders': ['Ligue-2']},
    'Serie B': {
        'history url': 'https://fbref.com/en/comps/18/history/Serie-B-Seasons',
        'finders': ['Serie-B']},
    # Women's internation club competitions
    'Womens Champions League': {
        'history url': 'https://fbref.com/en/comps/181/history/Champions-League-Seasons',
        'finders': ['Champions-League']},
    # Women's national team competitions
    'Womens World Cup': {
        'history url': 'https://fbref.com/en/comps/106/history/Womens-World-Cup-Seasons',
        'finders': ['Womens-World-Cup']},
    'Womens Euros': {
        'history url': 'https://fbref.com/en/comps/162/history/UEFA-Womens-Euro-Seasons',
        'finders': ['UEFA-Womens-Euro']},
    # Women's domestic leagues
    'NWSL': {
        'history url': 'https://fbref.com/en/comps/182/history/NWSL-Seasons',
        'finders': ['NWSL']},
    'A-League Women': {
        'history url': 'https://fbref.com/en/comps/196/history/A-League-Women-Seasons',
        'finders': ['A-League-Women', 'W-League']},
    'WSL': {
        'history url': 'https://fbref.com/en/comps/189/history/Womens-Super-League-Seasons',
        'finders': ['Womens-Super-League']},
    'D1 Feminine': {
        'history url': 'https://fbref.com/en/comps/193/history/Division-1-Feminine-Seasons',
        'finders': ['Division-1-Feminine']},
    'Womens Bundesliga': {
        'history url': 'https://fbref.com/en/comps/183/history/Frauen-Bundesliga-Seasons',
        'finders': ['Frauen-Bundesliga']},
    'Womens Serie A': {
        'history url': 'https://fbref.com/en/comps/208/history/Serie-A-Seasons',
        'finders': ['Serie-A']},
    'Liga F': {
        'history url': 'https://fbref.com/en/comps/230/history/Liga-F-Seasons',
        'finders': ['Liga-F']},
    # Women's domestic cups
    'NWSL Challenge Cup': {
        'history url': 'https://fbref.com/en/comps/881/history/NWSL-Challenge-Cup-Seasons',
        'finders': ['NWSL-Challenge-Cup']},
    'NWSL Fall Series': {
        'history url': 'https://fbref.com/en/comps/884/history/NWSL-Fall-Series-Seasons',
        'finders': ['NWSL-Fall-Series']},
}



class fbref():
    def __init__(self, wait_time :int =10) -> None:
        self.wait_time = wait_time
        choice = random.choice(headersKey)
        self.header = browser_headers.get(choice)

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
            Defining a waiting time for separate requests
        """
        time.sleep(self.wait_time)


