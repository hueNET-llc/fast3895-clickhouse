FROM alpine:3.20

COPY . /fast3895-clickhouse

WORKDIR /fast3895-clickhouse

RUN apk update && \
    apk add --no-cache python3 py3-pip tzdata rsync && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

ENTRYPOINT ["python", "-u", "fast3895.py"]