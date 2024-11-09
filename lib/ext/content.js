function printLog(logStr) {
    // console.log("[" + new Date().toLocaleTimeString() + "] content.js:: " + logStr);
}

printLog("loaded");

chrome.runtime.onMessage.addListener(
    function (request, sender, sendResponse) {
        printLog(sender.tab ?
            "from a content script:" + sender.tab.url :
            "from the extension");

        jscript = request.script;
        printLog("script > " + jscript)

        res = "";
        try {
            res = eval(jscript);
        }
        catch (error) {
            res = error.message;
        }

        if (res == undefined) {
            res = "<undefined>";
        }
        printLog("result > " + res);
        sendResponse({ result: res });
    }
);
