function printLog(logStr) {
    // console.log("[" + new Date().toLocaleTimeString() + "] background.js::" + logStr);
}

printLog("loaded");
var serverUrl = "ws://127.0.0.1:{PORT}";
printLog("server > " + serverUrl);

var webSocket = new WebSocket(serverUrl);

webSocket.onopen = function (message) {
    printLog("Server connect...\n");
};
webSocket.onclose = function (message) {
    printLog("Server Disconnect...\n");
};
webSocket.onerror = function (message) {
    printLog("error...\n");
};
webSocket.onmessage = function (message) {
    onWebSocketMessage(message);
};

function onWebSocketMessage(message) {
    printLog(message.data);
    var command = JSON.parse(message.data);
    if (command.msg === "clearCookie") {
        var callback = function () {
            resStr = JSON.stringify({ result: "" });
            webSocket.send(resStr);
        };
        var millisecondsPerWeek = 1000 * 60 * 60 * 24 * 7;
        var oneWeekAgo = (new Date()).getTime() - millisecondsPerWeek;
        chrome.browsingData.remove({
            "since": oneWeekAgo
        }, {
            "appcache": false,
            "cache": false,
            "cacheStorage": false,
            "cookies": true,
            "downloads": false,
            "fileSystems": false,
            "formData": false,
            "history": false,
            "indexedDB": false,
            "localStorage": false,
            "passwords": false,
            "serviceWorkers": false,
            "webSQL": false
        }, callback);
    } else if (command.msg === "getCookie") {
        chrome.cookies.getAll({ domain: command.payload }, function (cookies) {
            resStr = JSON.stringify({ result: cookies });
            webSocket.send(resStr);
        });
    } else if (command.msg === "runScript") {
        chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
            if (tabs == undefined) {
                setTimeout(onWebSocketMessage, 100, message);
            }
            else if (tabs[0] == undefined) {
                setTimeout(onWebSocketMessage, 100, message);
            }
            else {
                chrome.tabs.sendMessage(tabs[0].id, { script: command.payload }, function (response) {
                    if (response == undefined) {
                        setTimeout(onWebSocketMessage, 100, message);
                    } else if (response.result == undefined) {
                        setTimeout(onWebSocketMessage, 100, message);
                    } else {
                        resStr = JSON.stringify({ result: response.result });
                        webSocket.send(resStr);
                    }
                });
            }
        });
    }
}
