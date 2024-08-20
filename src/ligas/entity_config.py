from dataclasses import dataclass


@dataclass
class Head2Head():
    date : str

@dataclass
class SeasonUrls():
    season_urls : dict

@dataclass
class BestScorer():
    name : str
    