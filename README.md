# fast3895-clickhouse
# [fast3895-clickhouse](https://github.com/hueNET-llc/fast3895-clickhouse)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/huenet-llc/fast3895-clickhouse/master.yml?branch=master)](https://github.com/hueNET-llc/fast3895-clickhouse/actions/workflows/master.yml)
[![Docker Image Version (latest by date)](https://img.shields.io/docker/v/rafaelwastaken/fast3895-clickhouse)](https://hub.docker.com/r/rafaelwastaken/fast3895-clickhouse)

A Sagemcom F@ST3895 (Claro) exporter for ClickHouse

## Requirements
Python requirements are listed in `requirements.txt`.

## Environment Variables ##
Configuration is done via environment variables. Any values with "N/A" default are required.

|  Name  | Description | Type | Default | Example |
| ------ | ----------- | ---- | ------- | ------- |
| LOG_LEVEL | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | str | INFO | INFO |
| MODEM_NAME | Modem name | str | fast3895 | fast3895 |
| MODEM_URL | Modem URL | str | N/A | http://192.168.100.1 |
| MODEM_USERNAME | Modem login username | str | N/A | CLARO_12345 |
| MODEM_PASSWORD | Modem login password | str | N/A | 1234567890 |
| SCRAPE_DELAY | Modem status scrape delay in seconds (minimum 1) | int | 30 | 30 |
| CLICKHOUSE_URL | ClickHouse URL | str | N/A | https://10.0.0.1:8123 |
| CLICKHOUSE_USERNAME | ClickHouse login username | str | N/A | exporter |
| CLICKHOUSE_PASSWORD | ClickHouse login password | str | N/A | hunter2 |
| CLICKHOUSE_DATABASE | ClickHouse database name | str | N/A | metrics |
| CLICKHOUSE_TABLE | ClickHouse modem stats table name | str | fast3895 | fast3895_buffer |
| CLICKHOUSE_QUEUE_LIMIT | Max number of data waiting to be inserted to ClickHouse (minimum 25) | int | 1000 | 1000 |