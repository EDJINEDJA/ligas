import unittest
import requests
import pytest
from typing import Sequence, List, Dict
import pandas as pd

from ligas import Fbref
from ligas.entity_config import SeasonUrls

class testLigasfbrefApi(unittest.TestCase):
    def setUp(self) -> None:
        
        super().setUp()
    
    def test_get_module(self):
        """
            Testing _get module from fbref
        """

        response = Fbref._get(url = 'https://fbref.com/en/matches')

        self.assertIsInstance(response , requests.Response)
    
    def test_invalid_key_word_of_get_current_seasons(self):
        with pytest.raises(Exception) as e_info:
            response = Fbref.get_valid_seasons(league = "La-ligas")

        
    def test_invalid_key_word_of_get_current_seasons(self):

        response = Fbref.get_valid_seasons(league = "La-ligas")

        self.assertIsInstance(response , SeasonUrls)

    def test_get_current_seasons(self):

        response = Fbref.get_valid_seasons(league = 'Serie A')

        self.assertIsInstance(response , SeasonUrls)
    
    def test_get_top_scorers(self):

        response = Fbref.TopScorers(league = 'Serie A')

        self.assertIsInstance(response , dict)

    def test_topScorer(self):

        response = Fbref.TopScorer(league = 'Serie A',  currentSeason =  '2023-2024')

        self.assertIsInstance(response , dict)
    
    def test_Fixtures(self):

        response = Fbref.Fixtures(year = '2023-2024', league = 'Serie A')
        
        self.assertIsInstance(response , dict)
    
    def test_teamsinfo(self):
        response = Fbref.TeamsInfo(league = 'Serie A')

        self.assertIsInstance(response , dict)

    def test_teaminfos(self):
        response = Fbref.TeamInfos(team ='Real Madrid', league = 'La Liga')

        self.assertIsInstance(response , dict)
    
    def test_matchreport(self):
        response = Fbref.MatchReport('2024-2025', 'Serie A')

        self.assertIsInstance(response , dict)

    def test_headhead(self):
        response = Fbref.HeadHead('2024-2025', 'Serie A')

        self.assertIsInstance(response , dict)

    def test_fixturesbyteam(self):
        response = Fbref.FixturesByTeam('inter','2024-2025', 'Serie A')

        self.assertIsInstance(response , dict)
    
    def test_matches(self):
        response = Fbref.Matches('2024-08-20','2024-2025', 'Serie A')

        self.assertIsInstance(response , dict)
    

if __name__ == "__main__":
    unittest.main()