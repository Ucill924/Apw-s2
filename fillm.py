import requests
from eth_account import Account
from eth_account.messages import encode_defunct
from fake_useragent import UserAgent
from colorama import Fore, init
import time
import random
import json
from datetime import datetime, timezone
import re
from web3 import Web3
init(autoreset=True)


ua = UserAgent()
rpc_url = "https://polygon-rpc.com"
chain_id = 137
contract_address = "0xa4d2DBee009029f2f8778119a74C0A00416074A8"
method_id = "0x183ff085"
value_eth = 0.02

w3 = Web3(Web3.HTTPProvider(rpc_url))
if w3.is_connected():
    print(Fore.GREEN + "✅ Successfully connected to ApeChain.")
else:
    print(Fore.RED + "❌ Failed to connect to ApeChain.")

def load_proxies(file_path='proxies.txt'):
    try:
        with open(file_path, 'r') as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except FileNotFoundError:
        print(Fore.RED + f"❌ File '{file_path}' tidak ditemukan!")
        return []
    
    
def get_proxy(proxies):
    if proxies:
        proxy = random.choice(proxies)
        return {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
    return None

def get_wallets_from_pk(file_path):
    try:
        with open(file_path, 'r') as file:
            private_keys = [line.strip() for line in file if line.strip()]
        return [(Account.from_key(pk).address, pk) for pk in private_keys]
    except FileNotFoundError:
        print(Fore.RED + f"❌ File '{file_path}' tidak ditemukan!")
        exit()

def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def get_nonce(proxies):
    url = "https://evm-api.pulsar.money/auth/nonce"
    headers = {
        "accept": "application/json",
        "user-agent": ua.random
    }
    try:
        response = requests.get(url, headers=headers, proxies=proxies)
        response.raise_for_status()

        nonce = response.text.strip()
        set_cookie = response.headers.get('Set-Cookie', '')
        connect_sid_match = re.search(r'connect\.sid=([^;]+)', set_cookie)
        connect_sid = connect_sid_match.group(1) if connect_sid_match else None
        timestamp = get_timestamp()
        return nonce, timestamp, connect_sid
    except requests.RequestException as e:
        print(Fore.RED + f"❌ Gagal mendapatkan nonce: {str(e)}")
        return None, None, None

def create_sign_message(address, nonce, timestamp):
    if not nonce or not timestamp:
        print(Fore.RED + "❌ Nonce atau timestamp tidak valid!")
        return None
    message = (
        "app.pulsar.money wants you to sign in with your Ethereum account:\n"
        f"{address}\n\n"
        "I Love Pulsar Money.\n\n"
        "URI: https://app.pulsar.money\n"
        "Version: 1\n"
        "Chain ID: 8453\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {timestamp}"
    )
    return message

def sign_message(private_key, message):
    try:
        message_encoded = encode_defunct(text=message)
        signed_message = Account.sign_message(message_encoded, private_key)
        return signed_message.signature.hex()
    except Exception as e:
        print(Fore.RED + f"❌ Error saat menandatangani pesan: {str(e)}")
        return None

def register_wallet(wallet_address, private_key, proxies):
    nonce, timestamp, connect_sid = get_nonce(proxies)
    if not nonce or not connect_sid:
        print(Fore.RED + f"[{wallet_address}] Gagal mendapatkan nonce atau connect.sid!")
        return None

    message = create_sign_message(wallet_address, nonce, timestamp)
    if not message:
        return None

    signature = sign_message(private_key, message)
    if not signature:
        return None

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "cookie": f"connect.sid={connect_sid}",
        "user-agent": ua.random
    }
    payload = {"message": message, "signature": "0x" + signature}
    url = "https://evm-api.pulsar.money/auth/verify"

    try:
        response = requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=10)
        response.raise_for_status()

        print(Fore.GREEN + f"[{wallet_address}] ✅ login sukses!")
        return connect_sid
    except requests.RequestException as e:
        print(Fore.RED + f"[{wallet_address}] ❌ Gagal login: {str(e)}")
        return None

