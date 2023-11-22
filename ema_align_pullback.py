from api import Client, TransactionRejected
import pandas as pd
import pandas_ta as ta
import json
import time
import os
from dotenv import load_dotenv, find_dotenv
from redis.client import Redis

REDIS_HOST = 'localhost'
REDIS_PORT = 6379


class Cache:
    def __init__(self):
        self.ttl_s = 604_800
        self.client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    def set_key(self, key, value):
        self.client.set(key, json.dumps(value), ex=self.ttl_s)

    def get_key(self, key):
        return json.loads(self.client.get(key))

    def get_keys(self, keys):
        return [json.loads(s) for s in self.client.mget(keys)]


def ma_align(row):
    """As row function, takes pandas.series.Series or dictionaries contain 'close' and 'EMA_X' keys,
    return: (str)EMA_trend_action, (int)degree_of_price_among_EMA.
    note: +/- is long/short.
    """

    # inner function
    def is_sorted(list_num):
        return list_num == sorted(list_num)

    def is_rsorted(list_num):
        return list_num == sorted(list_num, reverse=True)

    # extract EMA/SMA columns
    ma_cols = [(int(n.split('_')[-1]), n) for n in row.keys().to_list() if 'MA_' in n]
    ma_cols.sort()
    # calculation
    list_ma = [row[k] for i, k in ma_cols]
    close = row['close']
    action, degree = 'stay', 0
    if is_sorted(list_ma):
        action, degree = 'sell', -sorted(list_ma + [close]).index(close)
    if is_rsorted(list_ma):
        action, degree = 'buy', sorted(list_ma + [close], reverse=True).index(close)
    return {'Action': action, 'Degree': degree}


def indicator_signal(client, symbol, tech):
    # get charts
    period = 15
    now = int(time.time())
    res = client.get_chart_range_request(symbol, period, now, now, -100)
    rate_infos = res['rateInfos']
    print(f'Info: recv {symbol} {len(rate_infos)} ticks.')
    # caching
    cache = Cache()
    for ctm in rate_infos:
        cache.set_key(f'{symbol}_{period}:{ctm["ctm"]}', ctm)
    ctm_prefix = range(((now - 360_000) // 100_000), (now // 100_000)+1)
    rate_infos = []
    for pre in ctm_prefix:
        mkey = cache.client.keys(pattern=f'{symbol}_{period}:{pre}*')
        rate_infos.extend(cache.get_keys(mkey))
    # tech calculation
    rate_infos.sort(key=lambda x: x['ctm'])
    candles = pd.DataFrame(rate_infos)
    candles['close'] = candles['close'] + candles['open']
    print(f'Info: got {symbol} {len(candles)} ticks.')
    ta_strategy = ta.Strategy(
        name="Multi-Momo",
        description="EMA 25,50,100,200",
        ta=tech,
    )
    candles.ta.strategy(ta_strategy)
    # clean
    candles.dropna(inplace=True, ignore_index=True)
    print(f'Info: cleaned {symbol} {len(candles)} ticks.')
    # evaluate trend alignment
    candles[['Action', 'Degree']] = pd.DataFrame(candles.apply(ma_align, axis=1).values.tolist())
    print(f'Info: processed {symbol} {len(candles)} ticks.')
    # candles.to_csv(f'candles_{symbol}.csv')
    # filter last run trend
    df = candles[::-1]
    fltr = [cur := True] and [cur := bool(cur * i) for i in df['Degree'].values.tolist()]
    opentx, mode = False, 'stay'
    if sum(fltr):
        mode = df[fltr]['Action'].values.tolist()[0]
        degree = df[fltr]['Degree'].values.tolist()
        # whether current point just rebound
        peak = max(degree, key=abs)
        idx_peak = degree.index(peak)
        shoulder = [abs(peak - v) >= 2 for i, v in enumerate(degree) if i < idx_peak]
        opentx = sum(shoulder) == 1
    return opentx, mode


def trigger_open_trade(client, symbol, mode='buy', volume=0.1):
    try:
        client.open_trade(mode, symbol, volume)
    except TransactionRejected:
        # May send notification
        trigger_notify()
    return


def trigger_notify():
    return


# Settings.json
load_dotenv(find_dotenv())
r_name = os.getenv("RACE_NAME")
r_pass = os.getenv("RACE_PASS")
r_mode = os.getenv("RACE_MODE")
settings = {
    'racer': {'name': r_name, 'shield': r_pass, 'action': r_mode},
    'symbols': ['GOLD', 'EURUSD'],
    'tech': [
        {"kind": "ema", "length": 25},
        {"kind": "ema", "length": 50},
        {"kind": "ema", "length": 100},
        {"kind": "ema", "length": 200},
    ]
}

# Initial connection
racer = settings.get('racer')
symbols = settings.get('symbols')
tech = settings.get('tech')


def run():
    client = Client()
    client.login(racer['name'], racer['shield'], mode=racer['action'])
    print('Enter the Gate.')

    # Check if market is open
    market_status = client.check_if_market_open(symbols)
    print(f'Ready: {market_status}')
    for symbol in market_status.keys():
        if not market_status[symbol]:
            continue
        opentx, mode = indicator_signal(client, symbol, tech)
        print(f'Signal: [{symbol}, {opentx}, {mode}]')
        if opentx:
            # trigger_open_trade(client, symbol=symbol, mode=mode)
            print(f'Open: [{symbol}, {mode}]')

    client.logout()


if __name__ == '__main__':
    run()
