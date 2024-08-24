import json
import os
import shutil
from pathlib import Path
from  datetime import datetime, timezone, timedelta
from typing import Any
import joblib
import yaml
import time
from box import ConfigBox
from box.exceptions import BoxValueError
from ensure import ensure_annotations
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
import random
from io import StringIO
from .logger import logger


@ensure_annotations
def read_yaml(path_to_yaml: Path) -> ConfigBox:
    """reads yaml file and returns

    Args:
        path_to_yaml (str): path like input

    Raises:
        ValueError: if yaml file is empty
        e: empty file

    Returns:
        ConfigBox: ConfigBox type
    """
    try:
        with open(path_to_yaml) as yaml_file:
            content = yaml.safe_load(yaml_file)
            logger.info(f"yaml file: {path_to_yaml} loaded successfully")
            return ConfigBox(content)
    except BoxValueError:
        raise ValueError("yaml file is empty")
    except Exception as e:
        raise e


@ensure_annotations
def create_directories(path_to_directories: list, verbose=True):
    """create list of directories

    Args:
        path_to_directories (list): list of path of directories
        ignore_log (bool, optional): ignore if multiple dirs is to be created. Defaults to False.
    """
    for path in path_to_directories:
        os.makedirs(path, exist_ok=True)
        if verbose:
            logger.info(f"created directory at: {path}")


@ensure_annotations
def save_json(path: Path, data: dict):
    """save json data

    Args:
        path (Path): path to json file
        data (dict): data to be saved in json file
    """
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

    logger.info(f"json file saved at: {path}")


@ensure_annotations
def load_json(path: Path) -> ConfigBox:
    """load json files data

    Args:
        path (Path): path to json file

    Returns:
        ConfigBox: data as class attributes instead of dict
    """
    with open(path) as f:
        content = json.load(f)

    logger.info(f"json file loaded succesfully from: {path}")
    return ConfigBox(content)

def save_bin(data , path):
    """save binary file

    Args:
        data (Any): data to be saved as binary
        path (Path): path to binary file
    """
    joblib.dump(value=data, filename=path)
    logger.info(f"binary file saved at: {path}")

def load_bin(path):
    """load binary data

    Args:
        path (Path): path to binary file

    Returns:
        Any: object stored in the file
    """
    data = joblib.load(path)
    logger.info(f"binary file loaded from: {path}")
    return data

@ensure_annotations
def get_cache_directory(cache_delta_days : int) -> Path:
    """Returns the path of the directory for today's date.
        Removes directories older than `cache_delta_days`.
    
    Args:
        cache_delta_days (int): cache duration days

    Returns:
         path (Path): path of the directory
    """
    today_date = datetime.now().strftime("%Y-%m-%d")
    # The root directory where subdirectories are created
    base_directory = Path(".") 
    directory = base_directory / os.path.join("ligas/metadata/",today_date)

    # Remove directories older than `cache_duration_days`
    expiration_date = datetime.now() - timedelta(days= cache_delta_days)
    for folder in base_directory.iterdir():
        if folder.is_dir():
            try:
                folder_date = datetime.strptime(folder.name, "%Y-%m-%d")
                if folder_date < expiration_date:
                    logger.info(f"Deleting expired directory: {folder}")
                    for file in folder.iterdir():
                        # Delete each file in the directory
                        file.unlink()  
                    # Delete the directory
                    folder.rmdir()
            except ValueError:
                continue  
             
    # Create today's directory if it doesn't exist
    if not directory.exists():
        directory.mkdir(parents=True)
        logger.info(f"Directory '{today_date}' has been created.")
    else:
        logger.info(f"Directory '{today_date}' already exists.")

    return directory

@ensure_annotations
def get_size(path: Path) -> str:
    """get size in KB

    Args:
        path (Path): path of the file

    Returns:
        str: size in KB
    """
    size_in_kb = round(os.path.getsize(path) / 1024)
    return f"~ {size_in_kb} KB"


