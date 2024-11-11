import asyncio
import websockets
import base64
import json
import os
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import userpaths
from loguru import logger

CUR_DIR = Path(__file__).parent
TEMP_DIR = CUR_DIR / "temp"
EXTENSION_DIR = CUR_DIR / "ext"


class ChromeElem:
    def __init__(self, selector: Optional[str] = None):
        self.selector = selector


class Chrome:
    def __init__(
        self,
        init_url: str = "http://example.com",
        left: int = 0,
        top: int = 0,
        width: int = 0,
        height: int = 0,
        block_image: bool = False,
        user_data_dir: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.__init_url = init_url
        self.__left = left
        self.__top = top
        self.__width = width
        self.__height = height
        self.__block_image = block_image
        self.__user_data_dir = user_data_dir
        self.__user_agent = user_agent
        self.__process = None
        self.__websocket_server = None
        self.__client_unit = None

    def __find_port(self) -> int:
        with socket.socket() as s:
            s.bind(("", 0))  # Bind to a free port provided by the host
            return s.getsockname()[1]  # Return the assigned port number

    async def __send_command(self, msg: str, payload: Optional[str] = None) -> Any:
        ret = None
        try:
            if self.__client_unit is not None:
                if payload is not None:
                    await self.__client_unit.send(
                        json.dumps(
                            {
                                "msg": msg,
                                "payload": payload,
                            }
                        )
                    )
                else:
                    await self.__client_unit.send(
                        json.dumps(
                            {
                                "msg": msg,
                            }
                        )
                    )
                resp = await self.__client_unit.recv()
                if resp is not None:
                    js_res = json.loads(resp)["result"]
                    if js_res != "<undefined>":
                        ret = js_res
                else:
                    logger.error("resp is none")
                    await asyncio.sleep(0.5)
            else:
                logger.error("client_unit is none")
        except Exception as ex:
            logger.exception(ex)
        return ret

    async def handle_client(self, websocket, _path):
        self.__client_unit = websocket

    async def start(self):
        chrome_path = ""
        chrome_est_paths = [
            userpaths.get_local_appdata() + "\\Google\\Chrome\\Application\\Chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\Chrome.exe",
            "C:\\Program Files\\Google\\Chrome\\Application\\Chrome.exe",
        ]
        for chrome_est_path in chrome_est_paths:
            if os.path.isfile(chrome_est_path):
                chrome_path = chrome_est_path
                break

        if os.path.isfile(chrome_path):
            # find free port
            port = self.__find_port()

            # start socket server
            self.__websocket_server = await websockets.serve(
                self.handle_client, "localhost", port
            )

            # copy extension to temp folder
            temp_ext_dir = CUR_DIR / f"ext_{datetime.now().timestamp()}"
            shutil.copytree(EXTENSION_DIR, temp_ext_dir, dirs_exist_ok=True)

            # set extension port number
            background_js_path = os.path.join(temp_ext_dir, "background.js")
            with open(background_js_path, "r") as f:
                background_js_content = f.read()
            with open(background_js_path, "w") as f:
                f.write(background_js_content.replace("{PORT}", f"{port}"))

            # remove old profile folder
            if self.__user_data_dir is None:
                self.__user_data_dir = os.path.join(TEMP_DIR, "profile")

            # start chrome
            cmd = [chrome_path]
            cmd.append(f"--user-data-dir={self.__user_data_dir}")
            if os.path.isdir(temp_ext_dir):
                cmd.append(f"--load-extension={temp_ext_dir}")

            if self.__left * self.__top != 0:
                cmd.append(f"--window-position={self.__left},{self.__top}")

            if self.__width * self.__height != 0:
                cmd.append(f"--window-size={self.__width},{self.__height}")

            if self.__block_image:
                cmd.append("--blink-settings=imagesEnabled=false")

            if self.__user_agent is not None:
                cmd.append(f"--user-agent={self.__user_agent}")

            if self.__init_url != "":
                cmd.append(self.__init_url)

            self.__process = subprocess.Popen(cmd)
            logger.info("initializing browser ...")
            await asyncio.sleep(10)
            shutil.rmtree(temp_ext_dir)

            # accept
            logger.info("waiting for client ...")
            while self.__client_unit is None:
                await asyncio.sleep(1)
            logger.info("client connected")
        else:
            logger.error("chrome.exe not found")

    async def quit(self):
        if self.__process is not None:
            self.__process.terminate()
            self.__process = None

        if self.__client_unit is not None:
            await self.__client_unit.close()
            self.__client_unit = None

        if self.__websocket_server is not None:
            self.__websocket_server.close()
            self.__websocket_server = None

        self.__width = 0
        self.__height = 0
        self.__block_image = True

    async def run_script(self, script: str) -> Optional[str]:
        return await self.__send_command("runScript", script)

    async def url(self) -> Optional[str]:
        return await self.run_script("location.href")

    async def goto(
        self,
        url2go: str,
        wait_timeout: float = 30.0,
        wait_elem_selector: Optional[str] = None,
    ) -> bool:
        ret = False
        try:
            timeout = False

            old_url = await self.url()
            if old_url == url2go:
                await self.run_script("location.reload()")
            else:
                await self.run_script(f"location.href='{url2go}'")
                # wait for url changed
                start_tstamp = datetime.now().timestamp()
                while True:
                    if old_url != await self.url():
                        break
                    if datetime.now().timestamp() - start_tstamp > wait_timeout:
                        logger.error("timeout")
                        timeout = True
                        break
                    await asyncio.sleep(0.1)

            # wait for element valid
            if not timeout:
                if wait_elem_selector is not None:
                    start_tstamp = datetime.now().timestamp()
                    while True:
                        wait_elem = self.select_one(wait_elem_selector)
                        if wait_elem is not None:
                            break
                        if datetime.now().timestamp() - start_tstamp > wait_timeout:
                            logger.error("timeout")
                            timeout = True
                            break
                        await asyncio.sleep(0.1)

            if not timeout:
                ret = True
        except Exception as ex:
            logger.exception(ex)
        return ret

    async def cookie(self, domain: str) -> Any:
        return await self.__send_command("getCookie", domain)

    async def clear_cookie(self):
        return await self.__send_command(
            "clearCookie",
        )

    async def head(self) -> Optional[str]:
        return await self.run_script("document.head.outerHTML")

    async def body(self) -> Optional[str]:
        return await self.run_script("document.body.outerHTML")

    async def select(self, selector: str) -> list[ChromeElem]:
        ret = []
        jres = await self.run_script(
            """
function getSelector(elm) {
    if (elm.tagName === 'BODY') return 'BODY';
    const names = [];
    while (elm.parentElement && elm.tagName !== 'BODY') {
        if (elm.id) {
            names.unshift('#' + elm.getAttribute('id'));
            break;
        } else {
            let c = 1, e = elm;
            for (; e.previousElementSibling; e = e.previousElementSibling, c++);
            names.unshift(elm.tagName + ':nth-child(' + c + ')');
        }
        elm = elm.parentElement;
    }
    return names.join('>');
}

var selectors = [];

var elemList = document.querySelectorAll('"""
            + selector
            + """');
for (var elem in elemList) {
    if (elem == elem * 1) {
        var selector = getSelector(elemList[elem]);
        selectors.push(selector);
    }
}

selectors;"""
        )
        if jres is not None:
            for jitem in jres:
                ret.append(ChromeElem(jitem))
        return ret

    def select_one(self, selector: str) -> Optional[ChromeElem]:
        elems = self.select(selector=selector)
        if len(elems) > 0:
            return elems[0]
        else:
            return None

    async def set_value(self, selector: str, value: str):
        b64value = base64.b64encode(value.encode()).decode()
        await self.run_script(
            f"document.querySelector('{selector}').value=atob('{b64value}')"
        )

    async def click(self, selector: str):
        await self.run_script(f"document.querySelector('{selector}').click()")

async def main():
    chrome = Chrome(user_data_dir=os.path.join(TEMP_DIR, "profile"))
    await chrome.start()

    await chrome.goto(url2go="https://google.com", wait_elem_selector="#APjFqb")
    logger.info(str(await chrome.url()))

    await chrome.set_value(selector="#APjFqb", value="chrome")
    await chrome.click(selector="[name=btnK]")

    logger.info("before clear cookie")
    logger.info(chrome.cookie("google.com"))
    await chrome.clear_cookie()
    logger.info("after clear cookie")
    logger.info(chrome.cookie("google.com"))

    input("Press ENTER to exit.")
    await chrome.quit()

if __name__ == "__main__":
    asyncio.run(main())
