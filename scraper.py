import asyncio
import os
from pathlib import Path
from random import randint

from loguru import logger

from lib.chrome import Chrome

CUR_DIR = str(Path(__file__).parent.absolute())
TEMP_DIR = os.path.join(CUR_DIR, "temp")
OUTPUT_DIR = os.path.join(CUR_DIR, "output")
DONE_MARKER_NAME = "done"


async def work():
    try:
        chrome = None
        user_data_dir = os.path.join(TEMP_DIR, "profile")

        chrome = Chrome(
            width=800 + randint(0, 200),
            height=600 + randint(0, 100),
            block_image=True,
            user_data_dir=user_data_dir,
        )
        await chrome.start()
        await chrome.goto("google.com")
        await asyncio.sleep(5)
        await chrome.run_script("window.scrollTo(0, document.body.scrollHeight);")

    except Exception as ex:
        logger.exception(ex)
    finally:
        await chrome.quit()

async def main():
    await work()


if __name__ == "__main__":
    asyncio.run(main())
