const Chrome = require('./lib/chrome');
const sleep = require('./lib/sleep.js');
const fs = require('fs');
const path = require('path');

(async () => {
  // initialize browser
  const chrome = new Chrome("http://example.com", 0, 0, 800, 600, true);
  await chrome.start();
  await chrome.goto("https://shopee.tw/a-i.178926468.21448123549")
  await sleep(5000);
  await chrome.runScript("window.scrollTo(0, document.body.scrollHeight)")
  await sleep(5000);
  const htmlContent = await chrome.runScript("document.body.outerHTML");
  
  // create 'result' directory if it doesn't exist
  const resultDir = path.join(__dirname, 'result');
  if (!fs.existsSync(resultDir)) {
    fs.mkdirSync(resultDir);
  }
  
  // generate a unique filename using the timestamp
  const filename = `page_${Date.now()}.html`;
  const filepath = path.join(resultDir, filename);

  // save the HTML content to the file
  fs.writeFileSync(filepath, htmlContent);
  console.log(`Saved to ${filepath}`);
  
  chrome.quit();
  process.exit(0);
})();
