const fs = require('fs');
const path = require('path');
const os = require('os');
const net = require('net');
const { execFile } = require('child_process');
const WebSocket = require('ws');
const TEMP_DIR = os.tmpdir();
const EXTENSION_DIR = path.join(__dirname, 'ext');


class Chrome {
  constructor(initUrl = "http://example.com", left = 0, top = 0, width = 0, height = 0, blockImage = false, userDataDir = null, userAgent = null) {
    this._initUrl = initUrl;
    this._left = left;
    this._top = top;
    this._width = width;
    this._height = height;
    this._blockImage = blockImage;
    this._userDataDir = userDataDir;
    this._userAgent = userAgent;
    this._process = null;
    this._clientUnit = null;
  }

  _findPort() {
    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.listen(0, () => {
        const port = server.address().port;
        server.close(() => resolve(port));
      });
      server.on('error', reject);
    });
  }

  _sendCommand(msg, payload = null) {
    return new Promise((resolve, reject) => {
      if (this._clientUnit) {
        const message = JSON.stringify({ msg, payload });
        this._clientUnit.send(message, err => {
          if (err) return reject(err);
          this._clientUnit.on('message', data => {
            const response = JSON.parse(data).result;
            resolve(response !== "<undefined>" ? response : null);
          });
        });
      } else {
        reject(new Error("Client unit is not connected"));
      }
    });
  }

  async start() {
    const chromePaths = [
      path.join(process.env.LOCALAPPDATA, "Google\\Chrome\\Application\\Chrome.exe"),
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\Chrome.exe",
      "C:\\Program Files\\Google\\Chrome\\Application\\Chrome.exe"
    ];
    const chromePath = chromePaths.find(fs.existsSync);
    if (!chromePath) throw new Error("chrome.exe not found");

    const port = await this._findPort();
    const wsServer = new WebSocket.Server({ port });
    const extDir = path.join(TEMP_DIR, `ext_${Date.now()}`);
    fs.cpSync(EXTENSION_DIR, extDir, { recursive: true });

    const backgroundJsPath = path.join(extDir, "background.js");
    const backgroundJsContent = fs.readFileSync(backgroundJsPath, 'utf8');
    fs.writeFileSync(backgroundJsPath, backgroundJsContent.replace("{PORT}", port.toString()));

    this._userDataDir = this._userDataDir || path.join(TEMP_DIR, "profile");
    const args = [
      `--user-data-dir=${this._userDataDir}`,
      `--load-extension=${extDir}`,
      `--window-position=${this._left},${this._top}`,
      `--window-size=${this._width},${this._height}`,
      this._blockImage ? "--blink-settings=imagesEnabled=false" : "",
      this._userAgent ? `--user-agent=${this._userAgent}` : "",
      this._initUrl
    ];

    this._process = execFile(chromePath, args);
    wsServer.on('connection', ws => {
      this._clientUnit = ws;
      console.log("Client connected");
    });

    return new Promise(resolve => setTimeout(resolve, 5000));
  }

  quit() {
    if (this._process) {
      this._process.kill();
      this._process = null;
    }
    if (this._clientUnit) {
      this._clientUnit.close();
      this._clientUnit = null;
    }
    this._width = 0;
    this._height = 0;
    this._blockImage = true;
  }

  async runScript(script) {
    return await this._sendCommand("runScript", script);
  }

  async url() {
    return await this.runScript("location.href");
  }

  async goto(url, waitTimeout = 30000, waitElemSelector = null) {
    let timeout = false;
    const oldUrl = await this.url();
    if (oldUrl === url) {
      await this.runScript("location.reload()");
    } else {
      await this.runScript(`location.href='${url}'`);
      const start = Date.now();
      while ((await this.url()) === oldUrl && Date.now() - start < waitTimeout) {
        await new Promise(res => setTimeout(res, 100));
      }
      if ((await this.url()) === oldUrl) timeout = true;
    }

    if (!timeout && waitElemSelector) {
      const start = Date.now();
      while (Date.now() - start < waitTimeout) {
        const element = await this.runScript(`document.querySelector('${waitElemSelector}')`);
        if (element) break;
        await new Promise(res => setTimeout(res, 100));
      }
      if (Date.now() - start >= waitTimeout) timeout = true;
    }

    if (timeout) console.error("Timeout occurred");
    return !timeout;
  }
}

module.exports = Chrome;
