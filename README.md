<p align="center" style="overflow: hidden; height: 130px;">
  <img src="https://github.com/EDJINEDJA/ligas/blob/main/docs/images/ligasv1.png" alt="ligas logo" style="clip-path: inset(0 0 20px 0);">
</p>
<p align="center">
    <a href="https://github.com/EDJINEDJA/ligas/blob/main/LICENSE" alt="Licence">
        <img src="https://img.shields.io/badge/license-MIT-yellow.svg" />
    </a> 
    <a href="https://github.com/EDJINEDJA/ligas/commits/main" alt="Commits">
        <img src="https://img.shields.io/github/last-commit/EDJINEDJA/ligas/main" />
    </a>
    <a href="https://github.com/EDJINEDJA/ligas" alt="Activity">
        <img src="https://img.shields.io/badge/contributions-welcome-orange.svg" />
    </a>
    <a href="https://github.com/EDJINEDJA/ligas" alt="Web Status">
        <img src="https://img.shields.io/website?down_color=red&down_message=down&up_color=success&up_message=up&url=http%3A%2F%2Fmatthaythornthwaite.pythonanywhere.com%2F" />
    </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/ligas/">
    <img src="https://img.shields.io/pypi/v/ligas.svg", alt="pypi version badge"></img>
  </a>
  <a href="https://ligas.readthedocs.io/en/latest/">
    <img src="https://readthedocs.org/projects/nrc4d/badge/?version=latest" alt="documentation status badge"/></img>
  </a>
  <a href="https://pypi.org/project/ligas/">
    <img src="https://img.shields.io/pypi/dm/ligas.svg" alt="monthly pypi downloads badge"/></img>
  </a>
</p>

<p align="center">
  <a href=https://discord.gg/GTHc77sK>
    <img src="https://dcbadge.limes.pink/api/server/GTHc77sK" alt="Discord invite link badge"></img>
  </a>
  <a href="https://buymeacoffee.com/automatica">
    <img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee badge"></img>
  </a>
</p>

## Table of Contents

<!--ts-->
* [Aims and Objectives](#Aims-and-Objectives)
* [Usage](#Usage)
* [Soccer data](#Soccer-data)
<!--te-->

## Aims and Objectives

Introducing `ligas`, a Python package designed to revolutionize access to soccer data. No more tedious football api, copy-pasting, or manual data entry—`ligas` makes it effortless for anyone with basic Python knowledge to tap into a world of soccer statistics. By streamlining the process, `ligas` allows you to focus on analysis and insights, whether you're a data scientist, analyst, or simply a soccer enthusiast. With `ligas`, the complex task of gathering and managing soccer data becomes simple, empowering you to explore and enjoy the beautiful game like never before.


## Usage
#### Install

To install ligas, run
```bash
$ pip install ligas
```

## FBref
Data have been scraped from the following sources:
* [FBref](https://fbref.com/fr/)

eg:
```bash
$ pip install ligas
$ from ligas import Fbref
$ Fbref.TeamInfos(team: str, league: str)
```
Fbref contain the following modules

| **Name**                                 | **Description**                        |
|------------------------------------------|----------------------------------------|
| `TeamInfos(team: str, league: str) -> dict` | Class or function to get information about a specific team.|
| `TeamsInfo(league: str) -> dict`            | Retrieves information about multiple teams.|
| `HeadHeadByTeam(team: str, year: str, league: str) -> dict`| Retrieves head-to-head statistics by team.|
| `MatchReportByTeam(team: str, year: str, league: str)`     | Generates a match report for a specific team.|
| `FixturesByTeam(team: str, year: str, league: str)`        | Lists the fixtures for a given team.|
| `Matches(date: str, year: str, league: str)`               | Provides general information about matches.|
| `HeadHead(year: str, league: str) -> dict`                 | Retrieves head-to-head statistics between two teams.|
| `MatchReport(year: str, league: str) -> dict`              | Generates a detailed match report.|
| `Fixtures(year: str, league: str) -> dict`                 | Lists fixtures for a league or team.|
| `TopScorer(league: str, currentSeason: str) -> dict` | Retrieves the top scorer of a league for the current season.|
| `TopScorers( league: str) -> dict`   | Retrieves the top scorers of a league.|
| `LeagueInfos(year: str, league: str) -> dict` | Gets information about a specific league for a given year.|
| `get_valid_seasons(league: str) -> SeasonUrls` | Retrieves the valid seasons for a given league.

