FROM python:3.10 as builder

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels websockets

# final stage
FROM python:3.10-slim

WORKDIR /usr/src/app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

COPY ./api.py .
COPY ./macd_crossover.py .

CMD [ "python", "-u", "./macd_crossover.py" ]

# FROM python:3.10-slim

# WORKDIR /usr/src/app

# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install websockets

# COPY ./main.py .

# CMD [ "python", "./main.py" ]
