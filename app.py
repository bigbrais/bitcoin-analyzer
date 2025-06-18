from flask import Flask, jsonify, redirect
import requests
import re
from mnemonic import Mnemonic
import bip32utils

app = Flask(__name__)

# === Настройки ===
SATOSHIS_PER_BTC = 1e8
mnemo = Mnemonic("english")

# === Генерация Bitcoin-адресов из мнемоники ===
def generate_bitcoin_addresses():
    mnemonic = mnemo.generate(strength=128)
    seed = mnemo.to_seed(mnemonic)
    root_key = bip32utils.BIP32Key.fromEntropy(seed)

    addresses = []
    for i in range(3):  # m/44'/0'/0'/0/0 ... m/44'/0'/0'/0/2
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


# === Проверка баланса через blockchair.com ===
def check_balance(address):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://api.blockchair.com/bitcoin/address/{address}" 
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"[Ошибка] HTTP {response.status_code} для {address}")
            return 0.0

        try:
            data = response.json()
            balance = float(data['data'][address]['balance']) / SATOSHIS_PER_BTC
            return balance
        except (ValueError, KeyError, TypeError) as e:
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


# === Маршрут для главной страницы (чтобы не было 404) ===
@app.route("/")
def home():
    return "<h1>Bitcoin Анализатор работает</h1><p>API доступен по /api/check</p>"


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
    port = int(os.environ.get("PORT", 10000))  # Render использует PORT=10000
    app.run(host="0.0.0.0", port=port)
