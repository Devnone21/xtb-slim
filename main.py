"""
XTBApi.api
~~~~~~~

Main module
"""

import enum
import json
import time
from datetime import datetime
from websockets.sync.client import connect
from websockets.exceptions import WebSocketException

LOGIN_TIMEOUT = 120
MAX_TIME_INTERVAL = 0.200


class CommandFailed(Exception):
    """when a command fail"""
    def __init__(self, response):
        self.msg = "command failed"
        self.err_code = response['errorCode']
        super().__init__(self.msg)


class NotLogged(Exception):
    """when not logged"""
    def __init__(self):
        self.msg = "Not logged, please log in"
        super().__init__(self.msg)


class SocketError(Exception):
    """when socket is already closed
    may be the case of server internal error"""
    def __init__(self):
        self.msg = "SocketError, mey be an internal error"
        super().__init__(self.msg)


class TransactionRejected(Exception):
    """transaction rejected error"""
    def __init__(self, status_code):
        self.status_code = status_code
        self.msg = "transaction rejected with error code {}".format(
            status_code)
        super().__init__(self.msg)


class STATUS(enum.Enum):
    LOGGED = enum.auto()
    NOT_LOGGED = enum.auto()


class MODES(enum.Enum):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BALANCE = 6
    CREDIT = 7


class TRANS_TYPES(enum.Enum):
    OPEN = 0
    PENDING = 1
    CLOSE = 2
    MODIFY = 3
    DELETE = 4


class PERIOD(enum.Enum):
    ONE_MINUTE = 1
    FIVE_MINUTES = 5
    FIFTEEN_MINUTES = 15
    THIRTY_MINUTES = 30
    ONE_HOUR = 60
    FOUR_HOURS = 240
    ONE_DAY = 1440
    ONE_WEEK = 10080
    ONE_MONTH = 43200


def _get_data(command, **parameters):
    data = {
        "command": command,
    }
    if parameters:
        data['arguments'] = {}
        for (key, value) in parameters.items():
            data['arguments'][key] = value
    return data


def _check_mode(mode):
    """check if mode acceptable"""
    modes = [x.value for x in MODES]
    if mode not in modes:
        raise ValueError("mode must be in {}".format(modes))


def _check_period(period):
    """check if period is acceptable"""
    if period not in [x.value for x in PERIOD]:
        raise ValueError("Period: {} not acceptable".format(period))


def _check_volume(volume):
    """normalize volume"""
    if not isinstance(volume, float):
        try:
            return float(volume)
        except Exception:
            raise ValueError("vol must be float")
    else:
        return volume


