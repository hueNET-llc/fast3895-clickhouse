-- PLEASE NOTE
-- The buffer tables are what I personally use to do buffer and batch inserts
-- You may have to modify them to work in your setup

CREATE TABLE fast3895 (
        modem_name LowCardinality(String), -- Modem name
        uptime UInt32, -- Modem uptime
        version LowCardinality(String), -- Modem version
        model LowCardinality(String), -- Modem model
        cpu_usage UInt8, -- Modem CPU usage
        load_average_1 Float32, -- Modem load average (1 min)
        load_average_5 Float32, -- Modem load average (5 min)
        load_average_15 Float32, -- Modem load average (15 min)
        total_memory UInt32, -- Modem total memory (KB)
        free_memory UInt32, -- Modem free memory (KB)
        downstream_channels Array(Nested( -- Array of downstream channels
            channel_id UInt8, -- Downstream channel ID
            frequency Float32, -- Downstream frequency
            modulation LowCardinality(String), -- Downstream modulation
            symbol_rate UInt16, -- Downstream symbol rate (symbols/second)
            bandwidth UInt32, -- Downstream bandwidth/width (Hz)
            power Float32, -- Downstream power
            snr Float32, -- Downstream signal-to-noise ratio
            unerrored_codewords UInt64, -- Downstream unerrored codewords
            correctable_codewords UInt64, -- Downstream correctable codewords
            uncorrectable_codewords UInt64, -- Downstream uncorrectable codewords
            -- Some modems (MB8600) have overflow bugs so we need to store error counters signed
        )),
        upstream_channels Array(Nested( -- Array of upstream channels
            channel_id UInt8, -- Upstream channel ID
            frequency Float32, -- Upstream frequency
            modulation LowCardinality(String), -- Upstream modulation
            symbol_rate UInt16, -- Upstream width
            power Float32, -- Upstream power
        )),
        scrape_latency Float32, -- Modem scrape latency
        timestamp DateTime DEFAULT now() -- Data timestamp
) ENGINE = MergeTree() PARTITION BY toDate(timestamp) ORDER BY (modem_name, timestamp) PRIMARY KEY (modem_name, timestamp);

CREATE TABLE fast3895_buffer (
        modem_name LowCardinality(String), -- Modem name
        uptime UInt32, -- Modem uptime
        version LowCardinality(String), -- Modem version
        model LowCardinality(String), -- Modem model
        cpu_usage UInt8, -- Modem CPU usage
        load_average_1 Float32, -- Modem load average (1 min)
        load_average_5 Float32, -- Modem load average (5 min)
        load_average_15 Float32, -- Modem load average (15 min)
        total_memory UInt32, -- Modem total memory (KB)
        free_memory UInt32, -- Modem free memory (KB)
        downstream_channels Array(Nested( -- Array of downstream channels
            channel_id UInt8, -- Downstream channel ID
            frequency Float32, -- Downstream frequency
            modulation LowCardinality(String), -- Downstream modulation
            symbol_rate UInt16, -- Downstream symbol rate (symbols/second)
            bandwidth UInt32, -- Downstream bandwidth/width (Hz)
            power Float32, -- Downstream power
            snr Float32, -- Downstream signal-to-noise ratio
            unerrored_codewords UInt64, -- Downstream unerrored codewords
            correctable_codewords UInt64, -- Downstream correctable codewords
            uncorrectable_codewords UInt64, -- Downstream uncorrectable codewords
            -- Some modems (MB8600) have overflow bugs so we need to store error counters signed
        )),
        upstream_channels Array(Nested( -- Array of upstream channels
            channel_id UInt8, -- Upstream channel ID
            frequency Float32, -- Upstream frequency
            modulation LowCardinality(String), -- Upstream modulation
            symbol_rate UInt16, -- Upstream width
            power Float32, -- Upstream power
        )),
        scrape_latency Float32, -- Modem scrape latency
        timestamp DateTime DEFAULT now() -- Data timestamp
    ) ENGINE = Buffer(homelab, fast3895, 1, 10, 10, 10, 100, 10000, 10000);
