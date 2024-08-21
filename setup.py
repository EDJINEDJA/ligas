from setuptools import setup, find_packages
from setuptools.command.install import install

import codecs
import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))

class CustomInstallCommand(install):
    def run(self):
        # calling welcome message
        os.system(f'python {os.path.join(BASEDIR, "src", "ligas", "install_hook.py")} display_welcome')
        super().run()

with codecs.open(os.path.join(BASEDIR, "README.md"), encoding="utf-8") as fh:
    long_description = fh.read()

VERSION = "0.1.0"
SRC_REPO = "ligas"
DESCRIPTION = 'Streaming video data via networks'
LONG_DESCRIPTION = 'A package that allows to build simple streams of video, audio and camera data.'
REPO_NAME = "mlproject-MLflow"
AUTHOR_USER_NAME = "edjinedja"
AUTHOR_EMAIL = "automaticall06@gmail.com"

setup(
    name=SRC_REPO,
    version=VERSION,
    author=AUTHOR_USER_NAME,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Bug Tracker": f"https://github.com/{AUTHOR_USER_NAME}/{REPO_NAME}/issues",
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    cmdclass={'install': CustomInstallCommand},
    install_requires=[
        'requests', 'beautifulsoup4', 'lxml' ,'pyYAML', 'python-box', 'tqdm', 'ensure', 'numpy', 'pandas', 'joblib', 'pyfiglet'
    ],
    keywords=['python', 'soccer', 'data', 'ligues', 'api', 'football'],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
