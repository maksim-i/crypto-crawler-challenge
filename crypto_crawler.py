import csv
import os
from datetime import datetime
from time import sleep

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import requests

import logging
from logging.handlers import RotatingFileHandler


logger = logging.getLogger(__name__)


HEADERS_CG = {
    'accept': 'application/json'
}

DEFAULT_TIMEOUT = 30
VALUES_LEN = 10

USER_AGENT_CHROME = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '\
                    '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

HEADERS_CMC_SEARCH = {
    'Host': 's3.coinmarketcap.com',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 '
                  'Firefox/134.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, zstd',
    'Referer': 'https://coinmarketcap.com/',
    'Origin': 'https://coinmarketcap.com',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'TE': 'trailers'
}
HEADERS_CMC_DETAILS = {
    'Host': 'api.coinmarketcap.com',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 '
                  'Firefox/134.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;'
              'q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, zstd',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Priority': 'u=0, i',
    'TE': 'trailers'
}


def return_price_str(price_value):
    usd_commas = '{:,}'.format(float(price_value))
    if len(usd_commas.split('.')[1]) == 1:
        usd_commas += '0'

    return usd_commas


def price_pulse_coingecko():
    prev_ts = None
    latest_values = []
    wait_timeout = DEFAULT_TIMEOUT
    failure_count = 0
    while True:
        logger.info('Pinging coingecko..')

        btc_usd_resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?'
            'ids=bitcoin&vs_currencies=usd&include_last_updated_at=true',
            headers=HEADERS_CG, timeout=10)

        resp_status = btc_usd_resp.status_code

        if 200 <= resp_status <= 299:
            wait_timeout = DEFAULT_TIMEOUT
            failure_count = 0

            btc_usd_dict = btc_usd_resp.json()['bitcoin']

            # UTC
            btc_usd_ts = datetime.utcfromtimestamp(
                btc_usd_dict['last_updated_at']).strftime('%Y-%m-%dT%H:%M:%S')

            usd_commas = return_price_str(btc_usd_dict['usd'])

            if btc_usd_ts != prev_ts:
                logger.info('Price has been updated')

                prev_ts = btc_usd_ts
                latest_values.append(btc_usd_dict['usd'])

                if len(latest_values) > VALUES_LEN:
                    del latest_values[0]

                # only calculate when there are enough values
                if len(latest_values) == VALUES_LEN:
                    moving_average = return_price_str(
                        round(sum(latest_values) / VALUES_LEN, 2))
                else:
                    moving_average = None

                if moving_average:
                    print(f'[{btc_usd_ts}] BTC → USD: ${usd_commas}; '
                          f'SMA({VALUES_LEN}): ${moving_average}')
                else:
                    print(f'[{btc_usd_ts}] BTC → USD: ${usd_commas}; '
                          f'SMA({VALUES_LEN}): not enough values '
                          f'(will need {VALUES_LEN})')
            else:
                logger.info('No changes detected')
        elif resp_status in [500, 503]:
            failure_count += 1

            if failure_count == 5:
                logger.error('(!) Five failures in a row, will continue')

            # do not increase the timeout further
            if failure_count <= 3:
                wait_timeout *= 2

            logger.warning('Server error (failure count: %s)', failure_count)
        else:
            logger.error('Error [code %s]\ndata:\n%s', resp_status,
                         btc_usd_resp.text)

            raise Exception(f'Error [code {resp_status}]')

        logger.info('Waiting for %s seconds..', wait_timeout)

        sleep(wait_timeout)