@ensure_annotations
def copy(source: str, destination: str, verbose=True):
    """copy file from source to destination

       wget https://raw.githubusercontent.com/github/gitignore/main/Python.gitignore -O .gitignore


    Args:
        path (Path): path of the file
    """

    shutil.copy(source, destination)
    if verbose:
        logger.info(
            f"file successfuly copied from {os.path.dirname(source)} to {os.path.dirname(destination)}"
        )


# =============================================== Proxies =================================================================


def get_proxy__() -> dict[str, str]:
    """Return a public proxy."""
    # list of free proxy apis
    # protocols: http, https, socks4 and socks5
    list_of_proxy_content = [
        "https://proxylist.geonode.com/api/proxy-list?sort_by=lastChecked&sort_type=desc",
    ]

    # extracting json data from this list of proxies
    full_proxy_list = []
    for proxy_url in list_of_proxy_content:
        proxy_json = json.loads(requests.get(proxy_url).text)["data"]
        full_proxy_list.extend(proxy_json)

        if not full_proxy_list:
            logger.info("There are currently no proxies available. Exiting...")
            return {}
        logger.info(f"Found {len(full_proxy_list)} proxy servers. Checking...")

    # creating proxy dict
    final_proxy_list = []
    for proxy in full_proxy_list:
        protocol = proxy["protocols"][0]
        ip_ = proxy["ip"]
        port = proxy["port"]

        proxy = {
            "https": protocol + "://" + ip_ + ":" + port,
            "http": protocol + "://" + ip_ + ":" + port,
        }

        final_proxy_list.append(proxy)

    # trying proxy
    for proxy in final_proxy_list:
        if check_proxy__(proxy):
            return proxy

    logger.info("There are currently no proxies available. Exiting...")
    return None


def check_proxy__(proxy: dict) -> bool:
    """Check if proxy is working."""
    try:
        r0 = requests.get("https://ipinfo.io/json", proxies=proxy, timeout=120)
        return r0.status_code == 200
    except Exception as error:
        logger.error(f"BAD PROXY: Reason: {error!s}\n")
        return False


# =============================================== free proxy list net =================================================================


def get_proxy_():
    try:
        response = requests.get("https://free-proxy-list.net/")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table")
        proxiesDf = pd.read_html(StringIO(str(table)))[0].fillna("-")
        proxies = list(proxiesDf["IP Address"] + ":" + proxiesDf["Port"].astype(str))
        proxies = sorted(proxies, key=lambda x: random.random())

        logger.error(f"Wait seeking proxy ...")
        for proxy in proxies:
            if check_proxy_(proxy):
                return proxy

        logger.info("There are currently no working proxies available. Exiting...")
        return None
    except requests.RequestException as e:
        logger.error(f"Error accessing free-proxy-list.net: {e}. Using your own proxy.")
        return None

def check_proxy_(proxy) -> bool:
    """Check if the proxy is working."""
    try:
        r0 = requests.get(
            "https://fbref.com/en/matches",
            proxies={"http": proxy, "https": proxy},
            timeout=20,
        )
        return r0.status_code == 200
    except requests.RequestException as error:
        logger.error(f"BAD PROXY: {proxy} - Reason: {error}")
        return False