class BaseClient(object):
    """main client class"""

    def __init__(self):
        self.ws = None
        self._login_data = None
        self._time_last_request = time.time() - MAX_TIME_INTERVAL
        self.status = STATUS.NOT_LOGGED

    def _login_decorator(self, func, *args, **kwargs):
        # if self.status == STATUS.NOT_LOGGED:
        #     raise NotLogged()
        try:
            return func(*args, **kwargs)
        except SocketError as e:
            self.login(self._login_data[0], self._login_data[1])
            print(self._login_data)
            return func(*args, **kwargs)
        except Exception as e:
            self.login(self._login_data[0], self._login_data[1])
            return func(*args, **kwargs)

    def _send_command(self, dict_data):
        """send command to api"""
        time_interval = time.time() - self._time_last_request
        if time_interval < MAX_TIME_INTERVAL:
            time.sleep(MAX_TIME_INTERVAL - time_interval)
        try:
            self.ws.send(json.dumps(dict_data))
            response = self.ws.recv()
        except WebSocketException:
            raise SocketError()
        self._time_last_request = time.time()
        res = json.loads(response)
        if res['status'] is False:
            raise CommandFailed(res)
        if 'returnData' in res.keys():
            return res['returnData']

    def _send_command_with_check(self, dict_data):
        """with check login"""
        return self._login_decorator(self._send_command, dict_data)

    def login(self, user_id, password, mode='demo'):
        """login command"""
        data = _get_data("login", userId=user_id, password=password)
        self.ws = connect(f"wss://ws.xtb.com/{mode}")
        response = self._send_command(data)
        self._login_data = (user_id, password)
        self.status = STATUS.LOGGED
        return response

    def logout(self):
        """logout command"""
        data = _get_data("logout")
        response = self._send_command(data)
        self.status = STATUS.LOGGED
        return response

    def get_all_symbols(self):
        """getAllSymbols command"""
        data = _get_data("getAllSymbols")
        return self._send_command_with_check(data)

    def get_calendar(self):
        """getCalendar command"""
        data = _get_data("getCalendar")
        return self._send_command_with_check(data)

    def get_chart_last_request(self, symbol, period, start):
        """getChartLastRequest command"""
        _check_period(period)
        args = {
            "period": period,
            "start": start * 1000,
            "symbol": symbol
        }
        data = _get_data("getChartLastRequest", info=args)
        return self._send_command_with_check(data)

    def get_chart_range_request(self, symbol, period, start, end, ticks):
        """getChartRangeRequest command"""
        if not isinstance(ticks, int):
            raise ValueError(f"ticks value {ticks} must be int")
        # self._check_login()
        args = {
            "end": end * 1000,
            "period": period,
            "start": start * 1000,
            "symbol": symbol,
            "ticks": ticks
        }
        data = _get_data("getChartRangeRequest", info=args)
        return self._send_command_with_check(data)

    def get_commission(self, symbol, volume):
        """getCommissionDef command"""
        volume = _check_volume(volume)
        data = _get_data("getCommissionDef", symbol=symbol, volume=volume)
        return self._send_command_with_check(data)

    def get_margin_level(self):
        """getMarginLevel command
        get margin information"""
        data = _get_data("getMarginLevel")
        return self._send_command_with_check(data)

    def get_margin_trade(self, symbol, volume):
        """getMarginTrade command
        get expected margin for volumes used symbol"""
        volume = _check_volume(volume)
        data = _get_data("getMarginTrade", symbol=symbol, volume=volume)
        return self._send_command_with_check(data)

    def get_profit_calculation(self, symbol, mode, volume, op_price, cl_price):
        """getProfitCalculation command
        get profit calculation for symbol with vol, mode and op, cl prices"""
        _check_mode(mode)
        volume = _check_volume(volume)
        data = _get_data("getProfitCalculation", closePrice=cl_price,
                         cmd=mode, openPrice=op_price, symbol=symbol,
                         volume=volume)
        return self._send_command_with_check(data)

    def get_server_time(self):
        """getServerTime command"""
        data = _get_data("getServerTime")
        return self._send_command_with_check(data)

    def get_symbol(self, symbol):
        """getSymbol command"""
        data = _get_data("getSymbol", symbol=symbol)
        return self._send_command_with_check(data)

    def get_tick_prices(self, symbols, start, level=0):
        """getTickPrices command"""
        data = _get_data("getTickPrices", level=level, symbols=symbols,
                         timestamp=start)
        return self._send_command_with_check(data)

    def get_trade_records(self, trade_position_list):
        """getTradeRecords command
        takes a list of position id"""
        data = _get_data("getTradeRecords", orders=trade_position_list)
        return self._send_command_with_check(data)

    def get_trades(self, opened_only=True):
        """getTrades command"""
        data = _get_data("getTrades", openedOnly=opened_only)
        return self._send_command_with_check(data)

    def get_trades_history(self, start, end):
        """getTradesHistory command
        can take 0 as actual time"""
        data = _get_data("getTradesHistory", end=end, start=start)
        return self._send_command_with_check(data)

    def get_trading_hours(self, trade_position_list):
        """getTradingHours command"""
        data = _get_data("getTradingHours", symbols=trade_position_list)
        response = self._send_command_with_check(data)
        for symbol in response:
            for day in symbol['trading']:
                day['fromT'] = int(day['fromT'] / 1000)
                day['toT'] = int(day['toT'] / 1000)
            for day in symbol['quotes']:
                day['fromT'] = int(day['fromT'] / 1000)
                day['toT'] = int(day['toT'] / 1000)
        return response

    def get_version(self):
        """getVersion command"""
        data = _get_data("getVersion")
        return self._send_command_with_check(data)

    def ping(self):
        """ping command"""
        data = _get_data("ping")
        self._send_command_with_check(data)

    def trade_transaction(self, symbol, mode, trans_type, volume, stop_loss=0,
                          take_profit=0, **kwargs):
        """tradeTransaction command"""
        # check type
        if trans_type not in [x.value for x in TRANS_TYPES]:
            raise ValueError(f"Type must be in {[x for x in trans_type]}")
        # check sl & tp
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)
        # check kwargs
        accepted_values = ['order', 'price', 'expiration', 'customComment',
                           'offset', 'sl', 'tp']
        assert all([val in accepted_values for val in kwargs.keys()])
        _check_mode(mode)  # check if mode is acceptable
        volume = _check_volume(volume)  # check if volume is valid
        info = {
            'cmd': mode,
            'symbol': symbol,
            'type': trans_type,
            'volume': volume,
            'sl': stop_loss,
            'tp': take_profit
        }
        info.update(kwargs)  # update with kwargs parameters
        data = _get_data("tradeTransaction", tradeTransInfo=info)
        name_of_mode = [x.name for x in MODES if x.value == mode][0]
        name_of_type = [x.name for x in TRANS_TYPES if x.value ==
                        trans_type][0]
        return self._send_command_with_check(data)

    def trade_transaction_status(self, order_id):
        """tradeTransactionStatus command"""
        data = _get_data("tradeTransactionStatus", order=order_id)
        return self._send_command_with_check(data)

    def get_user_data(self):
        """getCurrentUserData command"""
        data = _get_data("getCurrentUserData")
        return self._send_command_with_check(data)


