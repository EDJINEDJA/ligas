import unittest
import requests

from ligas import fbref

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


if __name__ == "__main__":
    unittest.main()