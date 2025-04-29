import requests
import pandas as pd
import platform
from flask import Flask, request

# Optional sound alert (Windows only)
if platform.system() == "Windows":
    import winsound

# Telegram Bot settings
bot_token = '7717076163:AAFzWU5dxRzBNNg7dm-UHgi7jQYYWmGNzs8'
app = Flask(__name__)
api_key = "c6e06c3072b34cab9798f6e0b56db499"
symbol = "XAU/USD"

# Send message to Telegram function
def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    requests.post(url, data=payload)

# Fetch market data from API
def fetch_data(symbol, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize=100&apikey={api_key}"
    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        print(f"❌ Error fetching {interval} data: {data}")
        return None

    df = pd.DataFrame(data["values"])
    numeric_cols = ['open', 'high', 'low', 'close']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)

    return df[::-1].reset_index(drop=True)

# Analyze data and generate signals
def analyze_data(df, interval):
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()

    latest_close = df["close"].iloc[-1]
    previous_close = df["close"].iloc[-2]

    market_trend = "Bullish" if latest_close > previous_close else "Bearish"
    ma_signal = "BUY" if df["MA5"].iloc[-1] > df["MA20"].iloc[-1] else "SELL"

    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()
    atr = df["ATR"].iloc[-1]

    risk = 1.5
    sl = latest_close - atr * risk if market_trend == "Bullish" else latest_close + atr * risk
    tp = latest_close + atr * risk if market_trend == "Bullish" else latest_close - atr * risk
    support_level = latest_close - atr
    resistance_level = latest_close + atr

    # ✅ Signal Accuracy Calculation
    correct_signals = 0
    total_signals = 0
    for i in range(20, len(df) - 1):  # start after MA20 is valid
        signal = "BUY" if df["MA5"].iloc[i] > df["MA20"].iloc[i] else "SELL"
        current_close = df["close"].iloc[i]
        next_close = df["close"].iloc[i + 1]

        if signal == "BUY" and next_close > current_close:
            correct_signals += 1
        elif signal == "SELL" and next_close < current_close:
            correct_signals += 1

        total_signals += 1

    accuracy = (correct_signals / total_signals) * 100 if total_signals else 0

    return f"⏱ Timeframe: {interval}\n" \
           f"📈 Trend: {market_trend}\n" \
           f"📊 Signal: {ma_signal}\n" \
           f"🎯 Accuracy: {accuracy:.1f}% (last {total_signals} signals)\n" \
           f"🔎 ATR: {atr:.2f}\n" \
           f"💡 SL: {sl:.2f} | TP: {tp:.2f}\n" \
           f"🔒 Support: {support_level:.2f} | 🔓 Resistance: {resistance_level:.2f}\n"

# Flask route for webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" in data:
        message = data['message']['text']
        chat_id = data['message']['chat']['id']
        user_name = data['message']['chat'].get('username') or data['message']['chat'].get('first_name', 'Trader')

        if message == '/signals':
            intervals = ["1h", "30min", "15min", "5min"]
            full_message = f"📩 Hello {user_name}!\n📊 Multi-Timeframe Signal Summary:\n\n"
            for interval in intervals:
                df = fetch_data(symbol, interval)
                if df is not None:
                    analysis = analyze_data(df, interval)
                    full_message += analysis + "\n" + ("─" * 40) + "\n"
            send_telegram_message(full_message.strip(), chat_id)

        elif message == '/status':
            df = fetch_data(symbol, "1h")
            if df is not None:
                response = analyze_data(df, "1h")
                send_telegram_message(f"📩 Hello {user_name}!\n{response}", chat_id)

        elif message == '/latest_signal':
            df = fetch_data(symbol, "5min")
            if df is not None:
                response = analyze_data(df, "5min")
                send_telegram_message(f"📩 Hello {user_name}!\n{response}", chat_id)

        else:
            send_telegram_message("🤖 Unknown command.\nTry /signals, /status, or /latest_signal.", chat_id)

    return '', 200

# Run Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)