class Transaction(object):
    def __init__(self, trans_dict):
        self._trans_dict = trans_dict
        self.mode = {0: 'buy', 1: 'sell'}[trans_dict['cmd']]
        self.order_id = trans_dict['order']
        self.symbol = trans_dict['symbol']
        self.volume = trans_dict['volume']
        self.price = trans_dict['close_price']
        self.actual_profit = trans_dict['profit']
        self.timestamp = trans_dict['open_time'] / 1000


class Client(BaseClient):
    """advanced class of client"""
    def __init__(self):
        super().__init__()
        self.trade_rec = {}

    def check_if_market_open(self, list_of_symbols):
        """check if market is open for symbol in symbols"""
        _td = datetime.today()
        actual_tmsp = _td.hour * 3600 + _td.minute * 60 + _td.second
        response = self.get_trading_hours(list_of_symbols)
        market_values = {}
        for symbol in response:
            today_values = [day for day in symbol['trading'] if day['day'] ==
                _td.isoweekday()]
            if not today_values:
                market_values[symbol['symbol']] = False
                continue
            today_values = today_values[0]
            if today_values['fromT'] <= actual_tmsp <= today_values['toT']:
                market_values[symbol['symbol']] = True
            else:
                market_values[symbol['symbol']] = False
        return market_values

    def get_lastn_candle_history(self, symbol, timeframe_in_seconds, number):
        """get last n candles of timeframe"""
        acc_tmf = [60, 300, 900, 1800, 3600, 14400, 86400, 604800, 2592000]
        if timeframe_in_seconds not in acc_tmf:
            raise ValueError(f"timeframe not accepted, not in "
                             f"{', '.join([str(x) for x in acc_tmf])}")
        sec_prior = timeframe_in_seconds * number

        res = {'rateInfos': []}
        while len(res['rateInfos']) < number:
            res = self.get_chart_last_request(symbol,
                timeframe_in_seconds // 60, time.time() - sec_prior)
            res['rateInfos'] = res['rateInfos'][-number:]
            sec_prior *= 3
        candle_history = []
        for candle in res['rateInfos']:
            _pr = candle['open']
            op_pr = _pr / 10 ** res['digits']
            cl_pr = (_pr + candle['close']) / 10 ** res['digits']
            hg_pr = (_pr + candle['high']) / 10 ** res['digits']
            lw_pr = (_pr + candle['low']) / 10 ** res['digits']
            new_candle_entry = {'timestamp': candle['ctm'] / 1000, 'open':
                op_pr, 'close': cl_pr, 'high': hg_pr, 'low': lw_pr,
                                'volume': candle['vol']}
            candle_history.append(new_candle_entry)
        return candle_history

    def update_trades(self):
        """update trade list"""
        trades = self.get_trades()
        self.trade_rec.clear()
        for trade in trades:
            obj_trans = Transaction(trade)
            self.trade_rec[obj_trans.order_id] = obj_trans
        return self.trade_rec

    def get_trade_profit(self, trans_id):
        """get profit of trade"""
        self.update_trades()
        profit = self.trade_rec[trans_id].actual_profit
        return profit

    def open_trade(self, mode, symbol, volume):
        """open trade transaction"""
        if mode in [MODES.BUY.value, MODES.SELL.value]:
            mode = [x for x in MODES if x.value == mode][0]
        elif mode in ['buy', 'sell']:
            modes = {'buy': MODES.BUY, 'sell': MODES.SELL}
            mode = modes[mode]
        else:
            raise ValueError("mode can be buy or sell")
        mode_name = mode.name
        mode_value = mode.value
        conversion_mode = {MODES.BUY.value: 'ask', MODES.SELL.value: 'bid'}
        price = self.get_symbol(symbol)[conversion_mode[mode_value]]
        response = self.trade_transaction(symbol, mode_value, 0, volume, price=price)
        self.update_trades()
        status = self.trade_transaction_status(response['order'])[
            'requestStatus']
        if status != 3:
            raise TransactionRejected(status)
        return response

    def _close_trade_only(self, order_id):
        """faster but less secure"""
        trade = self.trade_rec[order_id]
        try:
            response = self.trade_transaction(
                trade.symbol, 0, 2, trade.volume, order=trade.order_id,
                price=trade.price)
        except CommandFailed as e:
            if e.err_code == 'BE51':  # order already closed
                return 'BE51'
            else:
                raise
        status = self.trade_transaction_status(
            response['order'])['requestStatus']
        if status != 3:
            raise TransactionRejected(status)
        return response

    def close_trade(self, trans):
        """close trade transaction"""
        if isinstance(trans, Transaction):
            order_id = trans.order_id
        else:
            order_id = trans
        self.update_trades()
        return self._close_trade_only(order_id)

    def close_all_trades(self):
        """close all trades"""
        self.update_trades()
        trade_ids = self.trade_rec.keys()
        for trade_id in trade_ids:
            self._close_trade_only(trade_id)


import pandas as pd
import pandas_ta as ta
import firebase_admin as fba
from firebase_admin import firestore

def indicator_signal(symbol, strategy):
    today = datetime.today()
    mode = 'buy' if int(today.hour) % 2 == 1 else 'sell'
    cross = int(today.minute) % 2 == 1
    return cross, mode

def trigger_open_trade(symbol, mode='buy', volume=0.1):
    try:
        client.open_trade(mode, symbol, volume)
    except TransactionRejected:
        # May send notification
        trigger_notify()
    return

def trigger_notify():
    return


# Settings.json
settings = {
    'racer': {'name': '15351881', 'shield': '', 'action': 'demo'},
    'symbols': ['GOLD', 'EURUSD'],
    'strategy': 'EMA_50-SMA_200',
}

# Application Default credentials are automatically created.
dba = fba.initialize_app()
db = firestore.client()
docs = db.collection("xtb-set").stream()
for doc in docs:
    k, v = doc.to_dict().popitem()
    settings[k] = v

# Initial connection
racer = settings.get('racer')
symbols = settings.get('symbols')
strategy = settings.get('strategy')

client = Client()
client.login(racer['name'], racer['shield'], mode=racer['action'])
print('Enter the Gate.')

# Check if market is open
market_status = client.check_if_market_open(symbols)
print(f'Ready: {market_status}')
for symbol in market_status.keys():
    if not market_status[symbol]:
        continue
    crossover, mode = indicator_signal(symbol, strategy)
    print(f'Signal: [{symbol}, {crossover}, {mode}]')
    if crossover:
        trigger_open_trade(symbol=symbol, mode=mode)
        print(f'Open: [{symbol}, {mode}]')

client.logout()
