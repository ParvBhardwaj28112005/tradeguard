import os
import yfinance as yf
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Ticker mapping from UI symbols to Yahoo Finance symbols
TICKER_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "SBIN": "SBIN.NS",
    "BTC": "BTC-INR",
    "BTC/INR": "BTC-INR",
    "ETH": "ETH-INR",
    "EUR/USD": "EURUSD=X",
    "NIFTY FUT": "^NSEI", # Using spot index as proxy
    "Parag Parikh Flexi Cap": "0P00011MQD.BO", # PPFAS
    "Nippon India Small Cap": "0P0000XW8F.BO", # Nippon Small cap
    "NIFTY 24500 CE": "^NSEI" # Options proxy
}

@app.route("/")
def index():
    if os.path.exists("index.html"):
        return send_file("index.html")
    return "index.html not found", 404

@app.route("/api/market-data")
def market_data():
    symbols = request.args.get('symbols', '')
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    
    if not sym_list:
        return jsonify({"error": "No valid symbols provided"}), 400

    yf_symbols = []
    for s in sym_list:
        mapped = TICKER_MAP.get(s, s + ".NS")
        yf_symbols.append(mapped)

    result = {}
    
    try:
        tickers = " ".join(yf_symbols)
        data = yf.download(tickers, period="1d", group_by="ticker", threads=True, progress=False)
        
        if len(yf_symbols) == 1:
            try:
                last_price = float(data['Close'].iloc[-1])
            except Exception:
                ticker_obj = yf.Ticker(yf_symbols[0])
                last_price = float(ticker_obj.fast_info.last_price)
                
            import math
            if math.isnan(last_price):
                last_price = 0.0
                
            result[sym_list[0]] = {"price": last_price, "symbol": sym_list[0]}
        else:
            for ui_sym, yf_sym in zip(sym_list, yf_symbols):
                try:
                    if yf_sym in data:
                        last_price = float(data[yf_sym]['Close'].iloc[-1])
                    else:
                        raise KeyError
                except Exception:
                    try:
                        ticker_obj = yf.Ticker(yf_sym)
                        last_price = float(ticker_obj.fast_info.last_price)
                    except Exception:
                        last_price = 0.0
                
                import math
                if math.isnan(last_price):
                    last_price = 0.0
                    
                result[ui_sym] = {"price": last_price, "symbol": ui_sym}
                
        return jsonify({"data": result})

    except Exception as e:
        print(f"Error fetching data: {e}")
        for ui_sym in sym_list:
            result[ui_sym] = {"price": 1000.0, "symbol": ui_sym, "error": str(e)}
        return jsonify({"data": result})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)

