from dataclasses import dataclass


@dataclass
class Head2Head():
    date : str

@dataclass
class SeasonUrls():
    seasonUrls : dict

@dataclass
class CurrentSeasonUrls():
    url : str

@dataclass
class TopScorers():
    seasonScorers : dict
   
@dataclass
class BestScorer():
    name : str
    