import os
import json
import time
import requests

MORPHO_GQL = "https://api.morpho.org/graphql"

UNIQUE_KEY = os.getenv("MORPHO_MARKET_UNIQUE_KEY", "").strip()
CHAIN_ID = int(os.getenv("MORPHO_CHAIN_ID", "1"))
THRESHOLD = float(os.getenv("BORROW_APY_THRESHOLD", "0.07"))  # 7% = 0.07

TG_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()

COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "30"))

# 用于“上穿触发/冷却”状态
STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"last_alert_ts": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def tg_send(text: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        raise RuntimeError("Missing TG_BOT_TOKEN or TG_CHAT_ID")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    r.raise_for_status()

def fetch_borrow_apy():
    if not UNIQUE_KEY:
        raise RuntimeError("Missing MORPHO_MARKET_UNIQUE_KEY")

    query = """
    query($uniqueKey: String!, $chainId: Int!) {
      marketByUniqueKey(uniqueKey: $uniqueKey, chainId: $chainId) {
        uniqueKey
        loanAsset { symbol address }
        collateralAsset { symbol address }
        state { borrowApy utilization }
      }
    }
    """
    payload = {"query": query, "variables": {"uniqueKey": UNIQUE_KEY, "chainId": CHAIN_ID}}
    r = requests.post(MORPHO_GQL, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    m = data["data"]["marketByUniqueKey"]
    if not m:
        raise RuntimeError("marketByUniqueKey returned null (wrong uniqueKey/chainId?)")

    apy = float(m["state"]["borrowApy"])
    util = float(m["state"]["utilization"])
    loan_symbol = m["loanAsset"]["symbol"]
    loan_addr = m["loanAsset"]["address"]
    coll_symbol = m["collateralAsset"]["symbol"]
    coll_addr = m["collateralAsset"]["address"]
    return apy, util, loan_symbol, loan_addr, coll_symbol, coll_addr

def main():
    state = load_state()
    now = time.time()

    apy, util, loan_symbol, loan_addr, coll_symbol, coll_addr = fetch_borrow_apy()

    if apy > THRESHOLD:
        if now - state.get("last_alert_ts", 0) >= COOLDOWN_MIN * 60:
            msg = (
                f"⚠️ Morpho Borrow APY Alert\n"
                f"Market: {UNIQUE_KEY}\n"
                f"Borrow: {loan_symbol} ({loan_addr})\n"
                f"Collateral: {coll_symbol} ({coll_addr})\n"
                f"Borrow APY: {apy*100:.2f}% (threshold {THRESHOLD*100:.2f}%)\n"
                f"Utilization: {util*100:.2f}%\n"
                f"ChainId: {CHAIN_ID}"
            )
            tg_send(msg)
            state["last_alert_ts"] = now
            save_state(state)

if __name__ == "__main__":
    main()
