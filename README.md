## Setup instructions:

* Create a Python env and install the required modules (need Chrome installed as well):
```
pip install requests selenium
```
* Run the script (will first run phase 1, then phase 2 when interrupted with Ctrl+C):
```
python crypto_crawler.py
OR
python3 crypto_crawler.py
```

## Comparison:

* Lines of code:
HTML version: 91  
JSON version: 60  
* Requests per minute:
HTML version: 1  
JSON version: ~14.5  
* Execution time (minutes):
HTML version: 5  
JSON version: ~7 (should probably find a full list of prices instead of fetching one by one)  

## Notes:

According to:  
https://docs.coingecko.com/v3.0.1/reference/simple-price  
"Cache/Update Frequency: every 60 seconds for Public API."  
I checked and it appears to be around one minute (sometimes more, sometimes less, but around one minute, the smallest timeout I got was 40 seconds, longest one was close to 3 minutes).  
So there's no point to update every second, set it to every 30 seconds instead.  
  
Also, according to this:  
https://docs.coingecko.com/v3.0.1/reference/common-errors-rate-limit  
Unpaid plan's rate limit is ~30 calls per minute, so the limit is one call every 2 seconds (plus, when I tried to ping more frequently for a test it returned 429 with a 5 seconds timeout, if you really need it to ping that fast, I could implement async logic with proxies).  