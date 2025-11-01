from flask import Flask, request, jsonify
import requests
import json
import time
from byte import Encrypt_ID, encrypt_api  # pastikan file ini ada

app = Flask(__name__)

def load_tokens():
    """Load token dari file token_bd.json"""
    try:
        with open("token_bd.json", "r") as file:
            data = json.load(file)
        tokens = [item["token"] for item in data]
        return tokens
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

def send_friend_request(uid, token, results):
    """Kirim request AddingFriend"""
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
            "ReleaseVersion": "OB51",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-N975F Build/PI)",
            "Host": "clientbp.ggblueshark.com",
            "Connection": "close",
            "Accept-Encoding": "gzip, deflate, br"
        }

        # Kirim request dan tunggu selesai
        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=8)

        if response.status_code == 200:
            results["success"] += 1
            print(f"✅ Success ({results['success']})")
        else:
            results["failed"] += 1
            print(f"❌ Failed ({response.status_code})")

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

    print(f"Starting friend requests for UID: {uid} ({len(tokens)} tokens loaded)\n")

    for i, token in enumerate(tokens[:110], start=1):
        start_time = time.time()

        print(f"🔹 Sending request {i}/{len(tokens[:110])} ...")
        send_friend_request(uid, token, results)

        # Pastikan tiap loop berlangsung minimal 1 detik
        elapsed = time.time() - start_time
        delay = max(0, 1 - elapsed)
        time.sleep(delay)

    status = 1 if results["success"] > 0 else 2

    print("\n✅ All done.")
    print(f"Success: {results['success']} | Failed: {results['failed']}")

    return jsonify({
        "success_count": results["success"],
        "failed_count": results["failed"],
        "status": status
    })

if __name__ == "__main__":
    # Penting: matikan threading agar eksekusi sequential, tidak paralel
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=False)