def fetch_coinmarketcap_data_selenium():
    logger.info('Fetching CoinMarketCap data (Selenium)..')

    data_file = 'five_pages_selenium.csv'
    if os.path.exists(data_file):
        os.remove(data_file)

    options = webdriver.ChromeOptions()

    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1500,700')
    options.add_argument('--headless=new')

    with webdriver.Chrome(options=options) as driver:
        driver.execute_script(
            'Object.defineProperty(navigator, "webdriver", '
            '{get: () => undefined})')
        driver.execute_cdp_cmd(
            'Network.setUserAgentOverride', {'userAgent': USER_AGENT_CHROME})

        for cmc_page in range(5):
            logger.info('Processing page %s', cmc_page + 1)

            sleep(4)

            driver.get(f'https://coinmarketcap.com/?page={cmc_page + 1}')

            WebDriverWait(driver, 30).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'span.table_footer-left')))

            prev_height = 0
            same_count = 0
            while True:
                driver.execute_script('window.scrollBy(0, 300);')

                height = driver.execute_script(
                    'return document.body.scrollHeight')

                sleep(1)

                if height != prev_height:
                    prev_height = height
                    same_count = 0
                else:
                    same_count += 1

                if same_count == 2:
                    break

            logger.info('Generating rows list..')

            table_object = driver.find_element(
                By.CSS_SELECTOR, 'table.cmc-table')

            table_headers = [t_h.text for t_h
                             in table_object.find_elements(
                                By.CSS_SELECTOR, 'thead > tr > th')]
            table_rows = [
                [tr_txt.text for tr_txt
                 in t_r.find_elements(By.CSS_SELECTOR, 'td')]
                for t_r in table_object.find_elements(
                    By.CSS_SELECTOR, 'tbody > tr')
            ]

            for row in table_rows:
                row_dict = dict(zip(table_headers, row))

                write_dict = dict()
                write_dict['Rank'] = row_dict['#']

                name_split = row_dict['Name'].split('\n')
                write_dict['Name & Symbol'] = f'{name_split[0]} '\
                                              f'{name_split[1]}'

                write_dict['Price (USD)'] = row_dict['Price']
                write_dict['24 h % Change'] = row_dict['24h %']
                write_dict['Market Cap (USD)'] = row_dict['Market Cap']

                write_header = True
                if os.path.exists(data_file):
                    write_header = False

                with open(data_file, 'a', newline='', encoding='utf-8') as r:
                    writer = csv.DictWriter(r, fieldnames=write_dict.keys())

                    if write_header:
                        writer.writeheader()

                    writer.writerow(write_dict)


def fetch_coinmarketcap_data_api():
    logger.info('Fetching CoinMarketCap data (API)..')

    data_file = 'five_pages_api.csv'
    if os.path.exists(data_file):
        os.remove(data_file)

    cmc_resp = requests.get(
        'https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json',
        headers=HEADERS_CMC_SEARCH, timeout=10)

    resp_status = cmc_resp.status_code

    if 200 <= resp_status <= 299:
        cmc_dict = cmc_resp.json()

        list_headers = cmc_dict['fields']

        # fetching the first 100 values (5 pages)
        rows_five_pages = cmc_dict['values'][:100]
        for row in rows_five_pages:
            row_index = rows_five_pages.index(row) + 1

            row_dict = dict(zip(list_headers, row))

            write_dict = dict()
            # row_dict "rank" is not the needed value
            write_dict['Rank'] = row_index
            write_dict['Name & Symbol'] = f'{row_dict["name"]} '\
                                          f'{row_dict["symbol"]}'

            sleep(4)

            logger.info('Fetching details for "%s" (%s/%s)..',
                        row_dict['name'], row_index, len(rows_five_pages))

            coin_details = requests.get(
                f'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/'
                f'detail/lite?id={row_dict["id"]}',
                headers=HEADERS_CMC_DETAILS, timeout=10).json()
            coin_data = coin_details['data']['statistics']

            write_dict['Price (USD)'] = coin_data['price']
            write_dict['24 h % Change'] = coin_data['priceChangePercentage24h']
            write_dict['Market Cap (USD)'] = coin_data['marketCap']

            write_header = True
            if os.path.exists(data_file):
                write_header = False

            with open(data_file, 'a', newline='', encoding='utf-8') as r:
                writer = csv.DictWriter(r, fieldnames=write_dict.keys())

                if write_header:
                    writer.writeheader()

                writer.writerow(write_dict)
    else:
        logger.error('Error [code %s]\ndata:\n%s', resp_status, cmc_resp.text)

        raise Exception(f'Error [code {resp_status}]')


def main():
    logging.basicConfig(handlers=[RotatingFileHandler(
        'logs.log', maxBytes=10485760, backupCount=5, encoding='utf-8')],
        level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')

    logger.info('Script started')

    logger.info('Phase 1 - Price Pulse')

    try:
        price_pulse_coingecko()
    except KeyboardInterrupt:
        logger.info('Shutting down (KeyboardInterrupt)..')

        print('Shutting down (Phase 1)..')

    logger.info('Phase 2 - CoinMarketCap Watchlist')

    try:
        fetch_coinmarketcap_data_selenium()
    except KeyboardInterrupt:
        logger.info('Shutting down (KeyboardInterrupt)..')

        print('Shutting down (Phase 2.1)..')

    try:
        fetch_coinmarketcap_data_api()
    except KeyboardInterrupt:
        logger.info('Shutting down (KeyboardInterrupt)..')

        print('Shutting down (Phase 2.2)..')

    logger.info('Script finished')


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception('Exception')
