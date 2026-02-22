import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from bson.objectid import ObjectId
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "kisan_kart_secret"
is_demo_mode = False

class MockCollection:
    def __init__(self): self.data = []
    def find_one(self, query):
        for item in self.data:
            if all(item.get(k) == v or (k=="_id" and str(item.get(k))==str(v)) for k, v in query.items()):
                return item
        return None
    def insert_one(self, doc):
        if "_id" not in doc: doc["_id"] = ObjectId()
        self.data.append(doc)
        return type('obj', (object,), {'inserted_id': doc["_id"]})
    def find(self, query=None):
        if not query or query == {"status": "available"}: return self.data
        return self.data
    def update_one(self, query, update):
        item = self.find_one(query)
        if item and "$inc" in update:
            for k, v in update["$inc"].items(): item[k] += v
        return None
    def delete_one(self, query):
        item = self.find_one(query)
        if item: self.data.remove(item)
    def create_index(self, keys): pass

class MockDB:
    def __init__(self):
        self.farmers = MockCollection()
        self.customers = MockCollection()
        self.products = MockCollection()
        self.orders = MockCollection()
        self.successful_orders = MockCollection()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()
    db = client['kisankart']
    print("Connected to MongoDB!")
except Exception as e:
    print(f"MongoDB not found. Starting in DEMO MODE (In-memory storage). Error: {e}")
    db = MockDB()
    is_demo_mode = True

@app.context_processor
def inject_demo_mode():
    return dict(is_demo_mode=is_demo_mode)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data['name']
        self.type = user_data['type']

@login_manager.user_loader
def load_user(user_id):
    user_data = db.farmers.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        user_data = db.customers.find_one({"_id": ObjectId(user_id)})
    
    if user_data:
        return User(user_data)
    return None

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register/farmer', methods=['GET', 'POST'])
def register_farmer():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        
        if db.farmers.find_one({"name": name}) or db.customers.find_one({"name": name}):
            flash("Username already exists!", "danger")
            return redirect(url_for('register_farmer'))

        photo = request.files.get('photo')
        photo_filename = ""
        if photo and allowed_file(photo.filename):
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], photo_filename))
        
        farmer_data = {
            "name": name,
            "password": generate_password_hash(password),
            "bio": request.form.get('bio'),
            "location": request.form.get('location'),
            "certs": request.form.get('certs'),
            "photo": photo_filename,
            "type": "farmer"
        }
        
        if lat and lng:
            farmer_data["location_geo"] = {
                "type": "Point",
                "coordinates": [float(lng), float(lat)]
            }
            
        db.farmers.insert_one(farmer_data)
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))
        
    return render_template('register_farmer.html')

@app.route('/register/customer', methods=['GET', 'POST'])
def register_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        lat = request.form.get('lat')
        lng = request.form.get('lng')

        if db.farmers.find_one({"name": name}) or db.customers.find_one({"name": name}):
            flash("Username already exists!", "danger")
            return redirect(url_for('register_customer'))
            
        customer_data = {
            "name": name,
            "password": generate_password_hash(password),
            "phone": request.form.get('phone'),
            "location": request.form.get('location'),
            "bucket": [],
            "previous_orders": [],
            "type": "customer"
        }
        
        if lat and lng:
            customer_data["location_geo"] = {
                "type": "Point",
                "coordinates": [float(lng), float(lat)]
            }
            
        db.customers.insert_one(customer_data)
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register_customer.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        
        user_data = db.farmers.find_one({"name": name})
        if not user_data:
            user_data = db.customers.find_one({"name": name})
            
        if user_data and check_password_hash(user_data['password'], password):
            user_obj = User(user_data)
            login_user(user_obj)
            flash(f"Welcome back, {name}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password", "danger")
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/list-product', methods=['GET', 'POST'])
@login_required
def list_product():
    if current_user.type != 'farmer':
        flash("Only farmers can list products!", "danger")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = float(request.form.get('price', 0))
        qty = int(request.form.get('qty', 0))
        harvest_date = request.form.get('harvest_date')
        expiry_date = request.form.get('expiry_date')
        description = request.form.get('description')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        
        image = request.files.get('product_image')
        image_filename = ""
        if image and allowed_file(image.filename):
            image_filename = secure_filename(image.filename)
            prod_img_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(prod_img_path, exist_ok=True)
            image.save(os.path.join(prod_img_path, image_filename))
        
        product_data = {
            "farmer_id": ObjectId(current_user.id),
            "name": name,
            "category": category,
            "price": price,
            "qty": qty,
            "harvest_date": harvest_date,
            "expiry_date": expiry_date,
            "description": description,
            "image": image_filename,
            "status": "available"
        }
        
        if lat and lng:
            product_data["location_geo"] = {
                "type": "Point",
                "coordinates": [float(lng), float(lat)]
            }
            
        db.products.insert_one(product_data)
        flash(f"Product '{name}' listed successfully!", "success")
        return redirect(url_for('discover'))

    return render_template('list_product.html')

