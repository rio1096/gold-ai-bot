import requests
import pandas as pd
import platform
import logging
from flask import Flask, request

if platform.system() == "Windows":
    import winsound

# ✅ API Keys
bot_token = '7717076163:AAFzWU5dxRzBNNg7dm-UHgi7jQYYWmGNzs8'
api_key = 'c6e06c3072b34cab9798f6e0b56db499'
symbol = 'XAU/USD'

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ✅ Send message to Telegram
def send_telegram_message(message, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# ✅ Fetch live price
def fetch_live_price(sym):
    url = f"https://api.twelvedata.com/price?symbol={sym}&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    if "price" in data:
        return float(data["price"])
    logging.error(f"Error fetching live price: {data}")
    return None

# ✅ Fetch historical data
def fetch_data(sym, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval={interval}&outputsize=100&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    if "values" not in data:
        logging.error(f"Error fetching {interval} data: {data}")
        return None
    df = pd.DataFrame(data["values"])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df = df[::-1].reset_index(drop=True).dropna()
    return df

# ✅ Calculate technical indicators
def calculate_indicators(df):
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / (loss + 1e-10)
    df["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()

    return df.dropna()

# ✅ Generate signal and message
def generate_trade_signal(df, interval):
    latest = df.iloc[-1]
    previous = df.iloc[-2]

    trend = "Bullish" if latest["close"] > previous["close"] else "Bearish"
    ma_signal = "BUY" if latest["MA5"] > latest["MA20"] else "SELL"
    rsi = latest["RSI"]
    macd_trend = "Bullish" if latest["MACD"] > latest["MACD_signal"] else "Bearish"
    atr = latest["ATR"]
    close = latest["close"]
    risk = 1.5

    if ma_signal == "BUY" and rsi > 70:
        ma_signal += " (⚠️ RSI Overbought)"
    elif ma_signal == "SELL" and rsi < 30:
        ma_signal += " (⚠️ RSI Oversold)"
    if "BUY" in ma_signal and macd_trend != "Bullish":
        ma_signal += " (⚠️ MACD not Bullish)"
    elif "SELL" in ma_signal and macd_trend != "Bearish":
        ma_signal += " (⚠️ MACD not Bearish)"

    sl = close - atr * risk if "BUY" in ma_signal else close + atr * risk
    tp = close + atr * risk if "BUY" in ma_signal else close - atr * risk
    support = close - atr
    resistance = close + atr

    avg_vol = df["volume"].iloc[-20:].mean()
    vol_spike = df["volume"].iloc[-1] > 1.5 * avg_vol
    flat_market = df["high"].iloc[-10:].sub(df["low"].iloc[-10:]).mean() < close * 0.0015
    volume_note = "📢 Volume Spike Detected!\n" if vol_spike else ("😴 Flat Market — Low Range\n" if flat_market else "")

    return f"{volume_note}" \
           f"⏱ Timeframe: {interval}\n" \
           f"📈 Trend: {trend}\n" \
           f"📊 Signal: {ma_signal}\n" \
           f"📉 RSI: {rsi:.2f}\n" \
           f"📉 MACD: {latest['MACD']:.2f} | Signal: {latest['MACD_signal']:.2f} → {macd_trend}\n" \
           f"🔎 ATR: {atr:.2f}\n" \
           f"💡 SL: {sl:.2f} | TP: {tp:.2f}\n" \
           f"🔒 Support: {support:.2f} | 🔓 Resistance: {resistance:.2f}\n"

# ✅ Backtest logic
def backtest_strategy(df):
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["signal"] = 0
    df.loc[df["MA5"] > df["MA20"], "signal"] = 1
    df.loc[df["MA5"] < df["MA20"], "signal"] = -1
    df["returns"] = df["close"].pct_change()
    df["strategy"] = df["signal"].shift(1) * df["returns"]

    total_return = df["strategy"].cumsum().iloc[-1]
    wins = (df["strategy"] > 0).sum()
    losses = (df["strategy"] < 0).sum()
    trades = wins + losses

    return f"🧪 Backtest Results:\n" \
           f"📈 Total Return: {total_return * 100:.2f}%\n" \
           f"✅ Wins: {wins} | ❌ Losses: {losses}\n" \
           f"📊 Total Trades: {trades}\n"

# ✅ Webhook to handle Telegram commands
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" not in data:
        return '', 200

    chat_id = data['message']['chat']['id']
    user_name = data['message']['chat'].get('username') or data['message']['chat'].get('first_name', 'Trader')
    message = data['message'].get('text', '')
    live_price = fetch_live_price(symbol)
    live_msg = f"💰 Live XAU/USD Price: {live_price:.2f}" if live_price else "❌ Error fetching live price."

    if message == '/signals':
        intervals = ["1h", "30min", "15min", "5min"]
        reply = f"📩 Hello {user_name}!\n📊 Multi-Timeframe Signal Summary:\n\n{live_msg}\n\n"
        for interval in intervals:
            df = fetch_data(symbol, interval)
            if df is not None:
                df = calculate_indicators(df)
                reply += generate_trade_signal(df, interval) + "\n" + ("─" * 40) + "\n"
        send_telegram_message(reply.strip(), chat_id)

    elif message == '/status':
        df = fetch_data(symbol, "1h")
        if df is not None:
            df = calculate_indicators(df)
            reply = f"📩 Hello {user_name}!\n{live_msg}\n{generate_trade_signal(df, '1h')}"
            send_telegram_message(reply, chat_id)

    elif message == '/latest_signal':
        df = fetch_data(symbol, "5min")
        if df is not None:
            df = calculate_indicators(df)
            reply = f"📩 Hello {user_name}!\n{live_msg}\n{generate_trade_signal(df, '5min')}"
            send_telegram_message(reply, chat_id)

    elif message == '/backtest':
        df = fetch_data(symbol, "1h")
        if df is not None:
            df = calculate_indicators(df)
            reply = f"📩 Hello {user_name}!\n{backtest_strategy(df)}"
            send_telegram_message(reply, chat_id)

    else:
        send_telegram_message("🤖 Unknown command.\nTry /signals, /status, /latest_signal, or /backtest.", chat_id)

    return '', 200

# ✅ Run Flask app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=10000)
