import os
import json
import requests
import yfinance as yf
from datetime import datetime

# ==========================================
# 1. LINE Messaging API 設定（GitHub Secretsから自動読み込み）
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

# ==========================================
# 2. あなたのポートフォリオ設定（保有銘柄・待機資金）
# ==========================================
CASH_BALANCE_JPY = 1400000  # 待機資金（日本円）

HOLDINGS_CONFIG = [
    {
        "name": "三菱UFJフィナンシャルG",
        "ticker": "8306.T",
        "sector": "金融",
        "currency": "JPY",
        "shares": 1000,         # 保有株数
        "avg_cost": 1300.0      # 1株あたりの平均取得単価（円）
    },
    {
        "name": "三井住友フィナンシャルG",
        "ticker": "8316.T",
        "sector": "金融",
        "currency": "JPY",
        "shares": 300,
        "avg_cost": 3000.0
    },
    {
        "name": "バンガード S&P500 ETF",
        "ticker": "VOO",
        "sector": "米国ETF",
        "currency": "USD",
        "shares": 30,
        "avg_cost": 490.0       # 1株あたりの平均取得単価（ドル）
    },
    {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "sector": "IT・半導体",
        "currency": "USD",
        "shares": 40,
        "avg_cost": 215.0
    },
    {
        "name": "NVIDIA Corp.",
        "ticker": "NVDA",
        "sector": "IT・半導体",
        "currency": "USD",
        "shares": 60,
        "avg_cost": 122.0
    },
    {
        "name": "三井物産",
        "ticker": "8031.T",
        "sector": "商社・資源",
        "currency": "JPY",
        "shares": 450,
        "avg_cost": 2888.0
    }
]


def get_realtime_usdjpy() -> float:
    try:
        fx = yf.Ticker("USDJPY=X")
        hist = fx.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"[警告] ドル円レートの取得に失敗: {e}")
    return 150.0


def get_realtime_price(ticker: str) -> float:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"[エラー] {ticker} の株価取得に失敗: {e}")
    return 0.0


def analyze_portfolio():
    usdjpy = get_realtime_usdjpy()
    print(f"現在のドル円レート: 1ドル = {usdjpy:.2f} 円")

    evaluated_items = []
    stock_total_jpy = 0.0
    cost_total_jpy = 0.0
    danger_alerts = []
    warning_alerts = []

    for item in HOLDINGS_CONFIG:
        price = get_realtime_price(item["ticker"])
        if price <= 0:
            price = item["avg_cost"]

        fx_rate = usdjpy if item["currency"] == "USD" else 1.0
        cost_jpy = item["avg_cost"] * item["shares"] * fx_rate
        value_jpy = price * item["shares"] * fx_rate
        pnl_jpy = value_jpy - cost_jpy
        pnl_pct = ((price - item["avg_cost"]) / item["avg_cost"]) * 100.0

        stock_total_jpy += value_jpy
        cost_total_jpy += cost_jpy

        evaluated_items.append({
            "id": item["ticker"].lower().replace(".", "_"),
            "name": item["name"],
            "ticker": item["ticker"],
            "sector": item["sector"],
            "shares": item["shares"],
            "avg_cost": item["avg_cost"],
            "price": price,
            "currency": item["currency"],
            "cost_jpy": cost_jpy,
            "value_jpy": value_jpy,
            "pnl_jpy": pnl_jpy,
            "pnl_pct": pnl_pct
        })

        if pnl_pct <= -10.0:
            danger_alerts.append(
                f"🚨【緊急損切り】{item['name']} ({item['ticker']})\n"
                f"   現在損益: {pnl_pct:.2f}%（-10%防衛ライン突破！）"
            )
        elif pnl_pct <= -5.0:
            warning_alerts.append(
                f"⚠️【注意監視】{item['name']} ({item['ticker']}): {pnl_pct:.2f}%"
            )

    total_assets_jpy = stock_total_jpy + CASH_BALANCE_JPY
    total_pnl_jpy = stock_total_jpy - cost_total_jpy
    total_pnl_pct = (total_pnl_jpy / cost_total_jpy * 100.0) if cost_total_jpy > 0 else 0.0
    cash_ratio = (CASH_BALANCE_JPY / total_assets_jpy * 100.0) if total_assets_jpy > 0 else 0.0

    for ev in evaluated_items:
        ev["weight"] = (ev["value_jpy"] / total_assets_jpy * 100.0) if total_assets_jpy > 0 else 0.0

    cash_alert = None
    if cash_ratio < 10.0:
        cash_alert = f"⚠️【現金余力低下】待機資金比率が {cash_ratio:.1f}%（目安10%未満）です。新規買い増しを控えましょう。"

    return {
        "timestamp": datetime.now().strftime("%Y/%m/%d %H:%M"),
        "usdjpy": usdjpy,
        "total_assets_jpy": total_assets_jpy,
        "total_pnl_jpy": total_pnl_jpy,
        "total_pnl_pct": total_pnl_pct,
        "cash_jpy": CASH_BALANCE_JPY,
        "cash_ratio": cash_ratio,
        "items": evaluated_items,
        "danger_alerts": danger_alerts,
        "warning_alerts": warning_alerts,
        "cash_alert": cash_alert
    }