@app.route('/discover')
def discover():
    products = []
    if current_user.is_authenticated and current_user.type == 'customer':
        customer_data = db.customers.find_one({"_id": ObjectId(current_user.id)})
        if customer_data and "location_geo" in customer_data:
            products = list(db.products.find({
                "status": "available",
                "location_geo": {
                    "$near": {
                        "$geometry": customer_data["location_geo"],
                        "$maxDistance": 50000 
                    }
                }
            }))
            
    if not products:
        products = list(db.products.find({"status": "available"}))
        
    today = datetime.now().strftime('%Y-%m-%d')
    for product in products:
        product['is_expired'] = product.get('expiry_date') < today
    return render_template('discover.html', products=products, today=today)

@app.route('/product/<product_id>')
def product_detail(product_id):
    product = db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for('discover'))
    return render_template('product_detail.html', product=product)

@app.route('/buy/<product_id>', methods=['POST'])
@login_required
def buy_product(product_id):
    if current_user.type != 'customer':
        flash("Only customers can buy products!", "danger")
        return redirect(url_for('index'))
        
    product = db.products.find_one({"_id": ObjectId(product_id)})
    if not product:
        flash("Product not found!", "danger")
        return redirect(url_for('discover'))
    
    qty = int(request.form.get('buy_qty', 1))
    payment_method = request.form.get('payment_method')
    
    if qty > product['qty']:
        flash("Not enough stock available!", "warning")
        return redirect(url_for('product_detail', product_id=product_id))

    order_data = {
        "customer_id": ObjectId(current_user.id),
        "product_id": ObjectId(product_id),
        "product_name": product['name'],
        "qty": qty,
        "total_price": qty * product['price'],
        "payment_method": payment_method,
        "status": "pending",
        "created_at": datetime.now()
    }
    db.orders.insert_one(order_data)
    
    db.products.update_one(
        {"_id": ObjectId(product_id)},
        {"$inc": {"qty": -qty}}
    )
    
    flash(f"Order for {qty} {product['name']}(s) placed successfully!", "success")
    return redirect(url_for('view_orders'))

@app.route('/orders')
@login_required
def view_orders():
    if current_user.type == 'customer':
        pending_orders = list(db.orders.find({"customer_id": ObjectId(current_user.id), "status": "pending"}))
        successful_orders = list(db.successful_orders.find({"customer_id": ObjectId(current_user.id)}))
    else:
        prods = list(db.products.find({"farmer_id": ObjectId(current_user.id)}))
        prod_ids = [p['_id'] for p in prods]
        pending_orders = list(db.orders.find({"product_id": {"$in": prod_ids}, "status": "pending"}))
        successful_orders = list(db.successful_orders.find({"product_id": {"$in": prod_ids}}))
        
    return render_template('orders.html', pending_orders=pending_orders, successful_orders=successful_orders)

@app.route('/complete-order/<order_id>', methods=['POST'])
def complete_order(order_id):
    order = db.orders.find_one({"_id": ObjectId(order_id)})
    if order:
        db.successful_orders.insert_one({
            **order,
            "status": "successful",
            "delivered_at": datetime.now()
        })
        db.orders.delete_one({"_id": ObjectId(order_id)})
        flash("Order delivered successfully!", "success")
    return redirect(url_for('view_orders'))

try:
    db.farmers.create_index([("location_geo", "2dsphere")])
    db.products.create_index([("location_geo", "2dsphere")])
except Exception as e:
    print("Geo index creation error (expected if local DB not ready):", e)

if __name__ == '__main__':
    os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)
    app.run(debug=True)
