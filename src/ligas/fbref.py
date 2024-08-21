from pathlib import Path
import os
import random
from datetime import datetime

from typing import Sequence, List, Dict
import requests
from bs4 import BeautifulSoup
import threading
import time 
import numpy as np

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

        cuurentYear = datetime.now().year
        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
        
        season_link = self.get_valid_seasons(league=league)[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

      # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
        {
            'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
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

        cuurentYear = datetime.now().year
        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
            
        season_link = self.get_valid_seasons(league=league)[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
            {
                'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
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

    #====================================== HeadHead ==========================================#
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

        cuurentYear = datetime.now().year
        if int(year.split('-')[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, 'FBref', cuurentYear)
                
        season_link = self.get_valid_seasons(league=league)[year]

        fixtures_url = self.baseurl + '/'.join(season_link.split('/')[:-1] + ['schedule', '-'.join(season_link.split('/')[-1].split('-')[:-1]) + '-Scores-and-Fixtures'])

        r = self._get(fixtures_url)

        soup = BeautifulSoup(r.content, 'html.parser')

        table = soup.find('table')

        # Extract data from each row of matches using list comprehension
        fixtures = {league + "-Scores-and-Fixture": [
                {
                    'match link': self.baseurl + row.find('td', {'data-stat': 'date'}).find('a')['href'] if row.find('td', {'data-stat': 'date'}) and row.find('td', {'data-stat': 'date'}).find('a') else np.nan,
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
    #====================================== Match ==========================================#

    def Match(self, date : str, year : str , league : str) -> dict:
        """Fixtures containing match of the date
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
        return NotImplemented
 
    #====================================== FixturesByClub ==========================================#
    def FixturesByClub(self, club : str, year : str , league : str) -> dict:
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
        return NotImplemented
    #====================================== TeamsInfo ================================================#
    # def TeamsInfo(self,  league : str) -> dict:
    #     """
    #     Retrieves team information for a specified club and league, including current and previous season stats, previous and next matches, and seasonal trajectories.

    #     Args:
    #         club (str): The name of the club.
    #         league (str): The name of the league (e.g., "Champions League").

    #     Returns:
    #         dict: A dictionary where each key is a team name, and the value is another dictionary containing:
    #             - 'rank': The team's rank in the current season (starting from 1).
    #             - 'logo': The URL of the team's logo.
    #             - 'games': The number of games played.
    #             - 'current stats': A nested dictionary with the following current season statistics:
    #                 - 'wins': Number of wins.
    #                 - 'draws': Number of draws.
    #                 - 'losses': Number of losses.
    #                 - 'goals_for': Number of goals scored.
    #                 - 'goals_against': Number of goals conceded.
    #                 - 'goal_diff': Goal difference.
    #                 - 'points': Total points.
    #                 - 'points_avg': Average points per game.
    #                 - 'xg_for': Expected goals for.
    #                 - 'xg_against': Expected goals against.
    #                 - 'xg_diff': Expected goals difference.
    #                 - 'xg_diff_per90': Expected goals difference per 90 minutes.
    #                 - 'last_result': Result of the last match.
    #                 - 'top_scorer': Top scorer of the team.
    #                 - 'top_keeper': Top goalkeeper of the team.
    #             - 'previous stats': A dictionary of statistics from the previous season if available, otherwise an empty dictionary.

    #     Raises:
    #         TypeError: If `league` is not a string.
    #         FbrefInvalidLeagueException: If `league` is not a valid league name.
    #     """

    #     if not isinstance(league, str):
    #        raise  TypeError('`league` must be a str eg: Champions League .')
        
    #     if league not in validLeagues:
    #         raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

        
    #     urls = self.get_valid_seasons(league)

    #     #---------------------getting Cuurent Team Stats--------------------------------------
      
    #     url = urls.seasonUrls[f"{int(cuurentYear)-1}-{cuurentYear}"]
    #     response = requests.get(os.path.join(self.baseurl,url[1:]))
    #     soup = BeautifulSoup(response.content, 'html.parser')

    #     #  Looking for the table with the classes 'wikitable' and 'sortable'
    #     table = soup.find('table', class_='stats_table')

    #     # Collecting data into a dictionary with team names as keys and including rank
    #     cuurentTeamStats = {
    #         row.find_all('td')[0].find("a").get_text(strip=True): {
    #             "rank": index + 1,
    #             "logo": row.find_all('td')[0].find('img')['src'],
    #             "url": row.find_all('td')[0].find("a")['href'],
    #             "games": int(row.find_all('td')[1].get_text(strip=True)),
    #             "current stats" : {"wins": int(row.find_all('td')[2].get_text(strip=True)),
    #                 "draws": int(row.find_all('td')[3].get_text(strip=True)),
    #                 "losses": int(row.find_all('td')[4].get_text(strip=True)),
    #                 "goals_for": int(row.find_all('td')[5].get_text(strip=True)),
    #                 "goals_against": int(row.find_all('td')[6].get_text(strip=True)),
    #                 "goal_diff": row.find_all('td')[7].get_text(strip=True),
    #                 "points": int(row.find_all('td')[8].get_text(strip=True)),
    #                 "points_avg": float(row.find_all('td')[9].get_text(strip=True)),
    #                 "xg_for": float(row.find_all('td')[10].get_text(strip=True)),
    #                 "xg_against": float(row.find_all('td')[11].get_text(strip=True)),
    #                 "xg_diff": row.find_all('td')[12].get_text(strip=True),
    #                 "xg_diff_per90": row.find_all('td')[13].get_text(strip=True),
    #                 "last_result": row.find_all('td')[14].get_text(strip=True),
    #                 "top_scorer": row.find_all('td')[16].get_text(strip=True),
    #                 "top_keeper": row.find_all('td')[17].get_text(strip=True)}
    #         }
    #         for index, row in enumerate(table.tbody.find_all('tr'))
    #         if row.find_all('td')  # Ensures only rows with data are processed
    #     }



    #     #--------------------- getting previous Year Team Stats--------------------------------------
      
        
    #     url = urls.seasonUrls[f"{cuurentYear}-{int(cuurentYear)+1}"]
        
    #     response = requests.get(os.path.join(self.baseurl,url[1:]))
    #     soup = BeautifulSoup(response.content, 'html.parser')

    #     # Collecting data into a dictionary with team names as keys and including rank
    #     previousTeamStats = {
    #         row.find_all('td')[0].find("a").get_text(strip=True): {
    #             "rank": index + 1,
    #             "logo": row.find_all('td')[0].find('img')['src'],
    #             "url": row.find_all('td')[0].find("a")['href'],
    #             "games": int(row.find_all('td')[1].get_text(strip=True)),
    #             "wins": int(row.find_all('td')[2].get_text(strip=True)),
    #             "draws": int(row.find_all('td')[3].get_text(strip=True)),
    #             "losses": int(row.find_all('td')[4].get_text(strip=True)),
    #             "goals_for": int(row.find_all('td')[5].get_text(strip=True)),
    #             "goals_against": int(row.find_all('td')[6].get_text(strip=True)),
    #             "goal_diff": row.find_all('td')[7].get_text(strip=True),
    #             "points": int(row.find_all('td')[8].get_text(strip=True)),
    #             "points_avg": float(row.find_all('td')[9].get_text(strip=True)),
    #             "xg_for": float(row.find_all('td')[10].get_text(strip=True)),
    #             "xg_against": float(row.find_all('td')[11].get_text(strip=True)),
    #             "xg_diff": row.find_all('td')[12].get_text(strip=True),
    #             "xg_diff_per90": row.find_all('td')[13].get_text(strip=True),
    #             "last_result": row.find_all('td')[14].get_text(strip=True),
    #             "top_scorer": row.find_all('td')[16].get_text(strip=True), 
    #             "top_keeper": row.find_all('td')[17].get_text(strip=True),
    #         }
    #         for index, row in enumerate(table.tbody.find_all('tr'))
    #         if row.find_all('td')  # Ensures only rows with data are processed
    #     }

    #     #------------Create a new dictionary with updated stats including previous stats----------
    #     teamStats = cuurentTeamStats
    #     for team in cuurentTeamStats.keys():
    #         if team in previousTeamStats.keys():
    #             cuurentTeamStats[team]["previous stats"] = previousTeamStats[team]
        
    #     return teamStats
    
    # #====================================== TeamsInfo ================================================#
    # def TeamInfos(self,  team: str, league : str) -> dict:
    #     """
    #     Retrieves detailed information for a specific team within a specified league.

    #     Args:
    #         team (str): The name of the team whose information is being requested.
    #         league (str): The name of the league where the team plays (e.g., "Champions League").

    #     Returns:
    #         dict: A dictionary containing detailed information about the specified team. The structure of the dictionary includes:
    #             - 'rank': The team's rank in the current season (starting from 1).
    #             - 'logo': The URL of the team's logo.
    #             - 'games': The number of games played.
    #             - 'current stats': A nested dictionary with current season statistics:
    #                 - 'wins': Number of wins.
    #                 - 'draws': Number of draws.
    #                 - 'losses': Number of losses.
    #                 - 'goals_for': Number of goals scored.
    #                 - 'goals_against': Number of goals conceded.
    #                 - 'goal_diff': Goal difference.
    #                 - 'points': Total points.
    #                 - 'points_avg': Average points per game.
    #                 - 'xg_for': Expected goals for.
    #                 - 'xg_against': Expected goals against.
    #                 - 'xg_diff': Expected goals difference.
    #                 - 'xg_diff_per90': Expected goals difference per 90 minutes.
    #                 - 'last_result': Result of the last match.
    #                 - 'top_scorer': Top scorer of the team.
    #                 - 'top_keeper': Top goalkeeper of the team.
    #             - 'previous stats': A dictionary of statistics from the previous season if available, otherwise an empty dictionary.

    #     Raises:
    #         TypeError: If `league` is not a string.
    #         FbrefInvalidLeagueException: If `league` is not a valid league name.
    #         FbrefInvalidTeamException: If `team` is not a valid team name in the specified league.

    #     """
    #     if not isinstance(league, str):
    #        raise  TypeError('`league` must be a str eg: Champions League .')
        
    #     if league not in validLeagues:
    #         raise FbrefInvalidLeagueException(league, 'FBref', validLeagues)

    #     TeamsInfo = self.TeamsInfo(league)

    #     validTeams = TeamsInfo.keys()

    #     if team not in validTeams:
    #         raise  FbrefInvalidTeamException(cuurentYear,'FBref', league,  team , list(validTeams))
     
    #     return TeamsInfo[team]


    
    # #====================================== FixturesByClub ==========================================#
    # def Players(self, club : str, year : str , league : str) -> dict:
    #     """Players ststs by club , season and league
    #         Args:
    #             year (str)
    #             league (str)
    #         Returns:
    #     """

        
