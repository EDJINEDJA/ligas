from setuptools import setup, find_packages
import codecs
import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(BASEDIR, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

VERSION = "0.1.0"
SRC_REPO = "ligas"
DESCRIPTION = 'Streaming video data via networks'
LONG_DESCRIPTION = 'A package that allows to build simple streams of video, audio and camera data.'
REPO_NAME = "mlproject-MLflow"
AUTHOR_USER_NAME = "edjinedja"
SRC_REPO = "ligas"
AUTHOR_EMAIL = "<automaticall06@gmail.com>"


setup(
    name= SRC_REPO,
    version= VERSION,
    author= AUTHOR_USER_NAME,
    author_email= AUTHOR_EMAIL,
    description= DESCRIPTION,
    long_description= LONG_DESCRIPTION,
    long_description_content_type= "text/markdown",
    project_urls={
        "Bug Tracker": f"https://github.com/{AUTHOR_USER_NAME}/{REPO_NAME}/issues",
    },
    package_dir={"": "ligas"},
    packages=find_packages(where="ligas"),


    install_requires=['requests', 'beautifulsoup4'],
    keywords=['python', 'soccer', 'data', 'ligues', 'api', 'football'],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ],
   
)