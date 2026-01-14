FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip
COPY . .

RUN pip install -e .