import requests

def probe_get(url):
    try:
        print(f"GET {url} ...")
        resp = requests.get(url, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    probe_get("https://yunyi.rdzhvip.com/claude")
    probe_get("https://yunyi.rdzhvip.com")

if __name__ == "__main__":
    main()
