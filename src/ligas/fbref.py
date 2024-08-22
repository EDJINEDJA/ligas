from pathlib import Path
import os
import re
import random
from datetime import datetime

from typing import Sequence, List, Dict
import requests
from bs4 import BeautifulSoup
from io import StringIO
import threading
import time 
import numpy as np
import pandas as pd

from .exceptions import (FbrefRequestException, FbrefRateLimitException, 
        FbrefInvalidLeagueException, FbrefInvalidYearException, FbrefInvalidSeasonsException, FbrefInvalidTeamException)
from .entity_config import Head2Head, SeasonUrls,CurrentSeasonUrls, TopScorers, BestScorer
from .utils import compositions
from .utils import browserHeaders
from .utils import browser

from .logger import logger

cuurentYear = datetime.now().year
validLeagues = [league for league in compositions.keys()]
webBrowser = random.choice(browser)
header = browserHeaders.get(webBrowser)

class fbref():
    def __init__(self, wait_time :int = 10, baseurl : str = 'https://fbref.com/') -> None:
        self.baseurl = baseurl
        self.wait_time = wait_time
      
    
    # ====================================== request http ==========================================#
    def _get(self, url : str) -> requests.Response:

        """
            call _get create an instance of requests
            Args:
                url (str): is the the endpoint of fbref website 
            Returns:
                object (requests.Response): return the response
        """
       
        
        response = requests.get(url=url, headers = header)
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
                A dictionary containing the following keys
                'Governing Country': eg 'Spain' (country of the league)
                'Level':  eg 'See League Structure' (level of the league)
                'Gender': ': Male' ( gender)
                'Most Goals': 'Robert Lewandowski', ( player name)
                'Most Assists': 'Iker Almena'( assist name)
                'Most Clean Sheets': 'Karl Jakob Hein' ( name of the clean sheet)
                'Big 5': 'View Big 5 European Leagues together' ( the level of the league)
                'league logo': 'https://cdn.ssref.net/req/202408161/tlogo/fb/12.png' ( logo of the league)
        """
        if not isinstance(league, str):
           raise  TypeError('`league` must be a str eg: Champions League .')
        
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

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
        leagueInfos['logo'] = r.find('img', attrs={'class':'teamlogo'})['src']
        
        return leagueInfos
        
    #====================================== get_top_scorers ==========================================#
    
    def TopScorers(self, league: str) -> dict:
        """
        Retrieves the top scorer's statistics for a given league and season.

        Args:
            league (str): 
                The league identifier for which to obtain TopScorers.
                Examples include "EPL" (English Premier League) and "La Liga" (Spain's top division).
            currentSeason (str): 
                The season for which to retrieve the top scorer's statistics.
                The format is typically "YYYY-YYYY", e.g., "2023-2024".

        Returns:
            dict: 
                A dictionary containing the following keys:
                - 'top_scorer': The name of the top scorer.
                - 'goals': The number of goals scored by the top scorer.
                - 'stats_link': The direct link to the detailed statistics of the top scorer.
                - 'club': The club the top scorer played for during that season.
                - 'top_scorer_link': The link to the player's profile on the website.

        Raises:
            ValueError: If no data is found for the given league and season.
            TypeError: If the required table is not found on the page.
            """
        if not isinstance(league, str):
           raise  TypeError('`league` must be a str eg: Champions League .')
        
        if league not in validLeagues:
           raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        url = compositions[league]['history url']
        r = self._get(url)
        soup = BeautifulSoup(r.content, 'html.parser')
     
        top_scorers = {
                f'{league} season {row.find("th", {"data-stat": "year_id"}).text.strip()}': {
                    'year': row.find("th", {"data-stat": "year_id"}).text.strip(),
                    'top_scorer': row.find('td', {'data-stat': 'top_scorers'}).find('a').text.strip(),
                    'goals': row.find('td', {'data-stat': 'top_scorers'}).find('span').text.strip(),
                    'stats_link': self.baseurl + row.find('td', {'data-stat': 'top_scorers'}).find('a')['href'],
                    'club': row.find('td', {'data-stat': 'champ'}).text.split('-')[0].strip() if row.find('td', {'data-stat': 'champ'}) else "Unknown"
                }
                for row in soup.find_all('tr')
                if row.find('td', {'data-stat': 'top_scorers'}) and row.find('td', {'data-stat': 'top_scorers'}).find('a')
            }
        return top_scorers
    
    #====================================== TopScorer ==========================================#

    def TopScorer(self, league: str, currentSeason: str) -> dict:
        """
        Scrapes the best scorer's statistics for a specified league and season.

        Args:
            league (str): The league identifier (e.g., "EPL", "La Liga").
            currentSeason (str): The season to retrieve (e.g., "2023-2024").

        Returns:
            dict: A dictionary containing the top scorer's name, goals, stats link, and club.

        Raises:
            ValueError: If no data is found for the given league and season.
            TypeError: If the stats table is not found on the page.
        """
        # Fetch the top scorers data for the given league
        response = self.TopScorers(league=league)
        key = f'{league} season {currentSeason}'

        # Check if the season data exists
        if key not in response:
            # Raise an error if no data is found for the given season
            raise FbrefInvalidSeasonsException(currentSeason, 'Fbref', league,  response.keys() )

        stats_link = response[key]['stats_link']
        
        # Fetch and parse the top scorer's stats page
        r = self._get(stats_link)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table', {'id': 'scout_summary_FW'})

        if not table:
            raise TypeError("The statistics table was not found on the page.")

        # Extract statistics using list comprehension
        stats = [
            {
                'statistic': row.find('th', {'data-stat': 'statistic'}).text.strip(),
                'per90': row.find('td', {'data-stat': 'per90'}).text.strip(),
                'percentile': row.find('td', {'data-stat': 'percentile'}).text.strip()
            }
            for row in table.find_all('tr')[1:]  # Skip the header row
        ]

        # Return the extracted data in a structured dictionary
        return {
            'top_scorer': response[key]['top_scorer'],
            'goals': response[key]['goals'],
            'stats_link': stats_link,
            'club': response[key]['club'],
            'detailed_stats': stats
        }
    
    #====================================== Fixtures ==========================================#
    def Fixtures(self, year : str , league : str) -> dict:
        """Fixtures containing match report and head to head
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time
                    referre

                    stats
                        away
                            xg
                            link team stats
                        home
                            xg
                            link team stats
                    score
                        away
                        home
                    venue
                    teams
                        away
                        home

        """

        if not isinstance(league, str):
           raise  TypeError('`league` must be a str eg: Champions League .')
    
        if league not in validLeagues:
           raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        urls = self.get_valid_seasons(league)
                
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

      # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
        {
            'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
            'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
            'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
            'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
            'stats': {
                'home': {
                    'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                    'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan
                },
                'away': {
                    'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                    'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                }
            },
            'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
            'score': {
                'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
            },
            'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
            'teams': {
                'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
            }
        }
        for row in table.find_all('tr') 
        if row.find('td', {'data-stat': 'match_report'}) and any(term in row.find('td', {'data-stat': 'match_report'}).text for term in ['Head-to-Head', 'Match Report'])
    ]
        }

        return fixtures


    #====================================== MatchReport ==========================================#
    def MatchReport(self, year : str , league : str) -> dict:
        """Fixtures containing match report and head to head
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            xg
                            link team stats
                        home
                            xg
                            link team stats
                    score
                        away
                        home
                    venue
                    teams
                        away
                        home

            """
        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
        
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
            
        urls = self.get_valid_seasons(league)
                
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
            {
                'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                'stats': {
                    'home': {
                        'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                        'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan
                    },
                    'away': {
                        'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                        'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                    }
                },
                'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                'score': {
                    'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                    'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                },
                'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                'teams': {
                    'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                    'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                }
            }
            for row in table.find_all('tr') 
            if row.find('td', {'data-stat': 'match_report'}) and 'Match Report' in row.find('td', {'data-stat': 'match_report'}).text
        ]
            }

        return fixtures

    #====================================== Head Head ==========================================#
    def HeadHead(self, year : str , league : str) -> dict:
        """Fixtures containing match report and head to head
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            link team stats
                        home
                            link team stats
                    venue
                    teams
                        away
                        home

        """
        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
            
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        urls = self.get_valid_seasons(league)
                
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                {
                    'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                    'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                    'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                    'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                    'stats': {
                        'home': {
                            'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan
                        },
                        'away': {
                            'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                        }
                    },
                    'score': {
                        'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                        'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                    },
                    'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                    'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                    'teams': {
                        'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                        'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                    }
                }
                for row in table.find_all('tr') 
                if row.find('td', {'data-stat': 'match_report'}) and 'Head-to-Head' in row.find('td', {'data-stat': 'match_report'}).text
            ]
                }

        return fixtures
    #====================================== Matches ==========================================#

    def Matches(self, date : str, year : str , league : str) -> dict:
        """Fixtures containing matches of the date
            Args:
                date (str)
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            link team stats
                        home
                            link team stats
                    venue
                    teams
                        away
                        home

        """
        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
            
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        urls = self.get_valid_seasons(league)
                
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                {
                    'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                    'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                    'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                    'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                    'stats': {
                        'home': {
                            'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan
                        },
                        'away': {
                            'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                        }
                    },
                    'score': {
                        'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                        'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                    },
                    'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                    'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                    'teams': {
                        'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                        'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                    }
                }
                for row in table.find_all('tr') 
                if row.find('td', {'data-stat': 'match_report'}) and any(term in row.find('td', {'data-stat': 'match_report'}).text for term in ['Head-to-Head', 'Match Report'])
                # Filter matches for a given date
        and     row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).text.strip() == date
            ]
                }

        return fixtures
 
    #====================================== Fixture team ==========================================#
    def FixturesByTeam(self, team : str, year : str , league : str) -> dict:
        """FixtureTeam containing match report and head to head of one  club
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str) 
                        home
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str)
                    score
                        away
                        home
                    venue
                    teams
                        away
                        home

        """
        if not isinstance(league, str):
            raise  TypeError('`league` must be a str eg: Champions League .')
            
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        urls = self.get_valid_seasons(league)
                
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                {
                    'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                    'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                    'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                    'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                    'stats': {
                        'home': {
                            'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                            'team stats' : self.TeamInfos(team, league)
                        },
                        'away': {
                            'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                            'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan,
                            'team stats' : self.TeamInfos(team, league)
                        }
                    },
                    'score': {
                        'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                        'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                    },
                    'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                    'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                    'teams': {
                        'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                        'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                    }
                }
                for row in table.find_all('tr') 
                if row.find('td', {'data-stat': 'match_report'}) and any(term in row.find('td', {'data-stat': 'match_report'}).text for term in ['Head-to-Head', 'Match Report'])
                 # Filter matches where the target team is either the home or away team
             and (
            (row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() == team) or
            (row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() == team)
        )
            ]
                }

        return fixtures
    
    #====================================== Match report By team ==========================================#
    def MatchReportByTeam(self, team : str, year : str , league : str) -> dict:
        """MatchReportByTeam containing match report of one  club
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str) 
                        home
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str)
                    score
                        away
                        home
                    venue
                    teams
                        away
                        home

        """
        if not isinstance(league, str):
                raise  TypeError('`league` must be a str eg: Champions League .')
                
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
            
        urls = self.get_valid_seasons(league)
                    
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                    {
                        'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                        'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                        'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                        'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                        'stats': {
                            'home': {
                                'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                                'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                                'team stats' : self.TeamInfos(team, league)
                            },
                            'away': {
                                'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                                'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan,
                                'team stats' : self.TeamInfos(team, league)
                            }
                        },
                        'score': {
                            'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                            'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                        },
                        'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                        'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                        'teams': {
                            'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                            'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                        }
                    }
                    for row in table.find_all('tr') 
                    if row.find('td', {'data-stat': 'match_report'}) and 'Match Report' in row.find('td', {'data-stat': 'match_report'}).text
                    # Filter matches where the target team is either the home or away team
                and (
                (row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() == team) or
                (row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() == team)
            )
                ]
                    }

        return fixtures
    #====================================== Head Head By Team ==========================================#
    def HeadHeadByTeam(self, team : str, year : str , league : str) -> dict:
        """HeadHeadByTeam containing  head to head of one  club
            Args:
                year (str)
                league (str)
            Returns:

                fixtures

                    match link
                    data-venue-time-only
                    referre

                    stats
                        away
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str) 
                        home
                            xg
                            link team stats
                            team stats : TeamInfos(self,  team: str, league : str)
                            players : Players(self, team: str, league: str)
                    score
                        away
                        home
                    venue
                    teams
                        away
                        home

        """
        if not isinstance(league, str):
                raise  TypeError('`league` must be a str eg: Champions League .')
                
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
            
        urls = self.get_valid_seasons(league)
                    
        season_link = urls.seasonUrls[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                    {
                        'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
                        'match-date': row.find('td', {'data-stat': 'date'}).text.strip() if row.find('td', {'data-stat': 'date'}) else np.nan,
                        'data-venue-time': row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True})['data-venue-time'] if row.find('td', {'data-stat': 'start_time'}) and row.find('td', {'data-stat': 'start_time'}).find('span', {'data-venue-time': True}) else np.nan,
                        'referee': row.find('td', {'data-stat': 'referee'}).text.strip() if row.find('td', {'data-stat': 'referee'}) else np.nan,
                        'stats': {
                            'home': {
                                'xg': row.find('td', {'data-stat': 'home_xg'}).text.strip() if row.find('td', {'data-stat': 'home_xg'}) else np.nan,
                                'link team stats': self.baseurl + row.find('td', {'data-stat': 'home_team'}).find('a')['href'] if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                                'team stats' : self.TeamInfos(team, league)
                            },
                            'away': {
                                'xg': row.find('td', {'data-stat': 'away_xg'}).text.strip() if row.find('td', {'data-stat': 'away_xg'}) else np.nan,
                                'link team stats': self.baseurl + row.find('td', {'data-stat': 'away_team'}).find('a')['href'] if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan,
                                'team stats' : self.TeamInfos(team, league)
                            }
                        },
                        'score': {
                            'home': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[0].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan),
                            'away': (row.find('td', {'data-stat': 'score'}).find('a').text.strip().split('–')[1].strip() if row.find('td', {'data-stat': 'score'}) and row.find('td', {'data-stat': 'score'}).find('a') else np.nan)
                        },
                        'Attendance': row.find('td', {'data-stat': 'attendance'}).text.strip() if row.find('td', {'data-stat': 'attendance'}) else np.nan,
                        'venue': row.find('td', {'data-stat': 'venue'}).text.strip() if row.find('td', {'data-stat': 'venue'}) else np.nan,
                        'teams': {
                            'home': row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a') else np.nan,
                            'away': row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() if row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a') else np.nan
                        }
                    }
                    for row in table.find_all('tr') 
                    if row.find('td', {'data-stat': 'match_report'}) and 'Head-to-Head' in row.find('td', {'data-stat': 'match_report'}).text
                    # Filter matches where the target team is either the home or away team
                and (
                (row.find('td', {'data-stat': 'home_team'}) and row.find('td', {'data-stat': 'home_team'}).find('a').text.strip() == team) or
                (row.find('td', {'data-stat': 'away_team'}) and row.find('td', {'data-stat': 'away_team'}).find('a').text.strip() == team)
            )
                ]
                    }

        return fixtures
    #====================================== TeamsInfo ================================================#
    def TeamsInfo(self,  league : str) -> dict:
        """
        Retrieves team information for a specified club and league, including current and previous season stats, previous and next matches, and seasonal trajectories.

        Args:
            club (str): The name of the club.
            league (str): The name of the league (e.g., "Champions League").

        Returns:
            dict: A dictionary where each key is a team name, and the value is another dictionary containing:
                - 'rank': The team's rank in the current season (starting from 1).
                - 'logo': The URL of the team's logo.
                - 'games': The number of games played.
                - 'url' :  the url to the team stats
                - 'current stats': A nested dictionary with the following current season statistics:
                    - 'wins': Number of wins.
                    - 'draws': Number of draws.
                    - 'losses': Number of losses.
                    - 'goals_for': Number of goals scored.
                    - 'goals_against': Number of goals conceded.
                    - 'goal_diff': Goal difference.
                    - 'points': Total points.
                    - 'points_avg': Average points per game.
                    - 'xg_for': Expected goals for.
                    - 'xg_against': Expected goals against.
                    - 'xg_diff': Expected goals difference.
                    - 'xg_diff_per90': Expected goals difference per 90 minutes.
                    - 'last_result': Result of the last match.
                    - 'top_scorer': Top scorer of the team.
                    - 'top_keeper': Top goalkeeper of the team.
                - 'previous stats': A dictionary of statistics from the previous season if available, otherwise an empty dictionary.

        Raises:
            TypeError: If `league` is not a string.
            FbrefInvalidLeagueException: If `league` is not a valid league name.
        """

        if not isinstance(league, str):
           raise  TypeError('`league` must be a str eg: Champions League .')
        
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        
        urls = self.get_valid_seasons(league)

        #---------------------getting Cuurent Team Stats--------------------------------------
      
        url = urls.seasonUrls[f"{int(cuurentYear)-1}-{cuurentYear}"]
        response = self._get(os.path.join(self.baseurl,url[1:]))
        soup = BeautifulSoup(response.content, 'html.parser')

        #  Looking for the table with the classes 'wikitable' and 'sortable'
        table = soup.find('table', class_='stats_table')

        # Collecting data into a dictionary with team names as keys and including rank
        cuurentTeamStats = {
            row.find_all('td')[0].find("a").get_text(strip=True): {
                "rank": index + 1,
                "logo": row.find_all('td')[0].find('img')['src'],
                "url": row.find_all('td')[0].find("a")['href'],
                "games": int(row.find_all('td')[1].get_text(strip=True)),
                "current stats" : {"wins": int(row.find_all('td')[2].get_text(strip=True)),
                    "draws": int(row.find_all('td')[3].get_text(strip=True)),
                    "losses": int(row.find_all('td')[4].get_text(strip=True)),
                    "goals_for": int(row.find_all('td')[5].get_text(strip=True)),
                    "goals_against": int(row.find_all('td')[6].get_text(strip=True)),
                    "goal_diff": row.find_all('td')[7].get_text(strip=True),
                    "points": int(row.find_all('td')[8].get_text(strip=True)),
                    "points_avg": float(row.find_all('td')[9].get_text(strip=True)),
                    "xg_for": float(row.find_all('td')[10].get_text(strip=True)),
                    "xg_against": float(row.find_all('td')[11].get_text(strip=True)),
                    "xg_diff": row.find_all('td')[12].get_text(strip=True),
                    "xg_diff_per90": row.find_all('td')[13].get_text(strip=True),
                    "last_result": row.find_all('td')[14].get_text(strip=True),
                    "top_scorer": row.find_all('td')[16].get_text(strip=True),
                    "top_keeper": row.find_all('td')[17].get_text(strip=True)}
            }
            for index, row in enumerate(table.tbody.find_all('tr'))
            if row.find_all('td')  # Ensures only rows with data are processed
        }

        #  Looking for the table with the classes 'wikitable' and 'sortable'
        table2 = soup.find('table', {'class':re.compile('stats'), 'id':re.compile('for')})



        #--------------------- getting previous Year Team Stats--------------------------------------
      
        
        url = urls.seasonUrls[f"{cuurentYear}-{int(cuurentYear)+1}"]
        
        response = self._get(os.path.join(self.baseurl,url[1:]))
        soup = BeautifulSoup(response.content, 'html.parser')

        # Collecting data into a dictionary with team names as keys and including rank
        previousTeamStats = {
            row.find_all('td')[0].find("a").get_text(strip=True): {
                "rank": index + 1,
                "logo": row.find_all('td')[0].find('img')['src'],
                "url": row.find_all('td')[0].find("a")['href'],
                "games": int(row.find_all('td')[1].get_text(strip=True)),
                "wins": int(row.find_all('td')[2].get_text(strip=True)),
                "draws": int(row.find_all('td')[3].get_text(strip=True)),
                "losses": int(row.find_all('td')[4].get_text(strip=True)),
                "goals_for": int(row.find_all('td')[5].get_text(strip=True)),
                "goals_against": int(row.find_all('td')[6].get_text(strip=True)),
                "goal_diff": row.find_all('td')[7].get_text(strip=True),
                "points": int(row.find_all('td')[8].get_text(strip=True)),
                "points_avg": float(row.find_all('td')[9].get_text(strip=True)),
                "xg_for": float(row.find_all('td')[10].get_text(strip=True)),
                "xg_against": float(row.find_all('td')[11].get_text(strip=True)),
                "xg_diff": row.find_all('td')[12].get_text(strip=True),
                "xg_diff_per90": row.find_all('td')[13].get_text(strip=True),
                "last_result": row.find_all('td')[14].get_text(strip=True),
                "top_scorer": row.find_all('td')[16].get_text(strip=True), 
                "top_keeper": row.find_all('td')[17].get_text(strip=True),
            }
            for index, row in enumerate(table.tbody.find_all('tr'))
            if row.find_all('td')  # Ensures only rows with data are processed
        }

        #------------Create a new dictionary with updated stats including previous stats----------
        teamStats = cuurentTeamStats
        for team in cuurentTeamStats.keys():
            if team in previousTeamStats.keys():
                cuurentTeamStats[team]["previous stats"] = previousTeamStats[team]
        
        return teamStats
    
    #====================================== TeamsInfo ================================================#
    def TeamInfos(self,  team: str, league : str) -> dict:
        """
        Retrieves detailed information for a specific team within a specified league.

        Args:
            team (str): The name of the team whose information is being requested.
            league (str): The name of the league where the team plays (e.g., "Champions League").

        Returns:
            dict: A dictionary containing detailed information about the specified team. The structure of the dictionary includes:
                - 'rank': The team's rank in the current season (starting from 1).
                - 'logo': The URL of the team's logo.
                - 'url' :  the url to the team stats.
                - 'games': The number of games played.
                - 'current stats': A nested dictionary with current season statistics:
                    - 'wins': Number of wins.
                    - 'draws': Number of draws.
                    - 'losses': Number of losses.
                    - 'goals_for': Number of goals scored.
                    - 'goals_against': Number of goals conceded.
                    - 'goal_diff': Goal difference.
                    - 'points': Total points.
                    - 'points_avg': Average points per game.
                    - 'xg_for': Expected goals for.
                    - 'xg_against': Expected goals against.
                    - 'xg_diff': Expected goals difference.
                    - 'xg_diff_per90': Expected goals difference per 90 minutes.
                    - 'last_result': Result of the last match.
                    - 'top_scorer': Top scorer of the team.
                    - 'top_keeper': Top goalkeeper of the team.
                - 'previous stats': A dictionary of statistics from the previous season if available, otherwise an empty dictionary.

        Raises:
            TypeError: If `league` is not a string.
            FbrefInvalidLeagueException: If `league` is not a valid league name.
            FbrefInvalidTeamException: If `team` is not a valid team name in the specified league.

        """
        if not isinstance(league, str):
           raise  TypeError('`league` must be a str eg: Champions League .')
        
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        teamsInfo = self.TeamsInfo(league)


        validTeams = teamsInfo.keys()

        if team not in validTeams:
            raise  FbrefInvalidTeamException(cuurentYear,'FBref', league,  team , list(validTeams))
        
        teamInfos = teamsInfo[team]

        #Adding additional stats current season
        team_url = os.path.join(self.baseurl,teamInfos["url"][1:])

        response = self._get(team_url)

        soup = BeautifulSoup(response.content, 'html.parser')

        players = self._players(soup)

        teamstatscompetitions = self._teamstatscompetitions(soup)

        keeper = self._keeper(soup)

        passing = self._passing(soup)

        shooting = self._shooting(soup)

        passing_type = self._passing_type(soup)

        goal_shot_creation = self._goal_shot_creation(soup)

        defensive_actions = self._defensive_actions(soup)

        possession = self._possession(soup)

        passing_type = self._passing_type(soup)


        #Adding additional stats in team info
        teamInfos['current stats']['players'] = players

        teamInfos['current stats']['Scores & Fixtures'] = teamstatscompetitions

        teamInfos['current stats']['keeper'] = keeper

        teamInfos['current stats']['passing'] = passing

        teamInfos['current stats']['shooting'] = shooting

        teamInfos['current stats']['passing_type'] = passing_type

        teamInfos['current stats']['goal_shot_creation'] = goal_shot_creation

        teamInfos['current stats']['defensive_actions'] =  defensive_actions

        teamInfos['current stats']['possession'] = possession

        teamInfos['current stats']['passing_type'] = passing_type

        #Adding additional stats previous season
        team_url = os.path.join(self.baseurl,teamInfos["previous stats"]["url"][1:])

        response = self._get(team_url)

        soup = BeautifulSoup(response.content, 'html.parser')

        players = self._players(soup)

        teamstatscompetitions = self._teamstatscompetitions(soup)

        keeper = self._keeper(soup)

        passing = self._passing(soup)

        shooting = self._shooting(soup)

        passing_type = self._passing_type(soup)

        goal_shot_creation = self._goal_shot_creation(soup)

        defensive_actions = self._defensive_actions(soup)

        possession = self._possession(soup)

        passing_type = self._passing_type(soup)


        #Adding additional stats in team info
        teamInfos["previous stats"]['players'] = players

        teamInfos["previous stats"]['Scores & Fixtures'] = teamstatscompetitions

        teamInfos["previous stats"]['keeper'] = keeper

        teamInfos["previous stats"]['passing'] = passing

        teamInfos["previous stats"]['shooting'] = shooting

        teamInfos["previous stats"]['passing_type'] = passing_type

        teamInfos["previous stats"]['goal_shot_creation'] = goal_shot_creation

        teamInfos["previous stats"]['defensive_actions'] =  defensive_actions

        teamInfos["previous stats"]['possession'] = possession

        teamInfos["previous stats"]['passing_type'] = passing_type
       
        return teamInfos

    #====================================== _players =========================================#
    
    @staticmethod
    def _players(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing player statistics and their corresponding URLs 
        from an HTML table within the provided BeautifulSoup object.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage 
                                with the player statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing player statistics with additional player URLs. 
                        The columns include various stats like appearances, goals, assists, 
                        and more, along with the player's name and URL.
        """
        # Locate the table containing player statistics
        table = soup.find('table', {'class': 'stats_table', 'id': 'stats_standard_12'})

        # Extract player names and their corresponding URLs
        data = {
            row.find('th', {'data-stat': "player"}).text: row.find('th', {'data-stat': "player"}).find('a')['href']
            for row in table.tbody.find_all('tr')
        }

        # Convert the player URLs to a DataFrame
        players_urls = pd.DataFrame(list(data.items()), columns=['Player', 'Url'])

        # Read the HTML table into a DataFrame
        players = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers
        players.columns = players.columns.droplevel(0)

        # Merge the players DataFrame with the URLs DataFrame
        players = players.merge(players_urls, how='left', on='Player')

        return players

    #====================================== _teamstatscompetitions =========================================#

    @staticmethod
    def _teamstatscompetitions(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing team statistics from a table within the provided 
        BeautifulSoup object. This table typically contains data for scores, fixtures, and other 
        related statistics across all competitions.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage 
                                with the team statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing team statistics across all competitions, 
                        with columns representing various performance metrics.
        """
        # Locate the table containing team statistics for all competitions
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('for')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        teamstatsallcompetition = pd.read_html(StringIO(str(table)))[0].fillna('-')

        return teamstatsallcompetition

    
    #====================================== _keeper =========================================#
    
    @staticmethod
    def _keeper(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing goalkeeper statistics from a table within the provided
        BeautifulSoup object. This table typically includes data related to goalkeeping performance.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                goalkeeper statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing goalkeeper statistics, with columns representing various
                        goalkeeping performance metrics.
        """
        # Locate the table containing goalkeeper statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('keeper')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        keeper = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        keeper.columns = keeper.columns.droplevel(0)

        return keeper
    
    #====================================== _passing =========================================#

    @staticmethod
    def _passing(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing passing statistics from a table within the provided
        BeautifulSoup object. This table typically includes data related to passing performance metrics
        for players or teams.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                passing statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing passing statistics, with columns representing various
                        passing performance metrics.
        """
        # Locate the table containing passing statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('passing')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        passing = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        passing.columns = passing.columns.droplevel(0)

        return passing

    
    #====================================== _shooting =========================================#

    @staticmethod
    def _shooting(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing shooting statistics from a table within the provided
        BeautifulSoup object. This table typically includes data related to shooting performance metrics
        for players or teams.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                shooting statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing shooting statistics, with columns representing various
                        shooting performance metrics.
        """
        # Locate the table containing shooting statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('shooting')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        shooting = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        shooting.columns = shooting.columns.droplevel(0)

        return shooting

    
    #====================================== _passing_type =========================================#

    @staticmethod
    def _passing_type(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing passing type statistics from a table within the provided
        BeautifulSoup object. This table typically includes data related to different types of passes, such as
        short, medium, and long passes, as well as their accuracy and success rates.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                passing type statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing passing type statistics, with columns representing various
                        metrics related to the types of passes.
        """
        # Locate the table containing passing type statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('passing_type')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        passing_type = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        passing_type.columns = passing_type.columns.droplevel(0)

        return passing_type

    
    #====================================== _goal_shot_creation =========================================#
    
    @staticmethod
    def _goal_shot_creation(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing statistics related to goal and shot creation from a table
        within the provided BeautifulSoup object. This table typically includes data on actions leading to shots
        and goals, such as key passes, dribbles, and fouls drawn.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                goal and shot creation statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing goal and shot creation statistics, with columns representing
                        various metrics related to shot-creating actions (SCA) and goal-creating actions (GCA).
        """
        # Locate the table containing goal and shot creation statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('gca')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        goal_shot_creation = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        goal_shot_creation.columns = goal_shot_creation.columns.droplevel(0)

        return goal_shot_creation
    
    #====================================== _defensive_actions =========================================#
    
    @staticmethod
    def _defensive_actions(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing statistics related to defensive actions from a table
        within the provided BeautifulSoup object. This table typically includes data on actions such as tackles,
        interceptions, clearances, and blocks.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                defensive actions statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing defensive actions statistics, with columns representing
                        various metrics related to defensive contributions such as tackles, interceptions,
                        and clearances.
        """
        # Locate the table containing defensive actions statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('defense')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        defensive_actions = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        defensive_actions.columns = defensive_actions.columns.droplevel(0)

        return defensive_actions

    
    #====================================== _possession =========================================#
    
    @staticmethod
    def _possession(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing statistics related to possession from a table
        within the provided BeautifulSoup object. This table typically includes data on metrics such as
        possession percentage, passes, and other possession-related statistics.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                possession statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing possession statistics, with columns representing
                        various metrics related to possession such as possession percentage, total passes,
                        and other relevant possession data.
        """
        # Locate the table containing possession statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('possession')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        possession = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        possession.columns = possession.columns.droplevel(0)

        return possession

    
    #====================================== _playing_time =========================================#
    
    @staticmethod
    def _playing_time(soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing player playing time statistics from a table
        within the provided BeautifulSoup object. This table typically includes data such as total
        minutes played, average minutes per game, and other metrics related to playing time.

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the
                                playing time statistics table.

        Returns:
            pd.DataFrame: A DataFrame containing playing time statistics, with columns representing
                        various metrics related to player participation and time on the field.
        """
        # Locate the table containing playing time statistics
        table = soup.find('table', {'class': re.compile('stats'), 'id': re.compile('playing_time')})

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        playing_time = pd.read_html(StringIO(str(table)))[0].fillna('-')

        # Drop the first level of the column headers (if it's a multi-level header)
        playing_time.columns = playing_time.columns.droplevel(0)

        return playing_time