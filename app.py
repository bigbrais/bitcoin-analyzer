from flask import Flask, jsonify
import requests
import re
import time
from mnemonic import Mnemonic
import bip32utils

app = Flask(__name__, static_folder='static', static_url_path='')

# === Настройки ===
SATOSHIS_PER_BTC = 1e8
CHECK_BALANCE_URL = "https://api.blockchair.com/bitcoin/address/{address}" 

mnemo = Mnemonic("english")

# === Генерация Bitcoin-адресов из мнемоники ===
def generate_bitcoin_addresses():
    mnemonic = mnemo.generate(strength=128)
    seed = mnemo.to_seed(mnemonic)
    root_key = bip32utils.BIP32Key.fromEntropy(seed)

    addresses = []
    for i in range(3):  # m/44'/0'/0'/0/0, m/44'/0'/0'/0/1, m/44'/0'/0'/0/2
        key = (
            root_key.ChildKey(44 + bip32utils.BIP32_HARDEN)
            .ChildKey(0 + bip32utils.BIP32_HARDEN)
            .ChildKey(0 + bip32utils.BIP32_HARDEN)
            .ChildKey(0)
            .ChildKey(i)
        )
        address = key.Address()
        private_key = key.WalletImportFormat()
        addresses.append((address, private_key))
    return addresses, mnemonic


# === Проверка баланса через API ===
def check_balance(address):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
    }
    try:
        url = CHECK_BALANCE_URL.format(address=address)
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"[Ошибка] HTTP {response.status_code} для {address}")
            return 0.0

        try:
            data = response.json()
            balance = float(data['data'][address]['balance']) / SATOSHIS_PER_BTC
            return balance
        except (ValueError, KeyError) as e:
            print(f"[Ошибка парсинга JSON] для {address}: {e}")
            return 0.0

    except Exception as e:
        print(f"[Ошибка] Не удалось проверить баланс для {address}: {e}")
        return 0.0


# === Сохранение найденного кошелька в файл ===
def save_found_wallet(mnemonic, address, private_key, balance):
    with open("found_wallets.txt", "a", encoding="utf-8") as f:
        f.write(f"Мнемоника: {mnemonic}\n")
        f.write(f"Адрес: {address}\n")
        f.write(f"Приватный ключ: {private_key}\n")
        f.write(f"Баланс: {balance:.8f} BTC\n")
        f.write("-" * 60 + "\n")


# === API маршрут ===
@app.route("/api/check")
def api_check():
    addresses, mnemonic = generate_bitcoin_addresses()
    results = []

    for addr, priv in addresses:
        balance = check_balance(addr)
        results.append({
            "address": addr,
            "private_key": priv,
            "balance": round(balance, 8)
        })

        if balance > 0:
            save_found_wallet(mnemonic, addr, priv, balance)

    return jsonify({"addresses": results})


# === Запуск сервера ===
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
