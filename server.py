import os
import uuid
import random
from datetime import datetime, timezone
import yfinance as yf
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# In-memory mock database to persist MVP data during the session
db_mock = {
    "orders": [],
    "executions": [],
    "execution_verification": []
}

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
    "NIFTY FUT": "^NSEI",
    "Parag Parikh Flexi Cap": "0P00011MQD.BO",
    "Nippon India Small Cap": "0P0000XW8F.BO",
    "NIFTY 24500 CE": "^NSEI"
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

@app.route("/api/simulate-order", methods=["POST"])
def simulate_order():
    try:
        data = request.json
        broker = data.get("broker", "Unknown")
        symbol = data.get("symbol", "").upper()
        side = data.get("side", "BUY").upper()
        order_type = data.get("order_type", "MARKET").upper()
        
        qty = float(data.get("qty", 0))
        target_price = float(data.get("target_price", 0))
        max_slippage = float(data.get("max_slippage", 0))

        order_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        fills = []
        executed_qty = 0
        total_cost = 0.0
        
        # Check for specific demo scenario
        if symbol == "RELIANCE" and qty == 1000000 and target_price == 250 and max_slippage == 0.05 and side == "BUY":
            # Generate two fills to total 500k executed, avg price 250.18 -> slippage 0.072%
            fill1_qty = 200000
            fill1_price = 250.05
            fills.append({
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "fill_quantity": fill1_qty,
                "fill_price": fill1_price,
                "cumulative_quantity": fill1_qty,
                "timestamp": created_at
            })
            
            fill2_qty = 300000
            fill2_price = 250.266666  # (250.18 * 500000 - 250.05 * 200000) / 300000 ≈ 250.2666
            fills.append({
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "fill_quantity": fill2_qty,
                "fill_price": 250.266666, # For display purposes, it will be 250.18 avg
                "cumulative_quantity": 500000,
                "timestamp": created_at
            })
            
            executed_qty = 500000
            avg_price = 250.18
            slippage = 0.072
            status = "PAUSED"
            paused_qty = 500000
            
            reason = f"Actual slippage of {slippage:.3f}% exceeded the allowed limit of {max_slippage}%."
            action = "Remaining order paused."
            verification_status = "SLIPPAGE LIMIT EXCEEDED"
            
        else:
            # Generic execution logic
            chunks = random.randint(2, 5)
            chunk_qty = int(qty / chunks)
            
            will_pause = random.random() > 0.6
            limit_breached = False
            
            for i in range(chunks):
                if limit_breached:
                    break
                    
                is_last = (i == chunks - 1)
                current_qty = int(qty - executed_qty) if is_last else chunk_qty
                
                # simulate some price movement
                if will_pause and i == chunks - 2:
                    # force a breach
                    slip_factor = max_slippage + random.uniform(0.01, 0.05)
                else:
                    slip_factor = random.uniform(0.0, max_slippage * 0.9)
                
                if side == "BUY":
                    fill_price = target_price * (1 + (slip_factor / 100))
                else:
                    fill_price = target_price * (1 - (slip_factor / 100))
                    
                executed_qty += current_qty
                total_cost += (current_qty * fill_price)
                
                fills.append({
                    "id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "fill_quantity": current_qty,
                    "fill_price": round(fill_price, 2),
                    "cumulative_quantity": executed_qty,
                    "timestamp": created_at
                })
                
                current_avg = total_cost / executed_qty
                current_slip = abs((current_avg - target_price) / target_price) * 100
                
                if current_slip > max_slippage:
                    limit_breached = True
            
            avg_price = total_cost / executed_qty if executed_qty > 0 else target_price
            slippage = abs((avg_price - target_price) / target_price) * 100
            paused_qty = qty - executed_qty
            
            if limit_breached or paused_qty > 0:
                status = "PAUSED"
                verification_status = "SLIPPAGE LIMIT EXCEEDED"
                reason = f"Actual slippage of {slippage:.3f}% exceeded the allowed limit of {max_slippage}%."
                action = "Remaining order paused."
            else:
                status = "EXECUTED"
                verification_status = "VERIFIED"
                reason = "Execution within slippage tolerance."
                action = "Order completely filled."

        # Prepare DB records
        order_record = {
            "id": order_id,
            "broker": broker,
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "requested_quantity": qty,
            "target_price": target_price,
            "max_slippage": max_slippage,
            "status": status,
            "created_at": created_at
        }
        
        verification_record = {
            "id": str(uuid.uuid4()),
            "order_id": order_id,
            "executed_quantity": executed_qty,
            "remaining_quantity": paused_qty,
            "average_execution_price": round(avg_price, 2),
            "actual_slippage": round(slippage, 3),
            "max_allowed_slippage": max_slippage,
            "verification_status": verification_status,
            "action_taken": action,
            "timestamp": created_at
        }
        
        db_mock["orders"].insert(0, order_record)
        db_mock["executions"].extend(fills)
        db_mock["execution_verification"].append(verification_record)

        return jsonify({
            "order": order_record,
            "fills": fills,
            "verification": verification_record
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/execution-history", methods=["GET"])
def execution_history():
    history = []
    for o in db_mock["orders"][:10]:
        v = next((x for x in db_mock["execution_verification"] if x["order_id"] == o["id"]), {})
        history.append({**o, **v})
    return jsonify({"history": history})

@app.route("/api/fill-audit/<order_id>", methods=["GET"])
def fill_audit(order_id):
    fills = [f for f in db_mock["executions"] if f["order_id"] == order_id]
    return jsonify({"fills": fills})

@app.route("/api/execution-verification/<order_id>", methods=["GET"])
def execution_verification(order_id):
    data = next((v for v in db_mock["execution_verification"] if v["order_id"] == order_id), None)
    if not data:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"verification": data})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
