import os
import json
import requests

MORPHO_GQL = "https://api.morpho.org/graphql"

UNIQUE_KEY = os.getenv("MORPHO_MARKET_UNIQUE_KEY", "").strip()
CHAIN_ID = int(os.getenv("MORPHO_CHAIN_ID", "1"))
THRESHOLD = float(os.getenv("BORROW_APY_THRESHOLD", "0.07"))

TG_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()

STATE_FILE = "state.json"

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"was_above": False}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def tg_send(text: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    r.raise_for_status()

def fetch_borrow_apy():
    query = """
    query($uniqueKey: String!, $chainId: Int!) {
      marketByUniqueKey(uniqueKey: $uniqueKey, chainId: $chainId) {
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

    m = data["data"]["marketByUniqueKey"]
    apy = float(m["state"]["borrowApy"])
    util = float(m["state"]["utilization"])

    loan_symbol = m["loanAsset"]["symbol"]
    coll_symbol = m["collateralAsset"]["symbol"]

    return apy, util, loan_symbol, coll_symbol

def main():
    state = load_state()
    was_above = state.get("was_above", False)

    apy, util, loan_symbol, coll_symbol = fetch_borrow_apy()
    is_above = apy >= THRESHOLD

    # 上穿
    if is_above and not was_above:
        msg = (
            f"🚨 Borrow APY 上穿 {THRESHOLD*100:.2f}%\n"
            f"Market: {UNIQUE_KEY}\n"
            f"Borrow: {loan_symbol}\n"
            f"Collateral: {coll_symbol}\n"
            f"Current APY: {apy*100:.2f}%\n"
            f"Utilization: {util*100:.2f}%"
        )
        tg_send(msg)

    # 跌破
    if not is_above and was_above:
        msg = (
            f"✅ Borrow APY 回落到 {THRESHOLD*100:.2f}% 下方\n"
            f"Market: {UNIQUE_KEY}\n"
            f"Borrow: {loan_symbol}\n"
            f"Collateral: {coll_symbol}\n"
            f"Current APY: {apy*100:.2f}%\n"
            f"Utilization: {util*100:.2f}%"
        )
        tg_send(msg)

    state["was_above"] = is_above
    save_state(state)

if __name__ == "__main__":
    main()
