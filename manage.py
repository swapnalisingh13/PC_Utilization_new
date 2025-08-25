#manage.py
import os
import re
import requests
import shutil

# URL of raw client.py in GitHub repo 
REPO_CLIENT_URL = "https://raw.githubusercontent.com/swapnalisingh13/PC_Utilization_new/main/client.py"
LOCAL_CLIENT = os.path.abspath(r"backup\client.py")    #make change here in last

def get_version_from_text(text):
    """Extract __version__ = "x.y" from Python code"""
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else None

def get_local_version():
    if not os.path.exists(LOCAL_CLIENT):
        return None
    with open(LOCAL_CLIENT, "r") as f:
        return get_version_from_text(f.read())

def get_remote_client():
    resp = requests.get(REPO_CLIENT_URL)
    resp.raise_for_status()
    return resp.text

def main():
    local_version = get_local_version()
    print("📂 Local version:", local_version)

    remote_code = get_remote_client()
    remote_version = get_version_from_text(remote_code)
    print("🌍 Remote version:", remote_version)

    if not remote_version:
        print("❌ Could not read version from remote client.py")
        return

    if local_version == remote_version:
        print("✅ Already up to date")
        return

    print(f"⬆️ Updating client.py from {local_version} → {remote_version}...")
    if os.path.exists(LOCAL_CLIENT):
        shutil.copyfile(LOCAL_CLIENT, LOCAL_CLIENT + ".bak")

    with open(LOCAL_CLIENT, "w") as f:
        f.write(remote_code)

    print("✅ Update complete. client.py now at version", remote_version)

if __name__ == "__main__":
    main()