def send_line_push_message(message_text: str):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("❌ LINEトークンまたはユーザーIDが未設定です")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message_text}]
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
    if resp.status_code == 200:
        print("✅ LINEへのプッシュ通知送信に成功しました！")
    else:
        print(f"❌ LINE送信エラー ({resp.status_code}): {resp.text}")


def build_report_message(result: dict) -> str:
    sign = "+" if result["total_pnl_jpy"] >= 0 else ""
    lines = [
        f"📡 AETHER QUANT 定期レポート",
        f"🕒 {result['timestamp']} (1$={result['usdjpy']:.1f}円)",
        f"━━━━━━━━━━━━━━",
        f"💰 総資産: ¥{result['total_assets_jpy']:,.0f}",
        f"📈 評価損益: {sign}¥{result['total_pnl_jpy']:,.0f} ({sign}{result['total_pnl_pct']:.2f}%)",
        f"💴 待機資金: ¥{result['cash_jpy']:,.0f} ({result['cash_ratio']:.1f}%)",
        f"━━━━━━━━━━━━━━"
    ]

    if result["danger_alerts"]:
        lines.append("【🚨 緊急ロスカット警告】")
        lines.extend(result["danger_alerts"])
        lines.append("")

    if result["cash_alert"]:
        lines.append(result["cash_alert"])
        lines.append("")

    if result["warning_alerts"]:
        lines.append("【👀 注意監視ゾーン (-5%〜)】")
        lines.extend(result["warning_alerts"])
        lines.append("")

    lines.append("【📊 保有銘柄ステータス】")
    for item in result["items"]:
        s = "+" if item["pnl_pct"] >= 0 else ""
        status_icon = "🚨" if item["pnl_pct"] <= -10 else ("⚠️" if item["pnl_pct"] <= -5 else "✅")
        lines.append(f"{status_icon} {item['name']}: {s}{item['pnl_pct']:.1f}% (比率{item['weight']:.1f}%)")

    if not result["danger_alerts"] and not result["cash_alert"]:
        lines.append("\n🛡️ 全銘柄が-10%防衛ライン内で安定推移中。分散と押し目待機を継続しましょう！")

    return "\n".join(lines)


def save_live_json(result: dict, filepath: str = "portfolio_live.json"):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 ダッシュボード連携用データ ({filepath}) を保存しました！")


if __name__ == "__main__":
    print("AETHER QUANT リアルタイム監視エンジンを起動します...")
    analysis_result = analyze_portfolio()
    save_live_json(analysis_result)
    report_text = build_report_message(analysis_result)
    send_line_push_message(report_text)
