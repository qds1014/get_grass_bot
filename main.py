import asyncio
import random
import ssl
import json
import time
import uuid
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent
ip_retry_count = {}
user_agent = UserAgent()
max_retries = 5
async def connect_to_wss(socks5_proxy, user_id, random_user_agent):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(device_id)
    ip_retry_count[device_id] = 0
    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg",
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            uri = "wss://proxy.wynd.network:4444/"
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(send_message)
                        await websocket.send(send_message)
                        await asyncio.sleep(15)

                send_ping_task = asyncio.create_task(send_ping())
                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(message)
                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": custom_headers['User-Agent'],
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "4.0.1"
                            }
                        }
                        logger.debug(auth_response)
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(pong_response)
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            ip_retry_count[device_id] += 1
            logger.error(f"Error with proxy {socks5_proxy}: {str(e)} (Retry {ip_retry_count[device_id]}/{max_retries})")
            if ip_retry_count[device_id] > max_retries:
                logger.error(f"Max retries exceeded for proxy {socks5_proxy}. Removing it.")
                remove_error_proxy(socks5_proxy)
                del ip_retry_count[device_id]
                return None
            continue


async def main():
    _user_id = "PRINTED TEXT IS THE USER_ID"  # Replace Your User ID HERE
    proxy_file = 'proxy.txt'  # your Path to Proxy3.txt file
    # formate => socks5://username:pass@ip:port
    with open(proxy_file, 'r') as file:
        all_proxies = file.read().splitlines()

    active_proxies = random.sample(all_proxies, 5)  # write the number of proxy you wana use
    tasks = {asyncio.create_task(connect_to_wss(proxy, _user_id, user_agent.random)): proxy for proxy in active_proxies}

    while True:
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.result() is None:
                failed_proxy = tasks[task]
                logger.info(f"Removing and replacing failed proxy: {failed_proxy}")
                active_proxies.remove(failed_proxy)
                new_proxy = random.choice(all_proxies)
                active_proxies.append(new_proxy)
                new_task = asyncio.create_task(connect_to_wss(new_proxy, _user_id, user_agent.random))
                tasks[new_task] = new_proxy  # Replace the task in the dictionary
            tasks.pop(task)  # Remove the completed task whether it succeeded or failed
        # Replenish the tasks if any have completed
        for proxy in set(active_proxies) - set(tasks.values()):
            random_user_agent = user_agent.random
            new_task = asyncio.create_task(connect_to_wss(proxy, _user_id, random_user_agent))
            tasks[new_task] = proxy


def remove_error_proxy(proxy):
    with open("proxy.txt", "r+") as file:
        lines = file.readlines()
        file.seek(0)
        for line in lines:
            if line.strip() != proxy:
                file.write(line)
        file.truncate()


if __name__ == '__main__':
    asyncio.run(main())

