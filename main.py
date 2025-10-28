import json
import os
import requests
import time
from github import Github

# ===== CONFIG =====
CONFIG_FILE = "config.json"
IDPW_FILE = "idpw.json"
OUT_FILE = "token_bd.json"

# Load config
try:
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
except Exception as e:
    raise SystemExit(f"❌ Gagal buka {CONFIG_FILE}: {e}")

GITHUB_TOKEN = config.get("GITHUB_TOKEN")
REPOS = config.get("GITHUB_REPOS", ["RhhyAryandi/likeapi2"])  # daftar repo
BRANCH = config.get("GITHUB_BRANCH", "main")
JWT_API_TEMPLATE = config.get(
    "JWT_API_TEMPLATE",
    "https://kasjajwtgen1.vercel.app/token?uid={uid}&password={pw}"
)

if not GITHUB_TOKEN:
    raise SystemExit("❌ GITHUB_TOKEN belum diatur di config.json.")

# ===== GENERATE TOKEN =====
def generate_tokens():
    try:
        with open(IDPW_FILE, "r") as f:
            accounts = json.load(f)
    except Exception as e:
        raise SystemExit(f"❌ Gagal buka {IDPW_FILE}: {e}")

    tokens = []
    print("🚀 Memulai generate token...\n")

    for i, acc in enumerate(accounts, start=1):
        uid = acc.get("uid")
        pw = acc.get("password")
        if not uid or not pw:
            print(f"⚠️ Baris {i} tidak valid, dilewati.")
            continue

        try:
            url = JWT_API_TEMPLATE.format(uid=uid, pw=pw)
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                token = data.get("token")
                if token:
                    tokens.append({"token": token})
                    print(f"✅ [{i}] Token berhasil untuk UID {uid}")
                else:
                    print(f"⚠️ [{i}] Tidak ada token di respons UID {uid}")
            else:
                print(f"❌ [{i}] UID {uid} gagal, HTTP {res.status_code}")
        except Exception as e:
            print(f"⚠️ [{i}] UID {uid} error: {e}")
        time.sleep(1)

    with open(OUT_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"\n💾 Total {len(tokens)} token disimpan ke {OUT_FILE}")
    return tokens


# ===== UPLOAD KE SEMUA GITHUB REPO =====
def upload_to_all_github(tokens):
    repos = REPOS
    if not repos:
        print("❌ Tidak ada daftar repo di config.json (GITHUB_REPOS).")
        return

    g = Github(auth=Auth.Token(GITHUB_TOKEN))

    for repo_name in repos:
        try:
            repo = g.get_repo(repo_name)
            print(f"📂 Mengunggah ke {repo_name}...")
            try:
                content = repo.get_contents(OUT_FILE, ref=BRANCH)
                repo.update_file(
                    content.path,
                    f"Auto update token_bd.json ({repo_name})",
                    json.dumps(tokens, indent=2),
                    content.sha,
                    branch=BRANCH
                )
                print(f"🟢 File token_bd.json DIUPDATE di {repo_name}")
            except Exception:
                repo.create_file(
                    OUT_FILE,
                    f"Auto create token_bd.json ({repo_name})",
                    json.dumps(tokens, indent=2),
                    branch=BRANCH
                )
                print(f"🟢 File token_bd.json DIBUAT di {repo_name}")
        except Exception as e:
            print(f"❌ Gagal upload ke {repo_name}: {e}")


# ===== AUTO UPDATE TIAP 6 JAM =====
if __name__ == "__main__":
    RESTART_INTERVAL = 6 * 60 * 60  # 6 jam dalam detik
    while True:
        try:
            tokens = generate_tokens()
            upload_to_all_github(tokens)
        except Exception as e:
            print(f"⚠️ Terjadi error: {e}")
        for s in range(RESTART_INTERVAL):
            if s % 300 == 0:  # tiap 5 menit log
                print(f"💤 Masih jalan... ({s//60} menit berlalu)")
            time.sleep(1)