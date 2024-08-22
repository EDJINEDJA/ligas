import pyfiglet
from ligas import logger

def display_welcome():
    welcome_msg = pyfiglet.figlet_format("Bienvenue")
    logger.info(welcome_msg)

if __name__=="__main__":
    display_welcome()