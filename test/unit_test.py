import unittest
import requests
import pytest
from ligas import fbref
from ligas.entity_config import Head2Head, SeasonUrls, BestScorer, TopScorers
from typing import Sequence, List, Dict

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
    
<<<<<<< HEAD
    def test_invalid_key_word_of_get_current_seasons(self):
        with pytest.raises(Exception) as e_info:
            response = self.api.get_valid_seasons(league = "La-ligas")

        
    def test_get_current_seasons(self):
=======
    # def test_invalid_key_word_of_get_current_seasons(self):

    #     response = self.api.get_valid_seasons(league = "La-ligas")

    #     self.assertIsInstance(response , SeasonUrls)

    # def test_get_current_seasons(self):
>>>>>>> 2ec45bade752633b0a984cb09bdf64fc5fa10bcc

    #     response = self.api.get_valid_seasons(league = 'Serie A')

    #     self.assertIsInstance(response , SeasonUrls)
    
    def test_get_top_scorers(self):

        response = self.api.get_top_scorers(league = 'Serie A')

        self.assertIsInstance(response , dict)

    def test_topScorer(self):

        response = self.api.topScorer(league = 'Serie A',  currentSeason =  '2023-2024')

        self.assertIsInstance(response , dict)

    def test_get_top_scorers(self):

        response = self.api.TopScorers(league = 'Serie A')

        self.assertIsInstance(response , dict)

    def test_topScorer(self):

        response = self.api.TopScorer(league = 'Serie A',  currentSeason =  '2023-2024')

        self.assertIsInstance(response , dict)

if __name__ == "__main__":
    unittest.main()