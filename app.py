import os
import re
import time
import uuid
import hmac
import secrets
import logging
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, g
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from werkzeug.security import generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import markupsafe
from sqlalchemy import UniqueConstraint
from seed_data import SAMPLE_FOODS
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sansale247")
IS_PROD = bool(os.environ.get('RENDER')) or os.environ.get('APP_ENV') == 'production'
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    if IS_PROD:
        raise RuntimeError("Thieu SECRET_KEY tren Render.")
    _secret = secrets.token_hex(32)
app.secret_key = _secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=IS_PROD,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=25*1024*1024,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sansale247.db')
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
db = SQLAlchemy(app)
DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/847/847969.png"
DEFAULT_FOOD_IMAGE = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500"
BRAND_AUTHOR = "San Sale 247"
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.]{3,30}$')
CATEGORIES = ["Tat ca", "Cong nghe & Dien tu", "Thoi trang & My pham", "Doi song & Gia dung", "Ma giam gia & Voucher"]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(500), default=DEFAULT_AVATAR)
    role = db.Column(db.String(20), default="user")

class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), default="Cong nghe & Dien tu")
    time = db.Column(db.String(50), default="Hom nay")
    servings = db.Column(db.String(50), default="Shopee / Lazada")
    difficulty = db.Column(db.String(50), default="Hot Deal")
    image = db.Column(db.String(500), nullable=False)
    aff_link = db.Column(db.String(1000), default="https://shopee.vn")
    price = db.Column(db.String(50), default="0")
    old_price = db.Column(db.String(50), default="")
    discount = db.Column(db.String(20), default="")
    sold = db.Column(db.String(50), default="DA BAN 0")
    ingredients = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), default="approved")
    author_name = db.Column(db.String(100), default=BRAND_AUTHOR)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class RecipeStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'food_id', name='uq_favorite_user_food'),)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_avatar = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)

@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    return markupsafe.Markup(str(markupsafe.escape(s)).replace('\n', '<br>\n'))

def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(32)
    return session['_csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def csrf_protect():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        exp = session.get('_csrf')
        sent = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not exp or not sent or not hmac.compare_digest(exp, sent):
            abort(400)

@app.after_request
def security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return resp

def get_current_user():
    if 'current_user' not in g:
        uid = session.get('user_id')
        g.current_user = User.query.get(uid) if uid else None
    return g.current_user

@app.before_request
def load_user():
    if session.get('user_id'):
        u = get_current_user()
        if not u:
            session.clear()

@app.context_processor
def inject_user():
    return {'current_user': get_current_user()}

def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if not get_current_user():
            return redirect(url_for('login'))
        return view(*a, **k)
    return wrapped

@app.route('/')
def index():
    query = request.args.get('q', '').strip()
    cat = request.args.get('cat', 'Tat ca')
    q = Food.query.filter_by(status='approved')
    if cat and cat != 'Tat ca':
        q = q.filter_by(category=cat)
    if query:
        q = q.filter(Food.name.ilike(f'%{query}%'))
    foods = q.order_by(Food.id.desc()).all()
    return render_template('index.html', foods=foods, categories=CATEGORIES, selected_cat=cat, query=query)

@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/flashsale')
def flashsale():
    query = request.args.get('q', '').strip()
    cat = request.args.get('cat', 'Tat ca')
    q = Food.query.filter_by(status='approved')
    if cat and cat != 'Tat ca':
        q = q.filter_by(category=cat)
    if query:
        q = q.filter(Food.name.ilike(f'%{query}%'))
    foods = q.order_by(Food.id.desc()).all()
    return render_template('flashsale.html', foods=foods, categories=CATEGORIES, selected_cat=cat, query=query)

@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    return render_template('detail.html', food=food)

@app.route('/my-recipes')
@login_required
def my_recipes():
    foods = Food.query.filter_by(author_id=get_current_user().id).order_by(Food.id.desc()).all()
    return render_template('my_recipes.html', foods=foods)

@app.route('/my-favorites')
@login_required
def my_favorites():
    favs = Favorite.query.filter_by(user_id=get_current_user().id).all()
    foods = [f.food for f in favs if f.food]
    return render_template('my_favorites.html', foods=foods)

@app.route('/login')
def login():
    return "<h3>Trang dang nhap demo</h3><a href='/'>Ve trang chu</a>"

def init_db():
    with app.app_context():
        db.create_all()
        try:
            with db.engine.connect() as c:
                cols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(food)").fetchall()]
                for col, default in [('aff_link', "'https://shopee.vn'"), ('price', "'0'"), ('old_price', "''"), ('discount', "''"), ('sold', "'DA BAN 0'")]:
                    if col not in cols:
                        c.exec_driver_sql(f"ALTER TABLE food ADD COLUMN {col} VARCHAR(1000) DEFAULT {default}")
                        c.commit()
        except Exception as e:
            log.info(f"skip migrate: {e}")
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', email='admin@sansale247.com', password=generate_password_hash(admin_pass), full_name='Quan Tri Vien', role='admin'))
            db.session.commit()
            log.info("Da tao admin.")
        if Food.query.count() == 0:
            try:
                from seed_data import SAMPLE_FOODS as _S
            except Exception:
                _S = []
            for item in _S:
                db.session.add(Food(name=item.get('name', 'Deal hot'), category=item.get('category', 'Cong nghe'), time=item.get('time', 'Hom nay'), servings=item.get('servings', 'Shopee'), difficulty=item.get('difficulty', 'Hot'), image=item.get('image', DEFAULT_FOOD_IMAGE), ingredients=item.get('ingredients', ''), status='approved', author_name=BRAND_AUTHOR))
            if _S:
                db.session.commit()

init_db()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
