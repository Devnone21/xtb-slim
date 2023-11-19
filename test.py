import json
import time
from datetime import datetime
from websockets.sync.client import connect
import pandas as pd
import pandas_ta as ta

# Settings.json
settings = {
    'racer': {'name': '15351881', 'shield': 'wx+-jLk*9Be!a%*', 'action': 'demo'},
    'symbols': ['GOLD', 'EURUSD'],
    'strategy': 'EMA_50-SMA_200',
}
print(f'Prepare: {settings}')

import firebase_admin as fba
from firebase_admin import firestore

# Application Default credentials are automatically created.
dba = fba.initialize_app()
db = firestore.client()
# collection = db.collection("xtb-set")
docs = db.collection("xtb-set").stream()
for doc in docs:
    print(f"{doc.id} => {doc.to_dict()}")
    k, v = doc.to_dict().popitem()
    settings[k] = v

racer = settings.get('racer')
symbols = settings.get('symbols')
strategy = settings.get('strategy')
print(f'Reload: {settings}')
