import os
import re
import csv
import io
import hmac
import secrets
import logging
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from flask import Flask, render_template, request, redirect, url_for, session, abort, g, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import markupsafe
from sqlalchemy import UniqueConstraint

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
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,
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
DEFAULT_DEAL_IMAGE = "https://cdn-icons-png.flaticon.com/512/3523/3523063.png"
BRAND_AUTHOR = "San Sale 247"
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.]{3,30}$')
CATEGORIES = [
    "Tất cả",
    "Công nghệ & Điện tử",
    "Thời trang & Mỹ phẩm",
    "Gia dụng",
    "Mã giảm giá & Voucher",
]
AFF_SUB_ID = os.environ.get('AFF_SUB_ID', 'sansale247')


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
    category = db.Column(db.String(100), default="Công nghệ & Điện tử")
    time = db.Column(db.String(50), default="Hôm nay")
    servings = db.Column(db.String(50), default="Shopee / Lazada")
    difficulty = db.Column(db.String(50), default="Hot Deal")
    image = db.Column(db.String(500), nullable=False)
    aff_link = db.Column(db.String(1000), default="https://shopee.vn")
    price = db.Column(db.String(50), default="Liên hệ")
    old_price = db.Column(db.String(50), default="")
    discount = db.Column(db.String(20), default="")
    sold = db.Column(db.String(50), default="Deal Hot")
    ingredients = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(20), default="approved")
    author_name = db.Column(db.String(100), default=BRAND_AUTHOR)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    clicks = db.Column(db.Integer, default=0)


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


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        u = get_current_user()
        if not u or u.role != 'admin':
            return redirect(url_for('login') + '?next=' + request.path)
        return view(*a, **k)
    return wrapped


def normalize_category(cat_str):
    c = re.sub(r'\s+', ' ', str(cat_str or '').strip())
    if not c:
        return "Công nghệ & Điện tử"
    low = c.lower()
    if low in ("tất cả",
