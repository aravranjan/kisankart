import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
app.secret_key = "kisan_kart_secret"

# Simple In-Memory Storage
global_products = [
    {
        "_id": "1",
        "name": "Fresh Organic Tomatoes",
        "category": "Vegetables",
        "price": 40.0,
        "qty": 20,
        "area": "Nashik",
        "description": "Farm-fresh ripe tomatoes, perfect for salads and cooking.",
        "image": "background.png",
        "status": "available"
    },
    {
        "_id": "2",
        "name": "Basmati Rice",
        "category": "Grains",
        "price": 120.0,
        "qty": 50,
        "area": "Punjab",
        "description": "Long-grain aromatic basmati rice from the fields of Punjab.",
        "image": "background2.png",
        "status": "available"
    }
]
global_orders = []

@app.context_processor
def inject_globals():
    return dict(is_demo_mode=True, current_user={'name': 'Guest User', 'is_authenticated': True, 'type': 'customer'})

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register/farmer')
def register_farmer():
    return redirect(url_for('list_product'))

@app.route('/register/customer')
def register_customer():
    return redirect(url_for('discover'))

@app.route('/login')
def login():
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

@app.route('/farmer', methods=['GET', 'POST'])
def farmer():
    if request.method == 'POST':
        name = request.form.get('crop_name')
        price = float(request.form.get('price', 0))
        qty = int(request.form.get('quantity', 0))
        
        new_prod = {
            "_id": str(len(global_products) + 1),
            "name": name,
            "category": "Fresh Produce",
            "price": price,
            "qty": qty,
            "area": request.form.get('area'),
            "description": f"Grown in {request.form.get('area')}",
            "image": "background.png", 
            "status": "available"
        }
        global_products.append(new_prod)
        flash(f"Crop '{name}' added successfully!", "success")
        return redirect(url_for('consumer'))

    return render_template('list_product.html')

@app.route('/consumer')
def consumer():
    return render_template('shop.html', products=global_products)

@app.route('/product/<product_id>')
def product_detail(product_id):
    product = next((p for p in global_products if p["_id"] == product_id), None)
    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for('consumer'))
    return render_template('product_detail.html', product=product)

@app.route('/buy/<product_id>', methods=['POST'])
def buy_product(product_id):
    product = next((p for p in global_products if p["_id"] == product_id), None)
    if product and product['qty'] > 0:
        product['qty'] -= 1
        global_orders.append({
            "product_name": product['name'],
            "qty": 1,
            "total_price": product['price'],
            "status": "ordered",
            "created_at": datetime.now()
        })
        flash(f"Bought 1 unit of {product['name']}!", "success")
    else:
        flash("Product not available!", "danger")
    return redirect(url_for('consumer'))

@app.route('/orders')
def view_orders():
    return render_template('orders.html', pending_orders=global_orders, successful_orders=[])

@app.route('/complete-order/<order_id>', methods=['POST'])
def complete_order(order_id):
    global global_orders
    # For demo, just clear the pending orders
    global_orders = []
    flash("Order marked as completed!", "success")
    return redirect(url_for('view_orders'))

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/api/weather')
def weather_api():
    city = request.args.get('city')
    if not city:
        return jsonify({"error": "No city provided"}), 400
    
    api_key = "0940f82f8b3d1a696b7afb88cf181c67"
    if not api_key:
        return jsonify({"error": "API key not configured"}), 500
        
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        daily = defaultdict(list)
        for entry in data["list"]:
            date = entry["dt_txt"].split(" ")[0]
            daily[date].append(entry)
            
        forecast = []
        for date, entries in list(daily.items())[:5]: # 5-day forecast
            temps = [e["main"]["temp"] for e in entries]
            desc = entries[0]["weather"][0]["description"]
            icon = entries[0]["weather"][0]["icon"]
            forecast.append({
                "date": date,
                "min": round(min(temps), 1),
                "max": round(max(temps), 1),
                "desc": desc.capitalize(),
                "icon": icon
            })
            
        return jsonify({
            "city": data["city"]["name"],
            "forecast": forecast
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)
    app.run(debug=True)
