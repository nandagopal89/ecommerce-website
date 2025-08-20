from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ecommerce.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    attributes = db.relationship("Attribute", backref="category", cascade="all, delete-orphan")
    products = db.relationship("Product", backref="category", cascade="all, delete-orphan")

class Attribute(db.Model):
    __tablename__ = "attributes"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    data_type = db.Column(db.String(20), nullable=False, default="text")

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    values = db.relationship("ProductAttributeValue", backref="product", cascade="all, delete-orphan")

class ProductAttributeValue(db.Model):
    __tablename__ = "product_attribute_values"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey("attributes.id"), nullable=False)
    value = db.Column(db.String(500), nullable=False)
    attribute = db.relationship("Attribute")

def validate_value(attr: Attribute, raw: str):
    t = attr.data_type
    if t == "number":
        float(raw)
    elif t == "boolean":
        if str(raw).lower() not in ("true", "false", "1", "0", "on", "off"):
            raise ValueError("boolean must be true/false/1/0")
    elif t == "date":
        datetime.strptime(str(raw), "%Y-%m-%d")

@app.before_request
def init_db():
    db.create_all()

@app.route("/")
def dashboard():
    counts = {"categories": Category.query.count(), "products": Product.query.count(), "attributes": Attribute.query.count()}
    latest = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    return render_template("index.html", counts=counts, latest=latest)

@app.get("/categories")
def categories_page():
    categories = Category.query.order_by(Category.name).all()
    return render_template("categories.html", categories=categories)

@app.post("/categories")
def create_category():
    name = (request.form.get("name") or "").strip()
    if not name:
        abort(400, "Category name required")
    if Category.query.filter_by(name=name).first():
        abort(409, "Category already exists")
    db.session.add(Category(name=name))
    db.session.commit()
    return redirect(url_for("categories_page"))

@app.get("/categories/<int:category_id>")
def category_attributes_page(category_id):
    cat = Category.query.get_or_404(category_id)
    attrs = Attribute.query.filter_by(category_id=category_id).all()
    return render_template("category_attributes.html", category=cat, attrs=attrs)

@app.post("/categories/<int:category_id>/attributes")
def add_attribute(category_id):
    Category.query.get_or_404(category_id)
    name = (request.form.get("name") or "").strip()
    data_type = (request.form.get("data_type") or "text").lower()
    if data_type not in ("text", "number", "boolean", "date"):
        abort(400, "data_type must be text | number | boolean | date")
    if not name:
        abort(400, "Attribute name required")
    db.session.add(Attribute(category_id=category_id, name=name, data_type=data_type))
    db.session.commit()
    return redirect(url_for("category_attributes_page", category_id=category_id))

@app.get("/products")
def products_page():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("products.html", products=products, categories=categories)

@app.post("/products")
def create_product():
    name = (request.form.get("name") or "").strip()
    price = float(request.form.get("price") or 0)
    category_id = int(request.form.get("category_id"))
    Category.query.get_or_404(category_id)
    if not name:
        abort(400, "Product name required")
    p = Product(name=name, price=price, category_id=category_id)
    db.session.add(p)
    db.session.commit()
    return redirect(url_for("edit_product", product_id=p.id))

@app.get("/products/<int:product_id>/edit")
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    attrs = Attribute.query.filter_by(category_id=p.category_id).all()
    existing = {v.attribute_id: v.value for v in p.values}
    return render_template("edit_product.html", product=p, attrs=attrs, existing=existing)

@app.post("/products/<int:product_id>/edit")
def save_product_values(product_id):
    p = Product.query.get_or_404(product_id)
    attrs = Attribute.query.filter_by(category_id=p.category_id).all()
    for a in attrs:
        field = f"attr_{a.id}"
        raw = request.form.get(field)
        if a.data_type == "boolean":
            raw = "true" if request.form.get(field) in ("on", "true", "1") else "false"
        if raw is None:
            continue
        validate_value(a, raw)
        row = ProductAttributeValue.query.filter_by(product_id=p.id, attribute_id=a.id).first()
        if row:
            row.value = str(raw)
        else:
            db.session.add(ProductAttributeValue(product_id=p.id, attribute_id=a.id, value=str(raw)))
    db.session.commit()
    return redirect(url_for("products_page"))

@app.get("/seed")
def seed():
    if Category.query.filter_by(name="Dresses").first() is None:
        dresses = Category(name="Dresses")
        shoes = Category(name="Shoes")
        db.session.add_all([dresses, shoes])
        db.session.flush()
        db.session.add_all([
            Attribute(category_id=dresses.id, name="Size", data_type="text"),
            Attribute(category_id=dresses.id, name="Color", data_type="text"),
            Attribute(category_id=shoes.id,   name="Size", data_type="number"),
            Attribute(category_id=shoes.id,   name="Material", data_type="text"),
        ])
        db.session.commit()
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)