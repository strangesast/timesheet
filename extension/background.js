const TIMELINE_URL = 'https://www.google.com/maps/timeline/kml';

chrome.runtime.onInstalled.addListener(function() {
    console.log("installed");

    chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
        console.log('sender:', sender);
        switch (request) {
            case "timeline": {
                setTimeout(() => sendResponse('toast'), 1000);
            }
        }
        return true;
    })
});

function rewriteDateString(fromDate, toDate) {
    return `1m8!1m3!1i${fromDate.getFullYear()}!2i${fromDate.getMonth()}!3i${fromDate.getDate()}!2m3!1i${toDate.getFullYear()}!2i${toDate.getMonth()}!3i${toDate.getDate()}`;
}

function addDays(date, n=1) {
    const d = new Date(date);
    d.setDate(d.getDate() + 1);
    return d;
}

function fetchTimeline(date) {}
    const url = new URL(TIMELINE_URL);
    const fromDate = new Date();
    const toDate = addDays(fromDate, 1);
    url.search = new URLSearchParams({authuser: 0, pb: rewriteDateString(fromDate, toDate)}).toString();
    console.log('url:', url);

    fetch(url).then(res => res.text()).then(txt => {
    });
}

