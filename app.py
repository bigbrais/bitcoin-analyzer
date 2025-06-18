from flask import Flask, jsonify
import time
import requests
import re
from mnemonic import Mnemonic
import bip32utils

app = Flask(__name__, static_folder='static', static_url_path='')

mnemo = Mnemonic("english")
SATOSHIS_PER_BTC = 1e8

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

def check_balance(address):
    try:
        url = f"https://api.blockchair.com/bitcoin/address/{address}" 
        response = requests.get(url, timeout=10)
        data = response.json()
        balance = data['data'][address]['balance'] / SATOSHIS_PER_BTC
        return balance
    except Exception as e:
        print(f"[Ошибка] Не удалось проверить баланс для {address}: {e}")
        return 0.0

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

    return jsonify({"mnemonic": mnemonic, "addresses": results})

# Главная страница (для теста)
@app.route("/")
def index():
    return app.send_static_file('index.html')

if __name__ == "__main__":
    app.run(debug=True)