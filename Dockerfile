# syntax=docker/dockerfile:1

FROM python:3.8.16-bullseye
COPY /requirements.txt /requirements.txt
RUN pip install -U pip
RUN pip install -r requirements.txt
WORKDIR historic-employee-count-tool
COPY . .
ENTRYPOINT [ "python", "historic-employee-count-tool/main.py"]
LABEL org.opencontainers.image.source=https://github.com/nubelaco/historic-employee-count-tool