from api import Client, TransactionRejected
import pandas as pd
import pandas_ta as ta
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from redis.client import Redis
from redis.exceptions import ConnectionError
import cloud as gcp

# Settings.json
settings = {
    'symbols': ['GOLD', 'GBPUSD', 'EURUSD'],
    'tech': [
        {"kind": "ema", "length": 8},
        {"kind": "ema", "length": 21},
        {
            "kind": "macd", "fast": 8, "slow": 21, "signal_indicators": True,
            "colnames": ('MACD', 'MACDh', 'MACDs', 'MACDh_XA0', 'MACDh_XB0', 'MACDh_A0'),
        },
    ],
    'volume': 0.1,
    'rate_tp': 0.2,
    'rate_sl': 0.1,
}

# Initial connection
load_dotenv(find_dotenv())
r_name = os.getenv("RACE_NAME")
r_pass = os.getenv("RACE_PASS")
r_mode = os.getenv("RACE_MODE")
symbols = settings.get('symbols')
tech = settings.get('tech')
volume = settings.get('volume')
rate_tp = settings.get('rate_tp')
rate_sl = settings.get('rate_sl')


class Cache:
    def __init__(self):
        self.ttl_s = 604_800
        self.client = Redis(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv("REDIS_PORT"),
            decode_responses=True
        )

    def set_key(self, key, value):
        self.client.set(key, json.dumps(value), ex=self.ttl_s)

    def get_key(self, key):
        return json.loads(self.client.get(key))

    def get_keys(self, keys):
        return [json.loads(s) for s in self.client.mget(keys)]


def macd_cross(df):
    """As evaluate function, takes pandas.DataFrame contains 'MACD..._A_0' column,
    return: (bool)whether_to_open_position, (str)mode_buy_or_sell.
    """
    cols = df.columns.to_list()
    col = [c for c in cols if c.startswith('MACD') and c.endswith('_A_0')]
    signal_col = col[0] if col else ''
    last_signal = df.iloc[-1][signal_col]
    prev_signal = df.iloc[-2][signal_col]
    opentx = last_signal != prev_signal
    mode = 'buy' if last_signal > 0 else 'sell'
    return opentx, mode


def indicator_signal(client, symbol):
    # get charts
    period = 15
    now = int(time.time())
    res = client.get_chart_range_request(symbol, period, now, now, -100)
    digits = res['digits']
    rate_infos = res['rateInfos']
    print(f'Info: recv {symbol} {len(rate_infos)} ticks.')
    # caching
    try:
        cache = Cache()
        for ctm in rate_infos:
            cache.set_key(f'{symbol}_{period}:{ctm["ctm"]}', ctm)
        ctm_prefix = range(((now - 360_000) // 100_000), (now // 100_000)+1)
        rate_infos = []
        for pre in ctm_prefix:
            mkey = cache.client.keys(pattern=f'{symbol}_{period}:{pre}*')
            rate_infos.extend(cache.get_keys(mkey))
    except ConnectionError as e:
        print(e)
    # tech calculation
    rate_infos.sort(key=lambda x: x['ctm'])
    candles = pd.DataFrame(rate_infos)
    candles['close'] = (candles['close'] + candles['open']) / 10 ** digits
    print(f'Info: got {symbol} {len(candles)} ticks.')
    ta_strategy = ta.Strategy(
        name="Multi-Momo",
        ta=tech,
    )
    candles.ta.strategy(ta_strategy)
    # clean
    candles.dropna(inplace=True, ignore_index=True)
    epoch_ms = candles.iloc[-1]['ctm']
    print(f'Info: cleaned {symbol} {len(candles)} ticks.')
    # evaluate
    opentx, mode = macd_cross(candles)
    return candles, {"epoch_ms": epoch_ms, "open": opentx, "mode": mode}


class Notify:
    def __init__(self):
        self.ts = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        self.notes = ''

    def setts(self, ts):
        self.ts = ts
        return ts

    def add(self, message):
        self.notes += f'{message}\n'
        return message


def trigger_open_trade(client, symbol, mode='buy'):
    try:
        return client.open_trade(mode, symbol, volume, rate_tp=rate_tp, rate_sl=rate_sl)
    except TransactionRejected as e:
        # print(f'Exception: transaction rejected! {e}')
        return e


def run():
    client = Client()
    client.login(r_name, r_pass, mode=r_mode)
    notify = Notify()
    print('Enter the Gate.')

    # Check if market is open
    market_status = client.check_if_market_open(symbols)
    msg = notify.add(f'Market status: {market_status}')
    print(msg)
    for symbol in market_status.keys():
        if not market_status[symbol]:
            continue
        # Market open, check signal
        df, signal = indicator_signal(client, symbol)
        close = df.iloc[-1]['close']
        opentx = signal.get("open")
        mode = signal.get("mode")
        ts = notify.setts(datetime.fromtimestamp(int(signal.get("epoch_ms"))/1000))
        msg = notify.add(f'Signal: {symbol}, {ts}, {opentx}, {mode}, {close}')
        print(msg)
        print(df.tail())
        # Check signal to open transaction
        if opentx:
            res = trigger_open_trade(client, symbol=symbol, mode=mode)
            msg = notify.add(f'>> Open: {symbol}, {ts}, {mode}, {volume}, {res}')
            print(msg)

    client.logout()
    gcp.pub(notify.notes)


if __name__ == '__main__':
    run()
