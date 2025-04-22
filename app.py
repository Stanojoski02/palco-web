from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from functools import wraps
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = 'tajna_lozinka'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax'
)
DATABASE = 'database.db'

limiter = Limiter(get_remote_address, app=app)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT,
        regular_price REAL,
        discount_price REAL)''')
    conn.commit()
    conn.close()

def remove_cyrillic(text):
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ѓ': 'gj', 'е': 'e', 'ж': 'zh', 'з': 'z', 'ѕ': 'dz',
        'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n', 'њ': 'nj', 'о': 'o', 'п': 'p',
        'р': 'r', 'с': 's', 'т': 't', 'ќ': 'kj', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'џ': 'dj',
        'ш': 'sh', 'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Ѓ': 'Gj', 'Е': 'E', 'Ж': 'Zh', 'З': 'Z',
        'Ѕ': 'Dz', 'И': 'I', 'Ј': 'J', 'К': 'K', 'Л': 'L', 'Љ': 'Lj', 'М': 'M', 'Н': 'N', 'Њ': 'Nj', 'О': 'O',
        'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'Ќ': 'Kj', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'Ch',
        'Џ': 'Dj', 'Ш': 'Sh'
    }
    return ''.join(mapping.get(c, c) for c in text)

@app.context_processor
def inject_date():
    return {'current_date': datetime.now().strftime('%d.%m.%Y')}

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            flash('Најави се за да пристапиш.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def home():
    return render_template('home.html')

@limiter.limit("5 per minute")
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session['user'] = user['username']
            return redirect(url_for('product_list'))
        else:
            flash('Неточни податоци.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/products')
def product_list():
    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form.get('description')
        regular_price = float(request.form.get('regular_price') or 0)
        discount_price = float(request.form.get('discount_price') or 0)
        if not name or price < 0 or len(name) > 100:
            flash("Невалиден внес.")
            return redirect(url_for('add_product'))
        conn = get_db()
        conn.execute("INSERT INTO products (name, price, description, regular_price, discount_price) VALUES (?, ?, ?, ?, ?)",
                     (name, price, description, regular_price, discount_price))
        conn.commit()
        conn.close()
        return redirect(url_for('product_list'))
    return render_template('add_product.html')

@app.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form.get('description')
        regular_price = float(request.form.get('regular_price') or 0)
        discount_price = float(request.form.get('discount_price') or 0)
        if not name or price < 0 or len(name) > 100:
            flash("Невалиден внес.")
            return redirect(url_for('edit_product', product_id=product_id))
        conn.execute("UPDATE products SET name=?, price=?, description=?, regular_price=?, discount_price=? WHERE id=?",
                     (name, price, description, regular_price, discount_price, product_id))
        conn.commit()
        conn.close()
        return redirect(url_for('product_list'))
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    conn = get_db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('product_list'))

@app.route('/download-pdf')
def download_pdf():
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 10)

    p.drawString(50, 800, f"Lista na proizvodi - {datetime.now().strftime('%d.%m.%Y')}")
    y = 780

    # Заглавие
    headers = ["ID", "Naziv", "Prodazna", "Redovna", "Popust", "Opis"]
    x_positions = [50, 90, 230, 300, 380, 450]

    y -= 20
    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)
    y -= 5
    p.line(50, y, 550, y)
    y -= 15

    conn = get_db()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    for prod in products:
        if y < 100:
            p.showPage()
            p.setFont("Helvetica", 10)
            y = 800
        name = remove_cyrillic(prod['name'])
        desc = remove_cyrillic(prod['description'] or "")
        p.drawString(x_positions[0], y, str(prod['id']))
        p.drawString(x_positions[1], y, name[:30])
        p.drawString(x_positions[2], y, f"{prod['price']:.2f}")
        p.drawString(x_positions[3], y, f"{prod['regular_price'] or 0:.2f}")
        p.drawString(x_positions[4], y, f"{prod['discount_price'] or 0:.2f}")
        p.drawString(x_positions[5], y, desc[:40])
        y -= 20

    p.save()
    buffer.seek(0)
    return make_response(buffer.read(), {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename=proizvodi.pdf'
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
