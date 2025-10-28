from flask import Flask, request, jsonify
import requests
import json
import time
from byte import Encrypt_ID, encrypt_api

app = Flask(__name__)

def load_tokens():
    try:
        with open("token_bd.json", "r") as file:
            data = json.load(file)
        tokens = [item["token"] for item in data]
        return tokens
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

def send_friend_request(uid, token, results):
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
            "Host": "clientbp.ggblueshark.com",
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate, br"
        }

        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload))

        if response.status_code == 200:
            results["success"] += 1
        else:
            results["failed"] += 1
    except Exception as e:
        results["failed"] += 1
        print(f"Error: {e}")

@app.route("/send_requests", methods=["GET"])
def send_requests():
    uid = request.args.get("uid")

    if not uid:
        return jsonify({"error": "uid parameter is required"}), 400

    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens found in token_bd.json"}), 500

    results = {"success": 0, "failed": 0}

    for i, token in enumerate(tokens[:110], start=1):
        send_friend_request(uid, token, results)
        print(f"[{i}] Token processed. Success: {results['success']} | Failed: {results['failed']}")
        time.sleep(1)  # Jeda 1 detik sebelum lanjut ke token berikutnya

    status = 1 if results["success"] != 0 else 2

    return jsonify({
        "success_count": results["success"],
        "failed_count": results["failed"],
        "status": status
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)