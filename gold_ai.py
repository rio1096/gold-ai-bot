import requests
import pandas as pd
import platform
from flask import Flask, request

# Optional sound alert (Windows only)
if platform.system() == "Windows":
    import winsound

# Telegram Bot settings
bot_token = '7717076163:AAFzWU5dxRzBNNg7dm-UHgi7jQYYWmGNzs8'  # Your Bot Token
chat_id = '5505179096'  # Your Chat ID

# Create a Flask app to interact with Telegram
app = Flask(__name__)

# Send message to Telegram function
def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    response = requests.post(url, data=payload)

    if response.status_code == 200:
        print("✅ Message sent successfully!")
    else:
        print("❌ Error sending message.")

# Optional function for Windows sound alert
def alert_user(signal):
    print(f"\n🚨 STRONG {signal} SIGNAL DETECTED 🚨")
    if platform.system() == "Windows":
        frequency = 1000 if signal == "BUY" else 600
        duration = 500  # milliseconds
        winsound.Beep(frequency, duration)
    else:
        print("🔔 (Sound alert not supported on this OS)")

# Fetch market data from API
api_key = "c6e06c3072b34cab9798f6e0b56db499"
symbol = "XAU/USD"
intervals = ["1min", "5min", "15min", "1h"]

def fetch_data(symbol, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize=100&apikey={api_key}"
    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        print(f"❌ Error fetching {interval} data: {data}")
        return None

    df = pd.DataFrame(data["values"])
    
    # Only convert numeric columns that actually exist
    numeric_cols = ['open', 'high', 'low', 'close']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)
    
    df = df[::-1].reset_index(drop=True)
    return df

# Analyze data and generate signals
def analyze_data(df, interval):
    print(f"\n🕒 Timeframe: {interval}")

    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()

    latest_close = df["close"].iloc[-1]
    previous_close = df["close"].iloc[-2]

    # Candle movement
    if latest_close > previous_close:
        print("📈 Market rising (Bullish)")
    else:
        print("📉 Market falling (Bearish)")

    # MA crossover
    if df["MA5"].iloc[-1] > df["MA20"].iloc[-1]:
        print("🟢 MA Crossover: MA5 > MA20 → BUY Signal")
        signal = "BUY"
    else:
        print("🔴 MA Crossover: MA5 < MA20 → SELL Signal")
        signal = "SELL"

    # ATR Calculation
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()

    atr = df["ATR"].iloc[-1]
    risk = 1.5  # You can adjust this

    # SL / TP Suggestion
    if latest_close > previous_close:
        sl = latest_close - atr * risk
        tp = latest_close + atr * risk
        print(f"💡 SL (BUY): {sl:.2f} | TP (BUY): {tp:.2f}")
    elif latest_close < previous_close:
        sl = latest_close + atr * risk
        tp = latest_close - atr * risk
        print(f"💡 SL (SELL): {sl:.2f} | TP (SELL): {tp:.2f}")
    else:
        print("❔ No clear trade direction → No SL/TP")
        sl = tp = "N/A"  # No SL/TP if no clear trade direction

    # Final Recommendation (send to Telegram)
    return f"\n🔮 Final Recommendation: {signal}\nSL: {sl:.2f}\nTP: {tp:.2f}"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" in data:
        message = data['message']['text']
        if message == '/status':
            # Fetch and analyze data
            df = fetch_data(symbol, "1h")  # Get 1-hour data for example
            if df is not None:
                response_message = analyze_data(df, "1h")
                send_telegram_message(response_message, chat_id)
        elif message == '/latest_signal':
            df = fetch_data(symbol, "5min")  # Get 5-min data for example
            if df is not None:
                response_message = analyze_data(df, "5min")
                send_telegram_message(response_message, chat_id)
        else:
            send_telegram_message("Unknown command. Try /status or /latest_signal.", chat_id)

    return '', 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)

