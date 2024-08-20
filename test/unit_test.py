import unittest
import requests

from ligas import fbref
from ligas.entity_config import Head2Head, SeasonUrls, BestScorer

class testLigasfbrefApi(unittest.TestCase):
    def setUp(self) -> None:
        #initializing the fbref api
        self.api = fbref()
        super().setUp()
    
    def test_get_module(self):
        """
            Testing _get module from fbref
        """

        response = self.api._get(url = 'https://fbref.com/en/matches/32bb9a67/Athletic-Club-Getafe-August-15-2024-La-Liga')

        self.assertIsInstance(response , requests.Response)
    
    def test_invalid_key_word_of_get_current_seasons(self):

        response = self.api.get_valid_seasons(league = "La-ligas")

        self.assertIsInstance(response , SeasonUrls)

    def test_get_current_seasons(self):

        response = self.api.get_valid_seasons(league = 'Serie A')

        self.assertIsInstance(response , SeasonUrls)
    
    def test_YearLeagueInfos(self):

        response = self.api.LeagueInfos('2023-2026', 'La Liga')

        self.assertIsInstance(response , dict)
    
    def test_LeagueInfos(self):

        response = self.api.LeagueInfos('2023-2024', 'La Liga')

        self.assertIsInstance(response , dict)

if __name__ == "__main__":
    unittest.main()