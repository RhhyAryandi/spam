from flask import Flask, request, jsonify
import json
import threading
import time
import random
import uuid
import asyncio
import aiohttp
from byte import Encrypt_ID, encrypt_api

app = Flask(__name__)

# menyimpan status job di memory (untuk prototipe). Untuk produksi gunakan DB/redis.
jobs = {}

def load_tokens():
    try:
        with open("spam_ind.json", "r") as file:
            data = json.load(file)
        tokens = [item["token"] for item in data]
        return tokens
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

async def send_single(session, uid, token, retries=2, backoff_factor=0.5, timeout=10):
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
                async with session.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=timeout) as resp:
                    status = resp.status
                    if status == 200:
                        return True
                    else:
                        attempt += 1
                        if attempt <= retries:
                            await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
            except asyncio.TimeoutError:
                attempt += 1
                if attempt <= retries:
                    await asyncio.sleep(backoff_factor * (2 ** (attempt - 1)))
                else:
                    return False
        return False
    except Exception as e:
        # Encrypt_ID / encrypt_api error
        return False

async def run_job_async(job_id, uid, tokens, delay, jitter, concurrency, retries, backoff):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()
    success = 0
    failed = 0
    total = len(tokens)

    semaphore = asyncio.Semaphore(concurrency)

    async def sem_task(session, token, index):
        # optional stagger per task: kecil, tidak blocking keseluruhan
        # tapi jangan gunakan asyncio.sleep besar di sini jika ingin cepat
        # kita gunakan a tiny jitter
        await asyncio.sleep(max(0, random.uniform(-jitter, jitter)))
        async with semaphore:
            ok = await send_single(session, uid, token, retries=retries, backoff_factor=backoff)
            return ok

    connector = aiohttp.TCPConnector(limit=0)  # no per-host limit here; concurrency controlled by semaphore
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for i, token in enumerate(tokens):
            # optional small spacing before scheduling task to keep CPU/memory friendly
            # but we DO NOT block the request thread here; it's within the background coroutine
            tasks.append(asyncio.create_task(sem_task(session, token, i)))
            # if you want to pace submission (very small), you can: await asyncio.sleep(delay + random.uniform(-jitter,jitter))
            # but to maximize throughput, don't add large sleeps here.

        for coro in asyncio.as_completed(tasks):
            ok = await coro
            if ok:
                success += 1
            else:
                failed += 1
            # update job progress
            jobs[job_id]["success"] = success
            jobs[job_id]["failed"] = failed
            jobs[job_id]["progress"] = (success + failed) / total

    jobs[job_id]["status"] = "done"
    jobs[job_id]["finished_at"] = time.time()
    jobs[job_id]["success"] = success
    jobs[job_id]["failed"] = failed
    jobs[job_id]["progress"] = 1.0

def run_job_in_thread(job_id, uid, tokens, delay, jitter, concurrency, retries, backoff):
    # wrapper untuk menjalankan asyncio event loop di thread background
    asyncio.run(run_job_async(job_id, uid, tokens, delay, jitter, concurrency, retries, backoff))

@app.route("/send_requests", methods=["GET"])
def send_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "uid parameter is required"}), 400

    try:
        # params (defaults)
        delay = float(request.args.get("delay", 0.0))       # kita set 0.0 default; jika ingin pacing set >0
        jitter = float(request.args.get("jitter", 0.01))
        concurrency = int(request.args.get("concurrency", 50))  # gunakan concurrency tinggi jika server tujuan sanggup
        limit = int(request.args.get("limit", 110))
        retries = int(request.args.get("retries", 2))
        backoff = float(request.args.get("backoff", 0.5))
    except ValueError:
        return jsonify({"error": "Invalid numeric parameter"}), 400

    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens found in spam_ind.json"}), 500

    tokens = tokens[:max(0, min(limit, len(tokens)))]

    # buat job id dan simpan job meta
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "uid": uid,
        "total": len(tokens),
        "success": 0,
        "failed": 0,
        "progress": 0.0,
        "created_at": time.time()
    }

    # start thread background (return HTTP cepat)
    t = threading.Thread(target=run_job_in_thread, args=(job_id, uid, tokens, delay, jitter, concurrency, retries, backoff), daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "status_url": f"/status?job_id={job_id}"}), 202

@app.route("/status", methods=["GET"])
def status():
    job_id = request.args.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id parameter required"}), 400
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)