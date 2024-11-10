import os
import time
from pathlib import Path
from random import randint

import urllib3
from loguru import logger

from lib.chrome import Chrome

urllib3.disable_warnings()

COOKIE = ""

CUR_DIR = str(Path(__file__).parent.absolute())
TEMP_DIR = os.path.join(CUR_DIR, "temp")
OUTPUT_DIR = os.path.join(CUR_DIR, "output")
DONE_MARKER_NAME = "done"


def work():
    try:
        chrome = None
        user_data_dir = os.path.join(TEMP_DIR, "profile")

        chrome = Chrome(
            width=800 + randint(0, 200),
            height=600 + randint(0, 100),
            block_image=True,
            user_data_dir=user_data_dir,
        )
        chrome.start()
        chrome.goto("google.com")
        time.sleep(5)
        chrome.run_script("window.scrollTo(0, document.body.scrollHeight);")

    except Exception as ex:
        logger.exception(ex)
    finally:
        chrome.quit()


def main():
    work()


if __name__ == "__main__":
    main()
