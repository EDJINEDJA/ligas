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
        return (
            "Rate limit error: FBref returned a 429 status, Too Many Requests."
            + "for more detail please see https://www.sports-reference.com/bot-traffic.html."
        )


class FbrefInvalidLeagueException(Exception):
    """
    Raised this exception when invalid league is provided by the client
    """

    def __init__(self, league: str, module: str, leagues: Sequence[str]) -> None:
        self.league = league
        self.leagues = leagues
        self.module = module
        super().__init__()

    def __str__(self) -> str:

        return (
            f"InvalidLeague: {self.league} not exist for {self.module} , please find the right league in "
            + f"{self.leagues}"
        )


class FbrefInvalidYearException(Exception):
    """
    Raised this exception when invalid year is provided by the client
    """

    def __init__(self, year: str, module: str, currentYear: Sequence[str]) -> None:
        self.year = year
        self.module = module
        self.currentYear = currentYear

        super().__init__()

    def __str__(self) -> str:

        return (
            f"InvalidYear: the last year in {self.year} must be greater that {self.currentYear} "
            + f"when using  {self.module} module, please choose right year eg: 2023-2024"
        )


class FbrefInvalidSeasonsException(Exception):
    """
    Raised this exception when year or season provided by the client are bad
    """

    def __init__(self, year: str, module: str, league: str, Saesons: list) -> None:
        self.year = year
        self.league = league
        self.module = module
        self.Saesons = Saesons

        super().__init__()

    def __str__(self) -> str:

        return (
            f"InvalidSeason:  {self.year} season {self.league}   is not in  {self.Saesons}"
            + f"when using  {self.module} module, please choose right key which is in {self.Saesons}"
        )


class FbrefInvalidTeamException(Exception):
    """
    Raised this exception when year or season provided by the client are bad
    """

    def __init__(
        self, year: str, module: str, league: str, team: str, teams: list
    ) -> None:
        self.year = year
        self.league = league
        self.module = module
        self.team = team
        self.teams = teams

        super().__init__()

    def __str__(self) -> str:

        return (
            f"InvalidTeam:  {self.year} season--{self.team}  is not valid "
            + f"when using  {self.module} module, please choose right team which is in {self.teams}"
        )