# =============================================== free proxy list net max wait time =================================================================

    
def get_proxy(max_wait_time=10):
    """
    Try to obtain a proxy from free-proxy-list.net for a given time.
    If no proxy is found after max_wait_time seconds, returns None.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        try:
            response = requests.get("https://free-proxy-list.net/")
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            table = soup.find("table")
            proxiesDf = pd.read_html(StringIO(str(table)))[0].fillna("-")
            proxies = list(proxiesDf["IP Address"] + ":" + proxiesDf["Port"].astype(str))
            proxies = sorted(proxies, key=lambda x: random.random())

            logger.info("Searching for a working proxy...")
            for proxy in proxies:
                if check_proxy(proxy):
                    logger.info(f"Proxy found: {proxy}")
                    return proxy

            logger.info("No working proxies found, retrying in a few seconds...")
            
        except requests.RequestException as e:
            logger.error(f"Error accessing free-proxy-list.net: {e}")

    logger.info("No proxies found within the time limit. Using the default proxy.")
    return None

def check_proxy(proxy) -> bool:
    """Check if the proxy is working."""
    try:
        r0 = requests.get(
            "https://fbref.com/en/matches",
            proxies={"http": proxy, "https": proxy},
            timeout=20,
        )
        return r0.status_code == 200
    except requests.RequestException as error:
        return False


# =============================================== Compositions =======================================================

compositions = {
    # Men's club international cups
    "Copa Libertadores": {
        "history url": "https://fbref.com/en/comps/14/history/Copa-Libertadores-Seasons",
        "finders": ["Copa-Libertadores"],
    },
    "Champions League": {
        "history url": "https://fbref.com/en/comps/8/history/Champions-League-Seasons",
        "finders": ["European-Cup", "Champions-League"],
    },
    "Europa League": {
        "history url": "https://fbref.com/en/comps/19/history/Europa-League-Seasons",
        "finders": ["UEFA-Cup", "Europa-League"],
    },
    "Europa Conference League": {
        "history url": "https://fbref.com/en/comps/882/history/Europa-Conference-League-Seasons",
        "finders": ["Europa-Conference-League"],
    },
    # Men's national team competitions
    "World Cup": {
        "history url": "https://fbref.com/en/comps/1/history/World-Cup-Seasons",
        "finders": ["World-Cup"],
    },
    "Copa America": {
        "history url": "https://fbref.com/en/comps/685/history/Copa-America-Seasons",
        "finders": ["Copa-America"],
    },
    "Euros": {
        "history url": "https://fbref.com/en/comps/676/history/European-Championship-Seasons",
        "finders": ["UEFA-Euro", "European-Championship"],
    },
    # Men's big 5
    "Big 5 combined": {
        "history url": "https://fbref.com/en/comps/Big5/history/Big-5-European-Leagues-Seasons",
        "finders": ["Big-5-European-Leagues"],
    },
    "EPL": {
        "history url": "https://fbref.com/en/comps/9/history/Premier-League-Seasons",
        "finders": ["Premier-League", "First-Division"],
    },
    "Ligue 1": {
        "history url": "https://fbref.com/en/comps/13/history/Ligue-1-Seasons",
        "finders": ["Ligue-1", "Division-1"],
    },
    "Bundesliga": {
        "history url": "https://fbref.com/en/comps/20/history/Bundesliga-Seasons",
        "finders": ["Bundesliga"],
    },
    "Serie A": {
        "history url": "https://fbref.com/en/comps/11/history/Serie-A-Seasons",
        "finders": ["Serie-A"],
    },
    "La Liga": {
        "history url": "https://fbref.com/en/comps/12/history/La-Liga-Seasons",
        "finders": ["La-Liga"],
    },
    # Men's domestic leagues - 1st tier
    "MLS": {
        "history url": "https://fbref.com/en/comps/22/history/Major-League-Soccer-Seasons",
        "finders": ["Major-League-Soccer"],
    },
    "Brazilian Serie A": {
        "history url": "https://fbref.com/en/comps/24/history/Serie-A-Seasons",
        "finders": ["Serie-A"],
    },
    "Eredivisie": {
        "history url": "https://fbref.com/en/comps/23/history/Eredivisie-Seasons",
        "finders": ["Eredivisie"],
    },
    "Liga MX": {
        "history url": "https://fbref.com/en/comps/31/history/Liga-MX-Seasons",
        "finders": ["Primera-Division", "Liga-MX"],
    },
    "Primeira Liga": {
        "history url": "https://fbref.com/en/comps/32/history/Primeira-Liga-Seasons",
        "finders": ["Primeira-Liga"],
    },
    "Belgian Pro League": {
        "history url": "https://fbref.com/en/comps/37/history/Belgian-Pro-League-Seasons",
        "finders": ["Belgian-Pro-League", "Belgian-First-Division"],
    },
    "Argentina Liga Profesional": {
        "history url": "https://fbref.com/en/comps/21/history/Primera-Division-Seasons",
        "finders": ["Primera-Division"],
    },
    # Men's domestic league - 2nd tier
    "EFL Championship": {
        "history url": "https://fbref.com/en/comps/10/history/Championship-Seasons",
        "finders": ["First-Division", "Championship"],
    },
    "La Liga 2": {
        "history url": "https://fbref.com/en/comps/17/history/Segunda-Division-Seasons",
        "finders": ["Segunda-Division"],
    },
    "2. Bundesliga": {
        "history url": "https://fbref.com/en/comps/33/history/2-Bundesliga-Seasons",
        "finders": ["2-Bundesliga"],
    },
    "Ligue 2": {
        "history url": "https://fbref.com/en/comps/60/history/Ligue-2-Seasons",
        "finders": ["Ligue-2"],
    },
    "Serie B": {
        "history url": "https://fbref.com/en/comps/18/history/Serie-B-Seasons",
        "finders": ["Serie-B"],
    },
    # Women's internation club competitions
    "Womens Champions League": {
        "history url": "https://fbref.com/en/comps/181/history/Champions-League-Seasons",
        "finders": ["Champions-League"],
    },
    # Women's national team competitions
    "Womens World Cup": {
        "history url": "https://fbref.com/en/comps/106/history/Womens-World-Cup-Seasons",
        "finders": ["Womens-World-Cup"],
    },
    "Womens Euros": {
        "history url": "https://fbref.com/en/comps/162/history/UEFA-Womens-Euro-Seasons",
        "finders": ["UEFA-Womens-Euro"],
    },
    # Women's domestic leagues
    "NWSL": {
        "history url": "https://fbref.com/en/comps/182/history/NWSL-Seasons",
        "finders": ["NWSL"],
    },
    "A-League Women": {
        "history url": "https://fbref.com/en/comps/196/history/A-League-Women-Seasons",
        "finders": ["A-League-Women", "W-League"],
    },
    "WSL": {
        "history url": "https://fbref.com/en/comps/189/history/Womens-Super-League-Seasons",
        "finders": ["Womens-Super-League"],
    },
    "D1 Feminine": {
        "history url": "https://fbref.com/en/comps/193/history/Division-1-Feminine-Seasons",
        "finders": ["Division-1-Feminine"],
    },
    "Womens Bundesliga": {
        "history url": "https://fbref.com/en/comps/183/history/Frauen-Bundesliga-Seasons",
        "finders": ["Frauen-Bundesliga"],
    },
    "Womens Serie A": {
        "history url": "https://fbref.com/en/comps/208/history/Serie-A-Seasons",
        "finders": ["Serie-A"],
    },
    "Liga F": {
        "history url": "https://fbref.com/en/comps/230/history/Liga-F-Seasons",
        "finders": ["Liga-F"],
    },
    # Women's domestic cups
    "NWSL Challenge Cup": {
        "history url": "https://fbref.com/en/comps/881/history/NWSL-Challenge-Cup-Seasons",
        "finders": ["NWSL-Challenge-Cup"],
    },
    "NWSL Fall Series": {
        "history url": "https://fbref.com/en/comps/884/history/NWSL-Fall-Series-Seasons",
        "finders": ["NWSL-Fall-Series"],
    },
}

# =========================================Browse headers==========================================
browserHeaders = {
    "Chrome": {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
    },
    "Edge": {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-GB,en;q=0.9,en-US;q=0.8",
        "cache-control": "max-age=0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36 Edg/95.0.1020.44",
    },
    "Firefox": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0",
    },
    "IE": {
        "Accept": "text/html, application/xhtml+xml, image/jxr, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-GB",
        "Connection": "Keep-Alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
    },
}

# =======================================Headers keys==============================================================
browser = ["Chrome", "Edge", "Firefox", "IE", "Other"]
