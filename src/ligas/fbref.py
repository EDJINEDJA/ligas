import os
import re
import time
import random
from pathlib import Path
from datetime import datetime, timezone

import requests
import threading
import numpy as np
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from typing import Sequence, List, Dict
from functools import wraps

from .exceptions import (
    FbrefRequestException,
    FbrefRateLimitException,
    FbrefInvalidLeagueException,
    FbrefInvalidYearException,
    FbrefInvalidSeasonsException,
    FbrefInvalidTeamException,
)
from .entity_config import SeasonUrls
from .utils import (
    compositions,
    browserHeaders,
    browser,
    save_bin,
    load_bin,
    get_proxy,
    get_cache_directory,
)
from .logger import logger

cuurentYear = datetime.now(tz=timezone.utc).year
validLeagues = [league for league in compositions.keys()]
cache_duration_days = 3


class Fbref:
    wait_time: int = 10
    baseurl: str = "https://fbref.com/"

    # ====================================== wraper for save data ==========================================#
    @staticmethod
    def cache_data(func):
        """
        Decorator to check if the data is already stored in a file.
        If yes, it loads the data. Otherwise, it executes the function, saves the data, and then returns it.
        """

        @wraps(func)
        def wrapper(cls, *args, **kwargs):
            # Create a unique filename based on the function and its arguments
            args_str = "_".join(map(str, args))
            kwargs_str = "_".join(f"{k}={v}" for k, v in kwargs.items())
            file_name = f"{func.__name__}_{args_str}_{kwargs_str}.json"

            # Path to today's directory
            directory = get_cache_directory(cache_duration_days)
            file_path = directory / file_name

            if file_path.exists():
                logger.info(f"Loading data from {file_path}")
                data = load_bin(file_path)
            else:
                logger.info(f"Downloading data and saving to {file_path}")
                data = func(cls, *args, **kwargs)
                save_bin(data, file_path)

            return data

        return wrapper

    # ====================================== request http ==========================================#
    @classmethod
    def _get(cls, url: str) -> requests.Response:
        """
        Sends a GET request to the specified URL and handles potential HTTP errors.

        This method is responsible for sending an HTTP GET request to the specified URL
        (typically an endpoint on the FBref website). It initiates a request using the
        `requests` library, handles rate limiting and certain HTTP errors, and starts
        a waiting thread to manage delays between requests.

        Args:
            url (str): The URL endpoint to which the GET request should be sent. This
                    is usually an endpoint from the FBref website.

        Returns:
            requests.Response: The HTTP response object resulting from the GET request.
                            This object contains the server's response to the HTTP request,
                            including the status code, headers, and content.

        Raises:
            FbrefRateLimitException: If the server responds with a 429 status code,
                                    indicating that the rate limit has been exceeded.
            FbrefRequestException: If the server responds with a 404 or 504 status code,
                                indicating a "Not Found" or "Gateway Timeout" error,
                                respectively.
        """

        # Choose a random browser header if needed
        webBrowser = random.choice(browser)
        header = browserHeaders.get(webBrowser)
        proxy = get_proxy()

        response = requests.get(
            url=url,
            headers=header,
            proxies={"http": proxy, "https:": proxy} if proxy else None,
        )

        wait_thread = threading.Thread(target=cls._wait())
        wait_thread.start()
        wait_thread.join()

        # Check the status code of the response and handle errors
        status = response.status_code

        if status == 429:
            raise FbrefRateLimitException()  # Raised when too many requests are sent

        if status in {404, 504}:
            raise FbrefRequestException()  # Raised for Not Found or Gateway Timeout errors

        return response

    # ====================================== Waiting time to avoid rate limit error ====================#

    @classmethod
    def _wait(cls):
        """
        Implements a waiting period to avoid triggering rate limit errors.

        This method pauses the execution of the program for a specified amount of time,
        defined by `self.wait_time`. It is primarily used to prevent sending too many
        requests in a short period, which could result in rate limiting by the server.

        The method should be invoked before making HTTP requests to ensure compliance
        with the server's request rate policies.

        Args:
            None

        Returns:
            None
        """
        time.sleep(cls.wait_time)

    # ====================================== get current seasons ==========================================#

    @classmethod
    @cache_data
    def get_valid_seasons(cls, league: str) -> SeasonUrls:
        """
        Retrieves all valid seasons and their corresponding URLs for a specified league.

        This method fetches a list of valid seasons (years) and their associated URLs from the FBref website
        for a given football league. It first validates the input league, then sends an HTTP request to fetch
        the season data, and finally parses the response to extract the relevant information.

        Args:
            league (str):
                The league for which to obtain valid seasons. This should be a string representing the league name
                or abbreviation, such as "EPL" for the English Premier League or "La Liga" for the Spanish league.
                To see all valid league options, import `compositions` from the FBref module and examine the keys.

        Returns:
            SeasonUrls:
                A `SeasonUrls` object containing a dictionary where the keys are the season years (as strings) and the values
                are the corresponding URLs (as relative paths). These URLs need to be prefixed with "https://fbref.com"
                to form a complete link.

        Raises:
            TypeError:
                If the `league` argument is not a string.

            FbrefInvalidLeagueException:
                If the provided league is not recognized or is not included in the list of valid leagues.
        """

        # Ensure the league parameter is a string
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        # Ensure the league is valid by checking against the known valid leagues
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Get the URL for the league's history page from the compositions dictionary
        url = compositions[league]["history url"]

        # Send a GET request to the URL and parse the content using BeautifulSoup
        r = cls._get(url)
        soup = BeautifulSoup(r.content, "html.parser")

        # Extract the season years and their corresponding URLs
        seasonUrls = dict(
            [
                (x.text, x.find("a")["href"])
                for x in soup.find_all("th", {"data-stat": True, "class": True})
                if x.find("a") is not None
            ]
        )

        # Return the result wrapped in a SeasonUrls object
        return SeasonUrls(seasonUrls)

    # ====================================== League Infos ==========================================#

    @classmethod
    @cache_data
    def LeagueInfos(cls, year: str, league: str) -> dict:
        """
        Retrieves detailed league information for a given year and league.

        This method fetches specific information about a football league for a particular season (year).
        It validates the league and year inputs, constructs the appropriate URL, sends a request, and then
        parses the HTML content to extract the relevant league details.

        Args:
            year (str):
                The desired season in the format "YYYY-YYYY". The year must not exceed the current year.
                Example: "2023-2024".

            league (str):
                The league name or abbreviation for which to retrieve information. Examples include "EPL"
                for the English Premier League or "La Liga" for the Spanish league.

        Returns:
            dict:
                A dictionary containing various pieces of information about the league. The dictionary includes
                the following keys:

                - 'Governing Country': The country where the league is governed (e.g., 'Spain').
                - 'Level': The level of the league (e.g., 'See League Structure').
                - 'Gender': The gender category of the league (e.g., 'Male').
                - 'Most Goals': The player with the most goals in that season (e.g., 'Robert Lewandowski').
                - 'Most Assists': The player with the most assists in that season (e.g., 'Iker Almena').
                - 'Most Clean Sheets': The goalkeeper with the most clean sheets (e.g., 'Karl Jakob Hein').
                - 'Big 5': A statement if the league is part of the "Big 5" European leagues (e.g., 'View Big 5 European Leagues together').
                - 'league logo': The URL of the league's logo (e.g., 'https://cdn.ssref.net/req/202408161/tlogo/fb/12.png').

        Raises:
            TypeError:
                If the `league` argument is not a string.

            FbrefInvalidLeagueException:
                If the provided league is not recognized or not in the list of valid leagues.

            FbrefInvalidYearException:
                If the provided year is beyond the current year.

        """

        # Validate that the league parameter is a string
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        # Validate that the league is in the list of valid leagues
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Validate that the year does not exceed the current year
        if int(year.split("-")[0]) > int(year.split("-")[-1]):
            raise FbrefInvalidYearException(year, "FBref", cuurentYear)

        # Retrieve the valid seasons for the league and get the URL for the specified year
        urls = cls.get_valid_seasons(league)
        url = urls.seasonUrls[year]

        # Send a GET request to the constructed URL and parse the content
        response = requests.get(os.path.join(cls.baseurl, url[1:]))
        soup = BeautifulSoup(response.content, "html.parser")

        # Extract league information from the HTML content
        r = soup.find("div", attrs={"id": "meta"})

        leagueInfos = {
            p.find("strong").text.strip(":"): (
                p.find("a").text
                if p.find("a") is not None
                else (
                    p.find("span").text
                    if p.find("span") is not None
                    else p.get_text(strip=True)
                    .replace(p.find("strong").text, "")
                    .strip()
                )
            )
            for p in r.find_all("p")
            if p.find("strong") is not None
        }

        # Extract and add the league logo to the dictionary
        leagueInfos["league logo"] = r.find("img", attrs={"class": "teamlogo"})["src"]

        return leagueInfos

    # ====================================== get top scorers ==========================================#

    @classmethod
    @cache_data
    def TopScorers(cls, league: str) -> dict:
        """
        Retrieves the top scorer's statistics for a given league and season.

        This method fetches information about the top goal scorer(s) for a specific football league.
        It validates the league input, retrieves the historical data for that league, and then parses
        the HTML content to extract details about the top scorer, including their name, goals, club, and links to more statistics.

        Args:
            league (str):
                The league identifier for which to obtain the top scorer's statistics.
                Examples include "EPL" for the English Premier League and "La Liga" for Spain's top division.

        Returns:
            dict:
                A dictionary containing details about the top scorers for each season within the given league.
                The structure of the dictionary is as follows:

                - '{league} season {year}': {
                    - 'year': The season year (e.g., '2023-2024').
                    - 'top_scorer': The name of the top scorer for that season.
                    - 'goals': The number of goals scored by the top scorer.
                    - 'stats_link': The direct link to the detailed statistics of the top scorer on the website.
                    - 'club': The club for which the top scorer played during that season.
                }

        Raises:
            ValueError:
                If no data is found for the given league.

            TypeError:
                If the required table is not found on the page.

            FbrefInvalidLeagueException:
                If the provided league is not recognized or is not in the list of valid leagues.
        """

        # Validate that the league parameter is a string
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        # Validate that the league is in the list of valid leagues
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Retrieve the URL for the league's historical data
        url = compositions[league]["history url"]
        r = cls._get(url)
        soup = BeautifulSoup(r.content, "html.parser")

        # Extract top scorer information from the parsed HTML
        top_scorers = {
            f'{league} season {row.find("th", {"data-stat": "year_id"}).text.strip()}': {
                "year": row.find("th", {"data-stat": "year_id"}).text.strip(),
                "top_scorer": row.find("td", {"data-stat": "top_scorers"})
                .find("a")
                .text.strip(),
                "goals": row.find("td", {"data-stat": "top_scorers"})
                .find("span")
                .text.strip(),
                "stats_link": cls.baseurl
                + row.find("td", {"data-stat": "top_scorers"}).find("a")["href"],
                "club": (
                    row.find("td", {"data-stat": "champ"}).text.split("-")[0].strip()
                    if row.find("td", {"data-stat": "champ"})
                    else "Unknown"
                ),
            }
            for row in soup.find_all("tr")
            if row.find("td", {"data-stat": "top_scorers"})
            and row.find("td", {"data-stat": "top_scorers"}).find("a")
        }

        if not top_scorers:
            raise ValueError(f"No top scorer data found for the league: {league}")

        return top_scorers

    # ====================================== Top Scorer ==========================================#

    @classmethod
    @cache_data
    def TopScorer(cls, league: str, currentSeason: str) -> dict:
        """
        Scrapes the top scorer's detailed statistics for a specified league and season.

        This function fetches the top scorer's information for a specific league and season and retrieves detailed statistics
        from the associated player's stats page on FBref.

        Args:
            league (str):
                The league identifier for which to obtain the top scorer's statistics.
                Examples include "EPL" (English Premier League) and "La Liga" (Spain's top division).

            currentSeason (str):
                The season for which to retrieve the top scorer's statistics.
                The format is typically "YYYY-YYYY", e.g., "2023-2024".

        Returns:
            dict:
                A dictionary containing the top scorer's name, number of goals, stats link, club, and detailed statistics.
                The structure of the dictionary is as follows:

                - 'top_scorer': The name of the top scorer.
                - 'goals': The number of goals scored by the top scorer.
                - 'stats_link': The direct link to the detailed statistics of the top scorer.
                - 'club': The club the top scorer played for during that season.
                - 'detailed_stats': A list of dictionaries containing detailed statistics for the top scorer, where each dictionary
                contains:
                    - 'statistic': The name of the statistic.
                    - 'per90': The per90 value for that statistic.
                    - 'percentile': The percentile ranking for that statistic.

        Raises:
            ValueError:
                If no data is found for the given league and season.

            TypeError:
                If the required statistics table is not found on the player's stats page.
        """

        # Fetch the top scorers data for the given league using the TopScorers method
        response = cls.TopScorers(league=league)
        key = f"{league} season {currentSeason}"

        # Check if the season data exists in the fetched response
        if key not in response:
            raise FbrefInvalidSeasonsException(
                currentSeason, "Fbref", league, response.keys()
            )

        # Extract the statistics link for the top scorer
        stats_link = response[key]["stats_link"]

        # Fetch and parse the top scorer's detailed statistics page
        r = cls._get(stats_link)
        soup = BeautifulSoup(r.content, "html.parser")

        # Locate the table containing detailed statistics for forwards (FW)
        table = soup.find("table", {"id": "scout_summary_FW"})
        if not table:
            raise TypeError("The statistics table was not found on the page.")

        # Extract detailed statistics using list comprehension, skipping the header row
        stats = [
            {
                "statistic": row.find("th", {"data-stat": "statistic"}).text.strip(),
                "per90": row.find("td", {"data-stat": "per90"}).text.strip(),
                "percentile": row.find("td", {"data-stat": "percentile"}).text.strip(),
            }
            for row in table.find_all("tr")[1:]  # Skip the header row
        ]

        # Return a structured dictionary containing the top scorer's details and statistics
        return {
            "top_scorer": response[key]["top_scorer"],
            "goals": response[key]["goals"],
            "stats_link": stats_link,
            "club": response[key]["club"],
            "detailed_stats": stats,
        }

    # ====================================== Fixtures ==========================================#

    @classmethod
    @cache_data
    def Fixtures(cls, year: str, league: str) -> dict:
        """
        Retrieves match fixtures, including match reports, head-to-head details, and various statistics for a specific league and season.

        Args:
            year (str): The season for which to retrieve fixtures (e.g., "2023-2024").
            league (str): The league identifier (e.g., "EPL", "La Liga").

        Returns:
            dict: A dictionary containing match fixtures, where each fixture includes:
                - 'match link': The URL linking to the match report or head-to-head details.
                - 'match-date': The date of the match.
                - 'data-venue-time': The time and venue details.
                - 'referee': The referee officiating the match.
                - 'stats': A nested dictionary containing:
                    - 'home': Statistics for the home team.
                        - 'xg': The expected goals (xG) for the home team.
                        - 'link team stats': URL linking to the home team's stats page.
                    - 'away': Statistics for the away team.
                        - 'xg': The expected goals (xG) for the away team.
                        - 'link team stats': URL linking to the away team's stats page.
                - 'Attendance': The match attendance.
                - 'score': A nested dictionary containing:
                    - 'home': The score for the home team.
                    - 'away': The score for the away team.
                - 'venue': The venue where the match was played.
                - 'teams': A nested dictionary containing:
                    - 'home': The name of the home team.
                    - 'away': The name of the away team.

        Raises:
            TypeError: If the `league` is not a string.
            FbrefInvalidLeagueException: If the `league` is not a valid league.
            FbrefInvalidYearException: If the specified `year` exceeds the current year.
        """

        # Ensure the league is a valid string
        if not isinstance(league, str):
            raise TypeError("`league` must be a str eg: Champions League.")

        # Check if the league is valid
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Check if the specified year is valid
        if int(year.split("-")[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, "FBref", cuurentYear)

        # Retrieve the valid seasons and construct the fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]

        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Fetch the fixtures page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")

        # Locate the table containing the fixtures
        table = soup.find("table")

        # Extract data from each row of matches using list comprehension
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and any(
                    term in row.find("td", {"data-stat": "match_report"}).text
                    for term in ["Head-to-Head", "Match Report"]
                )
            ]
        }

        return fixtures

    # ====================================== MatchReport ==========================================#

    @classmethod
    @cache_data
    def MatchReport(cls, year: str, league: str) -> dict:
        """
        Retrieves detailed match report data for a specific league and season.

        Args:
            year (str): The season year (e.g., "2023-2024") for which to retrieve match reports.
            league (str): The league for which match reports are to be retrieved (e.g., "Premier League").

        Returns:
            dict: A dictionary containing match report data with the following structure:
                - match link (str): The URL to the match report.
                - match-date (str): The date of the match.
                - data-venue-time (str): The time and venue details of the match.
                - referee (str): The name of the referee officiating the match.
                - stats (dict): A nested dictionary containing team statistics:
                    - home (dict): Home team statistics:
                        - xg (str): Expected goals (xG) for the home team.
                        - link team stats (str): URL linking to the home team's stats page.
                    - away (dict): Away team statistics:
                        - xg (str): Expected goals (xG) for the away team.
                        - link team stats (str): URL linking to the away team's stats page.
                - Attendance (str): The attendance figure for the match.
                - score (dict): A dictionary containing the final score:
                    - home (str): Final score for the home team.
                    - away (str): Final score for the away team.
                - venue (str): The name of the venue where the match was played.
                - teams (dict): A dictionary containing the team names:
                    - home (str): Name of the home team.
                    - away (str): Name of the away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        # Validate league against allowed leagues
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Retrieve and parse the page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and "Match Report" in row.find("td", {"data-stat": "match_report"}).text
            ]
        }

        return fixtures

    # ====================================== Head Head ==========================================#

    @classmethod
    @cache_data
    def HeadHead(cls, year: str, league: str) -> dict:
        """
        Retrieves head-to-head match data for a specific league and season.

        Args:
            year (str): The season year (e.g., "2023-2024") for which to retrieve head-to-head match data.
            league (str): The league for which head-to-head data is to be retrieved (e.g., "Premier League").

        Returns:
            dict: A dictionary containing head-to-head match data with the following structure:
                - match link (str): The URL to the match report.
                - match-date (str): The date of the match.
                - data-venue-time (str): The time and venue details of the match.
                - referee (str): The name of the referee officiating the match.
                - stats (dict): A nested dictionary containing team statistics:
                    - home (dict): Home team statistics:
                        - link team stats (str): URL linking to the home team's stats page.
                    - away (dict): Away team statistics:
                        - link team stats (str): URL linking to the away team's stats page.
                - score (dict): A dictionary containing the final score:
                    - home (str): Final score for the home team.
                    - away (str): Final score for the away team.
                - Attendance (str): The attendance figure for the match.
                - venue (str): The name of the venue where the match was played.
                - teams (dict): A dictionary containing the team names:
                    - home (str): Name of the home team.
                    - away (str): Name of the away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        # Validate league against allowed leagues
        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Retrieve and parse the page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            )
                        },
                        "away": {
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            )
                        },
                    },
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and "Head-to-Head" in row.find("td", {"data-stat": "match_report"}).text
            ]
        }

        return fixtures

    # ====================================== Matches ==========================================#

    @classmethod
    @cache_data
    def Matches(cls, date: str, year: str, league: str) -> dict:
        """
        Retrieves fixtures for a specific date from a given league and season.

        Args:
            date (str): The date of the matches to retrieve (e.g., "2024-08-20").
            year (str): The season year (e.g., "2023-2024") for which to retrieve match data.
            league (str): The league for which to retrieve match data (e.g., "Premier League").

        Returns:
            dict: A dictionary containing match data with the following structure:
                - match link (str): The URL to the match report.
                - match-date (str): The date of the match.
                - data-venue-time (str): The time and venue details of the match.
                - referee (str): The name of the referee officiating the match.
                - stats (dict): A nested dictionary containing team statistics:
                    - home (dict): Home team statistics:
                        - xg (str): Expected goals for the home team.
                        - link team stats (str): URL linking to the home team's stats page.
                    - away (dict): Away team statistics:
                        - xg (str): Expected goals for the away team.
                        - link team stats (str): URL linking to the away team's stats page.
                - score (dict): A dictionary containing the final score:
                    - home (str): Final score for the home team.
                    - away (str): Final score for the away team.
                - Attendance (str): The attendance figure for the match.
                - venue (str): The name of the venue where the match was played.
                - teams (dict): A dictionary containing the team names:
                    - home (str): Name of the home team.
                    - away (str): Name of the away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Retrieve and parse the page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and any(
                    term in row.find("td", {"data-stat": "match_report"}).text
                    for term in ["Head-to-Head", "Match Report"]
                )
                and row.find("td", {"data-stat": "date"})
                and row.find("td", {"data-stat": "date"}).text.strip() == date
            ]
        }

        return fixtures

    # ====================================== Fixture team ==========================================#

    @classmethod
    @cache_data
    def FixturesByTeam(cls, team: str, year: str, league: str) -> dict:
        """
        Retrieves fixtures for a specific team from a given league and season.

        Args:
            team (str): The name of the team for which to retrieve fixtures (e.g., "Liverpool").
            year (str): The season year (e.g., "2023-2024") for which to retrieve match data.
            league (str): The league for which to retrieve match data (e.g., "Premier League").

        Returns:
            dict: A dictionary containing fixture details with the following structure:
                - match link (str): URL to the match report.
                - match-date (str): Date of the match.
                - data-venue-time (str): Time and venue details.
                - referee (str): Referee’s name.
                - stats (dict): A nested dictionary with team statistics:
                    - home (dict): Home team statistics:
                        - xg (str): Expected goals for the home team.
                        - link team stats (str): URL linking to the home team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                    - away (dict): Away team statistics:
                        - xg (str): Expected goals for the away team.
                        - link team stats (str): URL linking to the away team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                - score (dict): Match score:
                    - home (str): Home team’s score.
                    - away (str): Away team’s score.
                - Attendance (str): Attendance figure.
                - venue (str): Venue of the match.
                - teams (dict): Team names:
                    - home (str): Home team.
                    - away (str): Away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Fetch and parse the fixtures page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "home_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "away_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and any(
                    term in row.find("td", {"data-stat": "match_report"}).text
                    for term in ["Head-to-Head", "Match Report"]
                )
                # Filter matches where the team is either the home or away team
                if (
                    (
                        row.find("td", {"data-stat": "home_team"})
                        and row.find("td", {"data-stat": "home_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                    or (
                        row.find("td", {"data-stat": "away_team"})
                        and row.find("td", {"data-stat": "away_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                )
            ]
        }

        return fixtures

    # ====================================== Match report By team ==========================================#

    @classmethod
    @cache_data
    def MatchReportByTeam(cls, team: str, year: str, league: str) -> dict:
        """
        Retrieves match reports for a specific team from a given league and season.

        Args:
            team (str): The name of the team for which to retrieve match reports (e.g., "Liverpool").
            year (str): The season year (e.g., "2023-2024") for which to retrieve match data.
            league (str): The league for which to retrieve match data (e.g., "Premier League").

        Returns:
            dict: A dictionary containing match report details with the following structure:
                - match link (str): URL to the match report.
                - match-date (str): Date of the match.
                - data-venue-time (str): Time and venue details.
                - referee (str): Referee’s name.
                - stats (dict): A nested dictionary with team statistics:
                    - home (dict): Home team statistics:
                        - xg (str): Expected goals for the home team.
                        - link team stats (str): URL linking to the home team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                        - players (dict): Player statistics from the `Players` method.
                    - away (dict): Away team statistics:
                        - xg (str): Expected goals for the away team.
                        - link team stats (str): URL linking to the away team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                        - players (dict): Player statistics from the `Players` method.
                - score (dict): Match score:
                    - home (str): Home team’s score.
                    - away (str): Away team’s score.
                - Attendance (str): Attendance figure.
                - venue (str): Venue of the match.
                - teams (dict): Team names:
                    - home (str): Home team.
                    - away (str): Away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        if int(year.split("-")[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, "FBref", cuurentYear)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Fetch and parse the fixtures page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "home_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "away_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and "Match Report" in row.find("td", {"data-stat": "match_report"}).text
                # Filter matches where the target team is either the home or away team
                if (
                    (
                        row.find("td", {"data-stat": "home_team"})
                        and row.find("td", {"data-stat": "home_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                    or (
                        row.find("td", {"data-stat": "away_team"})
                        and row.find("td", {"data-stat": "away_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                )
            ]
        }

        return fixtures

    # ====================================== Head Head By Team ==========================================#

    @classmethod
    @cache_data
    def HeadHeadByTeam(cls, team: str, year: str, league: str) -> dict:
        """
        Retrieves head-to-head match reports for a specific team from a given league and season.

        Args:
            team (str): The name of the team for which to retrieve head-to-head match reports (e.g., "Liverpool").
            year (str): The season year (e.g., "2023-2024") for which to retrieve match data.
            league (str): The league for which to retrieve match data (e.g., "Premier League").

        Returns:
            dict: A dictionary containing head-to-head match details with the following structure:
                - match link (str): URL to the match report.
                - match-date (str): Date of the match.
                - data-venue-time (str): Time and venue details.
                - referee (str): Referee’s name.
                - stats (dict): A nested dictionary with team statistics:
                    - home (dict): Home team statistics:
                        - xg (str): Expected goals for the home team.
                        - link team stats (str): URL linking to the home team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                        - players (dict): Player statistics from the `Players` method.
                    - away (dict): Away team statistics:
                        - xg (str): Expected goals for the away team.
                        - link team stats (str): URL linking to the away team’s stats page.
                        - team stats (dict): Team stats from the `TeamInfos` method.
                        - players (dict): Player statistics from the `Players` method.
                - score (dict): Match score:
                    - home (str): Home team’s score.
                    - away (str): Away team’s score.
                - Attendance (str): Attendance figure.
                - venue (str): Venue of the match.
                - teams (dict): Team names:
                    - home (str): Home team.
                    - away (str): Away team.
        """

        # Validate input types and values
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        if int(year.split("-")[-1]) > int(cuurentYear):
            raise FbrefInvalidYearException(year, "FBref", cuurentYear)

        # Construct the season link and fixtures URL
        urls = cls.get_valid_seasons(league)
        season_link = urls.seasonUrls[year]
        fixtures_url = cls.baseurl + "/".join(
            season_link.split("/")[:-1]
            + [
                "schedule",
                "-".join(season_link.split("/")[-1].split("-")[:-1])
                + "-Scores-and-Fixtures",
            ]
        )

        # Fetch and parse the fixtures page
        r = cls._get(fixtures_url)
        soup = BeautifulSoup(r.content, "html.parser")
        table = soup.find("table")

        # Extract data from each row of matches
        fixtures = {
            league
            + "-Scores-and-Fixture": [
                {
                    "match link": (
                        cls.baseurl
                        + row.find("td", {"data-stat": "date"}).find("a")["href"]
                        if row.find("td", {"data-stat": "date"})
                        and row.find("td", {"data-stat": "date"}).find("a")
                        else np.nan
                    ),
                    "match-date": (
                        row.find("td", {"data-stat": "date"}).text.strip()
                        if row.find("td", {"data-stat": "date"})
                        else np.nan
                    ),
                    "data-venue-time": (
                        row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )["data-venue-time"]
                        if row.find("td", {"data-stat": "start_time"})
                        and row.find("td", {"data-stat": "start_time"}).find(
                            "span", {"data-venue-time": True}
                        )
                        else np.nan
                    ),
                    "referee": (
                        row.find("td", {"data-stat": "referee"}).text.strip()
                        if row.find("td", {"data-stat": "referee"})
                        else np.nan
                    ),
                    "stats": {
                        "home": {
                            "xg": (
                                row.find("td", {"data-stat": "home_xg"}).text.strip()
                                if row.find("td", {"data-stat": "home_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "home_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "home_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "home_team"})
                                and row.find("td", {"data-stat": "home_team"}).find("a")
                                else np.nan
                            ),
                        },
                        "away": {
                            "xg": (
                                row.find("td", {"data-stat": "away_xg"}).text.strip()
                                if row.find("td", {"data-stat": "away_xg"})
                                else np.nan
                            ),
                            "link team stats": (
                                cls.baseurl
                                + row.find("td", {"data-stat": "away_team"}).find("a")[
                                    "href"
                                ]
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                            "team stats": (
                                cls.TeamInfos(
                                    row.find("td", {"data-stat": "away_team"})
                                    .find("a")
                                    .text.strip(),
                                    league,
                                )
                                if row.find("td", {"data-stat": "away_team"})
                                and row.find("td", {"data-stat": "away_team"}).find("a")
                                else np.nan
                            ),
                        },
                    },
                    "score": {
                        "home": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[0]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "score"})
                            .find("a")
                            .text.strip()
                            .split("–")[1]
                            .strip()
                            if row.find("td", {"data-stat": "score"})
                            and row.find("td", {"data-stat": "score"}).find("a")
                            else np.nan
                        ),
                    },
                    "Attendance": (
                        row.find("td", {"data-stat": "attendance"}).text.strip()
                        if row.find("td", {"data-stat": "attendance"})
                        else np.nan
                    ),
                    "venue": (
                        row.find("td", {"data-stat": "venue"}).text.strip()
                        if row.find("td", {"data-stat": "venue"})
                        else np.nan
                    ),
                    "teams": {
                        "home": (
                            row.find("td", {"data-stat": "home_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "home_team"})
                            and row.find("td", {"data-stat": "home_team"}).find("a")
                            else np.nan
                        ),
                        "away": (
                            row.find("td", {"data-stat": "away_team"})
                            .find("a")
                            .text.strip()
                            if row.find("td", {"data-stat": "away_team"})
                            and row.find("td", {"data-stat": "away_team"}).find("a")
                            else np.nan
                        ),
                    },
                }
                for row in table.find_all("tr")
                if row.find("td", {"data-stat": "match_report"})
                and "Head-to-Head" in row.find("td", {"data-stat": "match_report"}).text
                # Filter matches where the target team is either the home or away team
                if (
                    (
                        row.find("td", {"data-stat": "home_team"})
                        and row.find("td", {"data-stat": "home_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                    or (
                        row.find("td", {"data-stat": "away_team"})
                        and row.find("td", {"data-stat": "away_team"})
                        .find("a")
                        .text.strip()
                        == team
                    )
                )
            ]
        }

        return fixtures

    # ====================================== TeamsInfo ================================================#

    @classmethod
    @cache_data
    def TeamsInfos(cls, league: str) -> dict:
        """
        Retrieves team information for a specified league, including current and previous season stats, and team details.

        Args:
            league (str): The name of the league (e.g., "Champions League").

        Returns:
            dict: A dictionary where each key is a team name, and the value is another dictionary containing:
                - 'rank': The team's rank in the current season (starting from 1).
                - 'logo': The URL of the team's logo.
                - 'games': The number of games played.
                - 'url': The URL to the team's stats page.
                - 'current stats': A dictionary with current season statistics:
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

        # Validate input type and league
        if not isinstance(league, str):
            raise TypeError('`league` must be a str, e.g., "Champions League".')

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        urls = cls.get_valid_seasons(league)

        # Retrieve current season team stats
        current_season_url = urls.seasonUrls[f"{cuurentYear}-{int(cuurentYear)+1}"]
        response = cls._get(os.path.join(cls.baseurl, current_season_url[1:]))
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", class_="stats_table")

        current_team_stats = {
            (
                row.find_all("td")[0].find("a").get_text(strip=True)
                if row.find_all("td")[0].find("a")
                else ""
            ): {
                "rank": index + 1,
                "logo": (
                    row.find_all("td")[0].find("img")["src"]
                    if row.find_all("td")[0].find("img")
                    else np.nan
                ),
                "url": row.find_all("td")[0].find("a")["href"],
                "games": row.find_all("td")[1].get_text(strip=True),
                "current stats": {
                    "wins": row.find_all("td")[2].get_text(strip=True),
                    "draws": row.find_all("td")[3].get_text(strip=True),
                    "losses": row.find_all("td")[4].get_text(strip=True),
                    "goals_for": row.find_all("td")[5].get_text(strip=True),
                    "goals_against": row.find_all("td")[6].get_text(strip=True),
                    "goal_diff": row.find_all("td")[7].get_text(strip=True),
                    "points": row.find_all("td")[8].get_text(strip=True),
                    "points_avg": row.find_all("td")[9].get_text(strip=True),
                    "xg_for": row.find_all("td")[10].get_text(strip=True),
                    "xg_against": row.find_all("td")[11].get_text(strip=True),
                    "xg_diff": row.find_all("td")[12].get_text(strip=True),
                    "xg_diff_per90": row.find_all("td")[13].get_text(strip=True),
                    "last_result": row.find_all("td")[14].get_text(strip=True),
                    "top_scorer": row.find_all("td")[16].get_text(strip=True),
                    "top_keeper": row.find_all("td")[17].get_text(strip=True),
                },
            }
            for index, row in enumerate(table.tbody.find_all("tr"))
            if row.find_all("td")  # Ensures only rows with data are processed
        }

        # Retrieve previous season team stats
        previous_season_url = urls.seasonUrls[f"{int(cuurentYear)-1}-{cuurentYear}"]

        response = cls._get(os.path.join(cls.baseurl, previous_season_url[1:]))
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", class_="stats_table")

        # Collecting data into a dictionary with team names as keys and including rank
        previous_team_stats = {
            (
                row.find_all("td")[0].find("a").get_text(strip=True)
                if row.find_all("td")[0].find("a")
                else ""
            ): {
                "rank": index + 1,
                "logo": row.find_all("td")[0].find("img")["src"],
                "url": row.find_all("td")[0].find("a")["href"],
                "games": row.find_all("td")[1].get_text(strip=True),
                "wins": row.find_all("td")[2].get_text(strip=True),
                "draws": row.find_all("td")[3].get_text(strip=True),
                "losses": row.find_all("td")[4].get_text(strip=True),
                "goals_for": row.find_all("td")[5].get_text(strip=True),
                "goals_against": row.find_all("td")[6].get_text(strip=True),
                "goal_diff": row.find_all("td")[7].get_text(strip=True),
                "points": row.find_all("td")[8].get_text(strip=True),
                "points_avg": row.find_all("td")[9].get_text(strip=True),
                "xg_for": row.find_all("td")[10].get_text(strip=True),
                "xg_against": row.find_all("td")[11].get_text(strip=True),
                "xg_diff": row.find_all("td")[12].get_text(strip=True),
                "xg_diff_per90": row.find_all("td")[13].get_text(strip=True),
                "last_result": row.find_all("td")[14].get_text(strip=True),
                "top_scorer": row.find_all("td")[16].get_text(strip=True),
                "top_keeper": row.find_all("td")[17].get_text(strip=True),
            }
            for index, row in enumerate(table.tbody.find_all("tr"))
            if row.find_all("td")  # Ensures only rows with data are processed
        }

        # Combine current and previous stats
        for team in current_team_stats.keys():
            if team in previous_team_stats:
                current_team_stats[team]["previous stats"] = previous_team_stats[team]
            else:
                current_team_stats[team]["previous stats"] = {}

        return current_team_stats

    # ====================================== Teams Info ================================================#

    @classmethod
    @cache_data
    def TeamInfos(cls, team: str, league: str) -> dict:
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
            raise TypeError("`league` must be a str eg: Champions League .")

        if league not in validLeagues:
            raise FbrefInvalidLeagueException(league, "FBref", validLeagues)

        teamsInfo = cls.TeamsInfos(league)

        validTeams = teamsInfo.keys()

        if team not in validTeams:
            raise FbrefInvalidTeamException(
                cuurentYear, "FBref", league, team, list(validTeams)
            )

        teamInfos = teamsInfo[team]

        # Adding additional stats current season
        team_url = os.path.join(cls.baseurl, teamInfos["url"][1:])

        response = cls._get(team_url)

        soup = BeautifulSoup(response.content, "html.parser")

        stats_categories = {
            "players": {"re": "players", "header": 1},
            "Scores & Fixtures": {"re": "for", "header": 0},
            "keeper": {"re": "keeper", "header": 1},
            "passing": {"re": "passing", "header": 1},
            "shooting": {"re": "shooting", "header": 1},
            "passing type": {"re": "passing_type", "header": 1},
            "goal shot creation": {"re": "gca", "header": 1},
            "defensive actions": {"re": "defense", "header": 1},
            "possession": {"re": "possession", "header": 1},
            "playing time": {"re": "playing_time", "header": 1},
        }

        for cat in stats_categories.keys():
            if cat != "players":
                teamInfos["current stats"][cat] = cls._categorystats(
                    soup, stats_categories[cat]["re"], stats_categories[cat]["header"]
                )
            else:
                teamInfos["current stats"]["players"] = cls._players(soup)

        # Adding additional stats previous season
        team_url = (
            os.path.join(cls.baseurl, teamInfos["previous stats"]["url"][1:])
            if teamInfos["previous stats"]
            else os.path.join(
                *os.path.join(cls.baseurl, teamInfos["url"][1:]).split("/")[:-1],
                f"{int(cuurentYear)-1}-{cuurentYear}",
                os.path.join(cls.baseurl, teamInfos["url"][1:]).split("/")[-1],
            ).replace("https:/", "https://", 1)
        )

        response = cls._get(team_url)

        soup = BeautifulSoup(response.content, "html.parser")

        for cat in stats_categories.keys():
            if cat != "players":
                teamInfos["previous stats"][cat] = cls._categorystats(
                    soup, stats_categories[cat]["re"], stats_categories[cat]["header"]
                )
            else:
                teamInfos["previous stats"]["players"] = cls._players(soup)

        return teamInfos

    # ====================================== _players =========================================#

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
        table = soup.find("table", {"class": "stats_table", "id": "stats_standard_12"})

        # Extract player names and their corresponding URLs
        data = {
            row.find("th", {"data-stat": "player"})
            .text: row.find("th", {"data-stat": "player"})
            .find("a")["href"]
            for row in table.tbody.find_all("tr")
        }

        # Convert the player URLs to a DataFrame
        players_urls = pd.DataFrame(list(data.items()), columns=["Player", "Url"])

        # Read the HTML table into a DataFrame
        players = pd.read_html(StringIO(str(table)), header=1)[0].fillna("-")

        # Merge the players DataFrame with the URLs DataFrame
        players = players.merge(players_urls, how="left", on="Player")

        return players

    # ====================================== _categorystats =========================================#

    @staticmethod
    def _categorystats(soup: BeautifulSoup, category: str, header: int) -> pd.DataFrame:
        """
        Extracts and returns a DataFrame containing statistics from a specified table on a webpage.

        This method locates a table based on the provided category and reads it into a pandas DataFrame.
        It uses the specified header row index to correctly interpret the table's column headers and
        fills any missing values with a placeholder ('-').

        Args:
            soup (BeautifulSoup): A BeautifulSoup object containing the HTML of the webpage with the table.
            category (str): The identifier for the table's `id` attribute, which determines which table to extract.
            header (int): The row index to use as the header for the DataFrame.

        Returns:
            pd.DataFrame: A DataFrame containing the statistics from the specified table, with any missing values
                        filled with '-'.

        Example:
            # Example usage
            df = _categorystats(soup, 'passing', 0)
        """
        # Locate the table containing statistics
        table = soup.find(
            "table", {"class": re.compile("stats"), "id": re.compile(f"{category}")}
        )

        # Convert the HTML table into a DataFrame and fill any missing values with '-'
        stats = pd.read_html(StringIO(str(table)), header=header)[0].fillna("-")

        return stats
