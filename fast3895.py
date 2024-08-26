import random
import aiochclient
import aiohttp
import asyncio
import colorlog
import datetime
import hashlib
import json
import logging
import os
import re
import signal
import sys

from time import perf_counter

log = logging.getLogger('fast3895')

class FAST3895:
    def __init__(self, loop):
        # Setup logging
        self._setup_logging()
        # Load environment variables
        self._load_env_vars()

        # Event loop
        self.loop = loop

        # Queue of data waiting to be inserted into ClickHouse
        self.clickhouse_queue = asyncio.Queue(maxsize=self.clickhouse_queue_limit)

        # Modem requests counter
        self.modem_request_counter: int = 0
        # Modem session SHA512 auth key
        self.modem_session_auth_key: str = ''
        # Modem session nonce
        self.modem_session_nonce: int = 0
        # Modem session ID
        self.modem_session_id: str = ''

        # Event used to stop the loop
        self.stop_event = asyncio.Event()

    def _setup_logging(self):
        """
            Sets up logging colors and formatting
        """
        # Create a new handler with colors and formatting
        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt={
                'DEBUG': '{log_color}{asctime} [{levelname}] {message}',
                'INFO': '{log_color}{asctime} [{levelname}] {message}',
                'WARNING': '{log_color}{asctime} [{levelname}] {message}',
                'ERROR': '{log_color}{asctime} [{levelname}] {message}',
                'CRITICAL': '{log_color}{asctime} [{levelname}] {message}',
            },
            log_colors={
                'DEBUG': 'blue',
                'INFO': 'white',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bg_red',
            },
            style='{',
            datefmt='%d/%m/%Y %H:%M:%S'
        ))
        # Add the new handler
        logging.getLogger('fast3895').addHandler(shandler)
        log.debug('Finished setting up logging')

    def _load_env_vars(self):
        """
            Loads environment variables and sets defaults
        """
        # Modem name (str, default: "FAST3895")
        self.modem_name = os.environ.get('MODEM_NAME', 'FAST3895')

        # Handle required environment variables
        try:
            # Modem URL (str)
            self.modem_url = os.environ['MODEM_URL']
            # Modem username (str)
            self.modem_username = os.environ['MODEM_USERNAME']
            # Modem password (str)
            self.modem_password = os.environ['MODEM_PASSWORD']
            # ClickHouse URL (str)
            self.clickhouse_url = os.environ['CLICKHOUSE_URL']
            # ClickHouse username (str)
            self.clickhouse_username = os.environ['CLICKHOUSE_USERNAME']
            # ClickHouse password (str)
            self.clickhouse_password = os.environ['CLICKHOUSE_PASSWORD']
            # ClickHouse database (str)
            self.clickhouse_database = os.environ['CLICKHOUSE_DATABASE']
        except KeyError as e:
            log.critical(f'Missing environment variable: {e}')
            exit(1)

        # ClickHouse table name (str, default: "docsis")
        self.clickhouse_table = os.environ.get('CLICKHOUSE_TABLE', 'docsis')

        # Scrape delay (int, default: 10)
        try:
            self.scrape_delay = int(os.environ.get('SCRAPE_DELAY', 10))
            # Make sure the scrape delay is at least 1 second
            if self.scrape_delay < 1:
                raise ValueError
        except ValueError:
            log.critical('Invalid SCRAPE_DELAY, must be a valid number >= 1')
            exit(1)

        # ClickHouse queue limit (int, default: 1000)
        try:
            self.clickhouse_queue_limit = int(os.environ.get('CLICKHOUSE_QUEUE_LIMIT', 1000))
            # Make sure the queue limit is at least 25
            if self.clickhouse_queue_limit < 25:
                raise ValueError
        except ValueError:
            log.critical('Invalid CLICKHOUSE_QUEUE_LIMIT, must be a valid number >= 25')
            exit(1)

        try:
            log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
            if log_level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
                raise ValueError
        except ValueError:
            log.critical('Invalid LOG_LEVEL, must be a valid log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
            exit(1)

        # Set the log level
        log.setLevel({'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}[log_level])

    async def insert_into_clickhouse(self):
        """
            Insert queue'd data into ClickHouse
        """
        while True:
            try:
                # Get the data from the queue
                data = await self.clickhouse_queue.get()
                log.debug(f'Inserting data into ClickHouse: {data}')
                # Insert the data into ClickHouse
                await self.clickhouse.execute(
                    data[0],
                    data[1]
                )
            except RuntimeError:
                break
            except Exception as e:
                log.exception(f'Failed to insert data into ClickHouse: {e}')
                # Wait before we retry inserting
                await asyncio.sleep(5)

    def get_request_id(self) -> int:
        """
        Gets the current request ID

        Returns:
            int: current request ID
        """
        # Increment the requests counter
        self.modem_request_counter += 1
        return self.modem_request_counter

    def get_nonce(self) -> int:
        """
        Generates a random 8-bit nonce integer

        Returns:
            int: nonce
        """
        # Generate a random u8 number
        return random.randint(10000000, 100000000)
        
    def get_sha512_auth_key(self, username: str, password: str, request_id: int, nonce: int, initial_login: bool=False) -> str:
        """
        Generates a SHA512 auth key for the modem
        Used only for initial login

        Args:
            username (str): modem username
            password (str): modem password
            request_id (int): current request ID
            nonce (int): nonce number
            login_nonce (bool, optional): Whether this is an initial login hash. Defaults to False.

        Returns:
            str: Hashed auth-key
        """
        log.debug(f'Generating SHA512 hash with variables username={username}, password={password}, request_id={request_id}, nonce={nonce}')
        # SHA512 hash the password
        hashed_password = hashlib.sha512(password.encode()).hexdigest()
        # SHA512 hash "username:nonce:password hash"
        # The nonce is not used here for the initial login hash
        hashed_login = hashlib.sha512(f'{username}:{nonce if not initial_login else ""}:{hashed_password}'.encode()).hexdigest()
        # SHA512 hash "hashed login:request id:nonce:JSON:/cgi/json-req"
        # If nonce is null, assume we're logging in and generate one for the auth key
        auth_key = hashlib.sha512(f'{hashed_login}:{request_id}:{nonce}:JSON:/cgi/json-req'.encode()).hexdigest()
        log.debug(f'Generated SHA512 auth key: {auth_key}')
        return auth_key
    
    async def login(self):
        log.info('Logging in...')
        # Reset the modem requests counter
        self.modem_request_counter = 0

        nonce = self.get_nonce()
        # Generate a SHA512 auth key for the modem
        self.modem_session_auth_key = auth_key = self.get_sha512_auth_key(
            username=self.modem_username,
            password=self.modem_password,
            request_id=0,
            nonce=nonce,
            initial_login=True
        )

        payload = {
            'request': {
                'id': 0,
                'session-id': '0',
                'priority': True,
                'actions': [
                    {
                        'id': 0,
                        'method': 'logIn',
                        'parameters': {
                            'user': self.modem_username,
                            'persistent': 'true',
                            'session-options': {
                                'nss': [
                                    {
                                        'name': 'gtw',
                                        'uri': 'http://sagemcom.com/gateway-data'
                                    }
                                ],
                                'language': 'ident',
                                'context-flags': {
                                    'get-content-name': True,
                                    'local-time': True
                                },
                                'capability-depth': 2,
                                'capability-flags': {
                                    'name': True,
                                    'default-value': False,
                                    'restriction': True,
                                    'description': False
                                },
                                'time-format': 'ISO_8601',
                                'jwt-auth': 'true'
                            }
                        }
                    }
                ],
                'cnonce': nonce,
                'auth-key': auth_key
            }
        }

        async with self.session.post(
            f'{self.modem_url}/cgi/json-req',
            data=f'req={json.dumps(payload)}'
        ) as resp:
            log.debug(f'Got login response HTTP {resp.status} {resp.reason}: {await resp.text()}')
            if resp.status != 200:
                log.error(f'Failed to login, got HTTP {resp.status} {resp.reason}')
                sys.exit(1)
            login_response = await resp.json()

        if login_response['reply']['error']['description'] != 'XMO_REQUEST_NO_ERR':
            log.error(f'Failed to login, invalid modem username or password')
            sys.exit(1)

        # Store the returned nonce and session ID
        # These are used for future requests
        self.modem_session_nonce: int = login_response['reply']['actions'][0]['callbacks'][0]['parameters']['nonce']
        self.modem_session_id: str = f'{login_response["reply"]["actions"][0]["callbacks"][0]["parameters"]["id"]}'
        log.info('Logged in')
        log.debug(f'Logged in, got session ID {self.modem_session_id} and nonce {self.modem_session_nonce}')

    async def export_modem_stats(self):
        # Generate an initial session
        try:
            await self.login()
        except SystemExit:
            self.stop_event.set()
            return
        except Exception as e:
            log.error(f'Failed to login: {type(e).__name__}: {e}')
            self.stop_event.set()
            return
        
        while True:
            try:
                request_id = self.get_request_id()
                auth_key = self.get_sha512_auth_key(
                    self.modem_username,
                    self.modem_password,
                    request_id,
                    self.modem_session_nonce
                )

                start = perf_counter()

                payload = {
                    'request': {
                        'id': request_id,
                        'session-id': self.modem_session_id,
                        'priority': False,
                        'actions': [
                            {
                                'id': 0,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/BuildDate',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 1,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/MemoryStatus',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 2,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/Manufacturer',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 3,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/ModelName',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 4,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/ProcessStatus',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 5,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/SoftwareVersion',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 6,
                                'method': 'getValue',
                                'xpath': 'Device/DeviceInfo/UpTime',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 7,
                                'method': 'getValue',
                                'xpath': 'Device/Docsis/CableModem/Downstreams',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            },
                            {
                                'id': 8,
                                'method': 'getValue',
                                'xpath': 'Device/Docsis/CableModem/Upstreams',
                                'options': {
                                    'capability-flags': {
                                        'interface': True
                                    }
                                }
                            }
                        ],
                        'cnonce': self.modem_session_nonce,
                        'auth-key': auth_key
                    }
                }
                log.debug(f'Sending payload to modem: {payload}')

                async with self.session.post(
                    f'{self.modem_url}/cgi/json-req',
                    data=f'req={json.dumps(payload)}'
                ) as resp:
                    log.debug(f'Got modem status response HTTP {resp.status} {resp.reason}: {await resp.text()}')
                    modem_response = await resp.json()

                # Check if the modem returned an error
                if modem_response['reply']['error']['description'] != 'XMO_REQUEST_NO_ERR':
                    # We likely need to re-login
                    # Wait a bit before re-logging in to prevent spamming
                    await asyncio.sleep(self.scrape_delay)
                    log.error(f'Failed to get modem stats, re-logging in')
                    await self.login()
                    continue

                scrape_latency = perf_counter() - start

                log.info(f'Scraped modem stats in {scrape_latency:.2f}s')

                downstream_channels = []
                for channel in modem_response['reply']['actions'][7]['callbacks'][0]['parameters']['value']:
                    downstream_channels.append([(
                        channel['ChannelID'],
                        channel['Frequency'],
                        channel['Modulation'],
                        channel['SymbolRate'],
                        channel['BandWidth'],
                        channel['PowerLevel'],
                        channel['SNR'],
                        channel['UnerroredCodewords'],
                        channel['CorrectableCodewords'],
                        channel['UncorrectableCodewords']
                    )])

                upstream_channels = []
                for channel in modem_response['reply']['actions'][8]['callbacks'][0]['parameters']['value']:
                    upstream_channels.append([(
                        channel['ChannelID'],
                        channel['Frequency'],
                        channel['Modulation'],
                        channel['SymbolRate'],
                        channel['PowerLevel']
                    )])

                data = [
                    self.modem_name,
                    modem_response['reply']['actions'][6]['callbacks'][0]['parameters']['value'], # Uptime
                    f'{modem_response["reply"]["actions"][5]["callbacks"][0]["parameters"]["value"]} {modem_response["reply"]["actions"][0]["callbacks"][0]["parameters"]["value"]}', # Software version + build date
                    f'{modem_response["reply"]["actions"][2]["callbacks"][0]["parameters"]["value"]} {modem_response["reply"]["actions"][3]["callbacks"][0]["parameters"]["value"]}', # Manufacturer + model name
                    modem_response['reply']['actions'][4]['callbacks'][0]['parameters']['value']['ProcessStatus']['CPUUsage'], # CPU usage
                    modem_response['reply']['actions'][4]['callbacks'][0]['parameters']['value']['ProcessStatus']['LoadAverage']['Load1'], # Load average 1 min
                    modem_response['reply']['actions'][4]['callbacks'][0]['parameters']['value']['ProcessStatus']['LoadAverage']['Load5'], # Load average 5 min
                    modem_response['reply']['actions'][4]['callbacks'][0]['parameters']['value']['ProcessStatus']['LoadAverage']['Load15'], # Load average 15 min
                    modem_response['reply']['actions'][1]['callbacks'][0]['parameters']['value']['MemoryStatus']['Total'], # Total memory
                    modem_response['reply']['actions'][1]['callbacks'][0]['parameters']['value']['MemoryStatus']['Free'], # Free memory
                    downstream_channels, # Downstream channels
                    upstream_channels, # Upstream channels
                    scrape_latency, # Scrape latency
                    datetime.datetime.now(tz=datetime.timezone.utc).timestamp() # Current UTC timestamp
                ]

                # Add the data to the ClickHouse queue
                await self.clickhouse_queue.put((
                    f"""
                    INSERT INTO {self.clickhouse_table} (
                        modem_name,
                        uptime,
                        version,
                        model,
                        cpu_usage,
                        load_average_1,
                        load_average_5,
                        load_average_15,
                        total_memory,
                        free_memory,
                        downstream_channels,
                        upstream_channels,
                        scrape_latency,
                        timestamp
                    ) VALUES
                    """,
                    data
                ))
            except RuntimeError:
                return
            except Exception as e:
                log.error(f'Failed to get modem stats: {type(e).__name__}: {e}')

            # Wait before we scrape again
            await asyncio.sleep(self.scrape_delay)

    async def run(self):
        # Create a ClientSession that doesn't verify SSL certificates
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        )
        self.clickhouse = aiochclient.ChClient(
            self.session,
            url=self.clickhouse_url,
            user=self.clickhouse_username,
            password=self.clickhouse_password,
            database=self.clickhouse_database,
            json=json
        )
        # Cookies used for auth
        self.cookies = {}

        # Start the ClickHouse insert task
        insert_task = self.loop.create_task(self.insert_into_clickhouse())

        # Start the exporter in a background task
        export_task = self.loop.create_task(self.export_modem_stats())

        # Wait for the stop event
        await self.stop_event.wait()

        # Close the aiohttp session
        await self.session.close()

        # Cancel the exporter task
        export_task.cancel()
        # Cancel the ClickHouse insert task
        insert_task.cancel()

loop = asyncio.new_event_loop()
exporter = FAST3895(loop)

def sigterm_handler(_signo, _stack_frame):
    """
        Handle SIGTERM
    """
    # Set the event to stop the loop
    exporter.stop_event.set()
# Register the SIGTERM handler
signal.signal(signal.SIGTERM, sigterm_handler)

try:
    loop.run_until_complete(exporter.run())
except KeyboardInterrupt:
    exporter.stop_event.set()