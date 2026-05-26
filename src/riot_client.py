"""
Riot API client with rate limit handling.
Loads the API key from .env and provides a safe GET helper
for platform and regional routing.
"""

import os
import time
from collections import deque

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
if not API_KEY:
    raise RuntimeError("RIOT_API_KEY not found. Check your .env file.")

PLATFORM = "euw1"      # summoner-v4 and league endpoints
REGION = "europe"      # account-v1 and match-v5 endpoints

HEADERS = {"X-Riot-Token": API_KEY}

# Development key limits: 20 requests per 1 second, 100 requests per 120 seconds
_request_times = deque()
PER_SECOND_LIMIT = 20
PER_TWO_MIN_LIMIT = 100


def _respect_rate_limit():
    """Sleep if we are close to the development key limits."""
    now = time.time()
    while _request_times and now - _request_times[0] > 120:
        _request_times.popleft()
    if len(_request_times) >= PER_TWO_MIN_LIMIT:
        sleep_for = 120 - (now - _request_times[0]) + 0.1
        if sleep_for > 0:
            time.sleep(sleep_for)
    recent = [t for t in _request_times if time.time() - t < 1]
    if len(recent) >= PER_SECOND_LIMIT:
        time.sleep(1)


def get(url, params=None, max_retries=5):
    """GET with rate limit awareness and retry on 429 and 5xx."""
    for attempt in range(max_retries):
        _respect_rate_limit()
        _request_times.append(time.time())
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise SystemExit(
                "\n--- Riot API key rejected (401/403). It has most likely expired. ---\n"
                "1. Get a fresh key at https://developer.riotgames.com\n"
                "2. Paste it into .env, replacing the old value.\n"
                "3. Run the same command again. Everything already pulled is saved,\n"
                "   and the pull will resume from where it stopped.\n"
            )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            print(f"Rate limited. Waiting {retry_after} seconds.")
            time.sleep(retry_after + 1)
            continue
        if response.status_code in (500, 502, 503, 504):
            wait = 2 ** attempt
            print(f"Server error {response.status_code}. Retrying in {wait} seconds.")
            time.sleep(wait)
            continue
        response.raise_for_status()

    raise RuntimeError(f"Failed after {max_retries} retries: {url}")


def platform_url(path):
    """Build a platform routed URL (euw1)."""
    return f"https://{PLATFORM}.api.riotgames.com{path}"


def regional_url(path):
    """Build a regional routed URL (europe)."""
    return f"https://{REGION}.api.riotgames.com{path}"


if __name__ == "__main__":
    status = get(platform_url("/lol/status/v4/platform-data"))
    if status:
        print("Key works. Connected to:", status.get("name"))
    else:
        print("No data returned. Check the key and region.")