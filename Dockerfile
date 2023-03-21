# syntax=docker/dockerfile:1

FROM python:3.8.16-bullseye
COPY /requirements.txt /requirements.txt
RUN pip install -U pip
RUN pip install -r requirements.txt
COPY main.py main.py
ENTRYPOINT [ "python", "main.py"]
LABEL org.opencontainers.image.source="https://github.com/nubelaco/historic-employee-count-tool"