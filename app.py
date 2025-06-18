from flask import Flask, jsonify
import requests
import re
from mnemonic import Mnemonic
import bip32utils

# === Настройки ===
app = Flask(__name__)
SATOSHIS_PER_BTC = 1e8

# 🔐 Укажи свои данные:
TELEGRAM_TOKEN = "ВАШ_ТОКЕН"
TELEGRAM_CHAT_ID = "ВАШ_CHAT_ID"

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


# === Отправка уведомления в Telegram ===
def send_telegram_message(mnemonic, address, private_key, balance):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" 
    text = (
        "💰 *Найден кошелёк с ненулевым балансом!*\n\n"
        f"**Баланс:** {balance:.8f} BTC\n"
        f"**Bitcoin-адрес:** `{address}`\n"
        f"**Приватный ключ:** `{private_key}`\n"
        f"**Мнемоника (12 слов):**\n`{mnemonic}`"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[Ошибка] Не удалось отправить сообщение в Telegram: {e}")


# === Сохранение найденного кошелька и отправка в Telegram ===
def save_and_notify_found_wallet(mnemonic, address, private_key, balance):
    with open("found_wallets.txt", "a", encoding="utf-8") as f:
        f.write(f"Мнемоника: {mnemonic}\n")
        f.write(f"Адрес: {address}\n")
        f.write(f"Приватный ключ: {private_key}\n")
        f.write(f"Баланс: {balance:.8f} BTC\n")
        f.write("-" * 60 + "\n")

    send_telegram_message(mnemonic, address, private_key, balance)


# === API маршрут ===
@app.route("/api/check")
def api_check():
    addresses, mnemonic = generate_bitcoin_addresses()
    results = []

    found_count = 0
    for addr, priv in addresses:
        balance = check_balance(addr)
        results.append({
            "address": addr,
            "private_key": priv,
            "balance": round(balance, 8)
        })

        if balance > 0:
            found_count += 1
            save_and_notify_found_wallet(mnemonic, addr, priv, balance)

    return jsonify({
        "addresses": results,
        "stats": {
            "total_checks": len(results),
            "found_non_zero": found_count
        }
    })


# === Главная страница ===
@app.route("/")
def index():
    return app.send_static_file("index.html")


# === Запуск сервера ===
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