def daily(account_address, private_key, connect_sid):
    try:
        account_nonce = w3.eth.get_transaction_count(account_address)
        value_wei = w3.to_wei(value_eth, 'ether')

        transaction = {
            'to': contract_address,
            'data': method_id,
            'value': value_wei,
            'gas': 100000,
            'maxFeePerGas': w3.to_wei(34, 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei(34, 'gwei'),
            'nonce': account_nonce,
            'chainId': chain_id
        }

        signed_tx = w3.eth.account.sign_transaction(transaction, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(Fore.YELLOW + f"[{account_address}] ⏳ Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt and receipt.get('status') == 1:
            print(Fore.GREEN + f"[{account_address}] ✅ Transaction successful! Hash: {tx_hash.hex()}")
            do_task(account_address, connect_sid, proxies)
        else:
            print(Fore.RED + f"[{account_address}] ❌ Transaction failed. Receipt: {receipt}")
        return receipt
    except TimeoutError:
        print(Fore.RED + f"[{account_address}] ⏳ Transaction timed out. Please check on the blockchain.")
    except ValueError as e:
        print(Fore.RED + f"[{account_address}] ❗ Transaction error: {e}")
    except Exception as e:
        print(Fore.RED + f"[{account_address}] ⚠️ Unexpected error: {type(e).__name__}: {e}")


def do_task(account_address, connect_sid, proxies, choice=None):
    print(Fore.CYAN + f"🔄 Running tasks for account: {account_address}")
    proxy = get_proxy(proxies)
    url = "https://evm-api.pulsar.money/challenges/do-task"
    headers = {
        "accept": "application/json, text/plain, */*",
        "cookie": f"connect.sid={connect_sid}",
        "content-type": "application/json",
        "user-agent": ua.random
    }

    all_tasks = [
    {"taskGuid": "a09765ae-5704-42ab-b830-c1d9caec968c", "extraArguments": []},
    {"taskGuid": "af59ab9a-eb21-4b7f-b2b3-44ce40cd0805", "extraArguments": []},
    {"taskGuid": "0d6ceb85-343f-4d07-a472-cf495304a349", "extraArguments": []},
    {"taskGuid": "64e554ef-5721-41e9-86a0-adec6a7f137a", "extraArguments": []},
    {"taskGuid": "2cdd20ee-167c-43c0-99d7-c4d54a8e4067", "extraArguments": []},
    {"taskGuid": "c0c76c23-d536-4240-bd9f-5b8573ec4ffa", "extraArguments": []},
    {"taskGuid": "bfdf87d9-681f-4552-a810-a6f767355aef", "extraArguments": []}, # daily chekin
    {"taskGuid": "06f19cd6-4683-47b8-a5fc-2cb3c1f621cc", "extraArguments": []},
    {"taskGuid": "56aed2e9-74e3-4adb-ac96-e15f8de85389", "extraArguments": []},
    {"taskGuid": "9e45c4bc-de89-410e-9a08-b988188b4114", "extraArguments": []}

]


    if choice == "1":
        tasks = [{"taskGuid": "bfdf87d9-681f-4552-a810-a6f767355aef", "extraArguments": []}]
        print(Fore.CYAN + "▶ Menjalankan mode: Daily Only\n")
    elif choice == "2":
        tasks = all_tasks
        print(Fore.CYAN + "▶ Menjalankan mode: All Tasks\n")
    elif choice == "3":
        tasks = [task for task in all_tasks if task["taskGuid"] != "bfdf87d9-681f-4552-a810-a6f767355aef"]
        print(Fore.CYAN + "▶ Menjalankan mode: All Tasks (tanpa Daily Check-in)\n")
    else:
        print(Fore.RED + "❌ Pilihan tidak valid. Task dibatalkan.")
        return

    for task in tasks:
        try:
            response = requests.post(url, headers=headers, json=task, proxies=proxy, timeout=10)
            response.raise_for_status()
            print(Fore.GREEN + f"✅ Check task : {response.text}")
        except requests.RequestException as e:
            print(Fore.RED + f"❌ Error completing task ({task['taskGuid']}): {str(e)}")
        time.sleep(3)



def check_point(account_address, connect_sid, proxies):
    print(Fore.CYAN + f"🔄 Checking points for account: {account_address}")
    proxy = get_proxy(proxies)
    url = "https://evm-api.pulsar.money/challenges/film/me"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "cookie": f"connect.sid={connect_sid}",
        "content-type": "application/json",
        "user-agent": ua.random,
        "if-none-match": 'W/"298-NHKmiaMV038CYQXQkOb4Sw4nlck"'
    }

    try:
        response = requests.get(url, headers=headers, proxies=proxy, timeout=10)
        response.raise_for_status()
        data = response.json() 
        total_points = data.get("totalPoints", "0")
        rank = data.get("rank", "N/A")
        is_eligible = data.get("eligibility", {}).get("isEligible", False)
        onchain = data.get("eligibility", {}).get("requirements", {}).get("onchain", False)
        print(Fore.GREEN + f"🏆 Rank        : {rank}")
        print(Fore.GREEN + f"🔗 Onchain     : {onchain}")
        print(Fore.GREEN + f"✅ isEligible  : {is_eligible}")
        print(Fore.GREEN + f"💰 Total Points: {total_points}")

    except requests.RequestException as e:

        print(Fore.RED + f"❌ Error checking points: {str(e)}")
file_path = "pk-film.txt"
if __name__ == "__main__":
    while True:  
        start_time = datetime.now()
        print(Fore.MAGENTA + f"\n🚀 Mulai proses pada {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        proxies = load_proxies('proxies.txt')
        wallets = get_wallets_from_pk(file_path)
        print(Fore.YELLOW + "\nPilih mode task:")
        print("1. Daily only")
        print("2. All tasks")
        print("3. Task only no daily tx")
        choice = input(Fore.CYAN + "Masukkan pilihan (1-3): ").strip()

        for account_address, private_key in wallets:
            print(Fore.YELLOW + f"\n📲 Proses wallet: {account_address} pakai proxy: {get_proxy(proxies)}")
            proxy = get_proxy(proxies)
            connect_sid = register_wallet(account_address, private_key, proxy)

            if connect_sid:
                print(Fore.CYAN + f"[{account_address}] 🔥 Melakukan transaksi task...")
                daily(account_address, private_key, connect_sid)
                do_task(account_address, connect_sid, proxies, choice)  # ✅

            sleep_time = random.randint(4, 8)
            print(Fore.GREEN + f"⏳ Sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)

            check_point(account_address, connect_sid, proxies)

        print(Fore.BLUE + "\n⏳ Semua akun selesai. Menunggu 24 jam sebelum menjalankan ulang...\n")
        time.sleep(86400)

