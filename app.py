import os
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "kisan_kart_secret"

# Simple In-Memory Storage
products = [
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
        "_id": "Potato",
        "category": "Grains",
        "price": 120.0,
        "qty": 50,
        "area": "Punjab",
        "description": "Long-grain aromatic basmati rice from the fields of Punjab.",
        "image": "background2.png",
        "status": "available"
    }
]
orders = []

@app.context_processor
def inject_globals():
    return dict(is_demo_mode=True, current_user={'name': 'Guest User', 'is_authenticated': True, 'type': 'customer'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/farmer', methods=['GET', 'POST'])
def farmer():
    if request.method == 'POST':
        name = request.form.get('crop_name')
        price = float(request.form.get('price', 0))
        qty = int(request.form.get('quantity', 0))
        
        new_prod = {
            "_id": str(len(products) + 1),
            "name": name,
            "category": "Fresh Produce",
            "price": price,
            "qty": qty,
            "area": request.form.get('area'),
            "description": f"Grown in {request.form.get('area')}",
            "image": "background.png", 
            "status": "available"
        }
        products.append(new_prod)
        flash(f"Crop '{name}' added successfully!", "success")
        return redirect(url_for('consumer'))

    return render_template('list_product.html')

@app.route('/consumer')
def consumer():
    return render_template('shop.html', products=products)

@app.route('/buy/<product_id>', methods=['POST'])
def buy_product(product_id):
    product = next((p for p in products if p["_id"] == product_id), None)
    if product and product['qty'] > 0:
        product['qty'] -= 1
        orders.append({
            "product_name": product['name'],
            "qty": 1,
            "total_price": product['price'],
            "status": "ordered",
            "created_at": datetime.now()
        })
        flash(f"Bought 1 unit of {product['name']}!", "success")
    return redirect(url_for('consumer'))

@app.route('/orders')
def view_orders():
    return render_template('orders.html', pending_orders=orders, successful_orders=[])

# Redirect legacy routes to the new simple ones
@app.route('/login')
def login(): return redirect(url_for('index'))

@app.route('/logout')
def logout(): return redirect(url_for('index'))

@app.route('/discover')
def discover(): return redirect(url_for('consumer'))

@app.route('/list-product')
def list_product_legacy(): return redirect(url_for('farmer'))

if __name__ == '__main__':
    app.run(debug=True)
