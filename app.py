from flask import Flask, request, jsonify
import requests
import json
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from byte import Encrypt_ID, encrypt_api

app = Flask(__name__)

def load_tokens():
    try:
        with open("spam_ind.json", "r") as file:
            data = json.load(file)
        tokens = [item["token"] for item in data]
        return tokens
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

def send_friend_request(uid, token, session, retries=2, backoff_factor=0.5):
    """
    Mengirim satu request untuk token tertentu. Mengembalikan True jika sukses, False jika gagal.
    retries: jumlah retry setelah kegagalan
    backoff_factor: faktor untuk exponential backoff (detik)
    """
    try:
        encrypted_id = Encrypt_ID(uid)
        payload = f"08a7c4839f1e10{encrypted_id}1801"
        encrypted_payload = encrypt_api(payload)

        url = "https://clientbp.ggwhitehawk.com/RequestAddingFriend"
        headers = {
            "Expect": "100-continue",
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB50",
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": "16",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-N975F Build/PI)",
            "Host": "clientbp.ggwhitehawk.com",
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate, br"
        }

        attempt = 0
        while attempt <= retries:
            try:
                # gunakan session.post dengan timeout
                response = session.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=10)
                if response.status_code == 200:
                    return True
                else:
                    # bisa log detail jika perlu
                    # print(f"Token {token[:6]}... status {response.status_code}")
                    attempt += 1
                    if attempt <= retries:
                        sleep_time = backoff_factor * (2 ** (attempt - 1))
                        time.sleep(sleep_time)
            except requests.RequestException as e:
                attempt += 1
                if attempt <= retries:
                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                else:
                    # final failure
                    return False

        return False
    except Exception as e:
        # jika Encrypt_ID / encrypt_api error
        print(f"Error sending for token {token[:6]}... : {e}")
        return False

@app.route("/send_requests", methods=["GET"])
def send_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "uid parameter is required"}), 400

    # optional params with defaults
    try:
        delay = float(request.args.get("delay", 0.2))       # rata-rata jeda (detik) antar start task
        jitter = float(request.args.get("jitter", 0.05))    # variasi +/- (detik)
        max_workers = int(request.args.get("max_workers", 5))  # concurrency
        limit = int(request.args.get("limit", 110))         # token limit
        retries = int(request.args.get("retries", 2))       # retry per request
        backoff = float(request.args.get("backoff", 0.5))   # backoff factor (detik)
    except ValueError:
        return jsonify({"error": "Invalid numeric parameter"}), 400

    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens found in spam_ind.json"}), 500

    tokens = tokens[:max(0, min(limit, len(tokens)))]

    results = {"success": 0, "failed": 0}
    futures = []

    # gunakan satu session per worker untuk efisiensi
    session = requests.Session()

    # ThreadPoolExecutor mengatur concurrency
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for token in tokens:
            # sebelum submit, tunggu delay dengan jitter agar tidak semua start bersamaan
            actual_delay = max(0, delay + random.uniform(-jitter, jitter))
            time.sleep(actual_delay)

            # submit job (jangan lupa untuk mengirim parameter retry/backoff)
            futures.append(executor.submit(send_friend_request, uid, token, session, retries, backoff))

        # tunggu semua selesai dan kumpulkan hasil
        for future in as_completed(futures):
            try:
                ok = future.result()
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1

    session.close()

    status = 1 if results["success"] != 0 else 2

    return jsonify({
        "success_count": results["success"],
        "failed_count": results["failed"],
        "status": status
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)