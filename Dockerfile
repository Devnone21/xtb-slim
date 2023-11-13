FROM python:3.10-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install websocket
RUN pip install websocket-client

COPY ./main.py .

CMD [ "python", "./main.py" ]
