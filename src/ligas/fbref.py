from pathlib import Path
import os
import random

import requests
import threading
import time 

from .exceptions import FbrefRequestException, FbrefRateLimitException
from .entity_config import Head2Head
from .utils import compositions
from .utils import browserHeaders
from .utils import browser



class fbref():
    def __init__(self, wait_time :int =5) -> None:
        self.wait_time = wait_time
        webBrowser = random.choice(browser)
        self.header = browserHeaders.get(webBrowser)

    def _get(self, url : str) -> requests.Response:

        """
            call _get create an instance of requests
            Args:
                url (str): is the the endpoint of fbref website 
            Returns:
                object (requests.Response): return the response
        """
       
        
        response = requests.get(url=url, headers=self.header)
        wait_thread = threading.Thread(target=self._wait)
        wait_thread.start()

        status = response.status_code

        if status == 429:
            raise FbrefRateLimitException()
 
        if status in set([404, 504]) :
            raise  FbrefRequestException()
        
        return response
    
    def _wait(self):
        """
            Defining a waiting time for separate requests
        """
        time.sleep(self.wait_time)


