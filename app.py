import os
import re
import time
import uuid
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, abort, g)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import markupsafe
from email_validator import validate_email, EmailNotValidError
from sqlalchemy import func, inspect, text, UniqueConstraint

from seed_data import SAMPLE_FOODS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bepnhabong")

# ============================================================
# 1. CẤU HÌNH
# ============================================================
IS_PROD = bool(os.environ.get('RENDER')) or os.environ.get('APP_ENV') == 'production'

app = Flask(__name__)
# Render đứng sau proxy: lấy đúng IP khách và giao thức https
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    if IS_PROD:
        raise RuntimeError("Thiếu biến môi trường SECRET_KEY. Hãy đặt một chuỗi ngẫu nhiên dài trên Render.")
    _secret = secrets.token_hex(32)  # chỉ dùng khi chạy thử trên máy
app.secret_key = _secret

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=IS_PROD,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,  # tổng dung lượng 1 lần gửi form: 25MB
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bepnhabong.db')

# Gửi mail (Gmail + App Password)
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
BRAND_AUTHOR = "Bếp Nhà Bông"
MIN_PASSWORD = 8
MAX_STEPS = 30
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.]{3,30}$')

CATEGORIES = [
    "Tất cả",
    "Cơm gia đình",
    "Món sáng & Món nước",
    "Ăn vặt & Tráng miệng",
    "Món đãi tiệc & Cuối tuần"
]

# ============================================================
# 2. MODEL
# ============================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(500), default=DEFAULT_AVATAR)
    role = db.Column(db.String(20), default="user")
    otp_hash = db.Column(db.String(100), nullable=True)
    otp_expires = db.Column(db.DateTime, nullable=True)
    otp_attempts = db.Column(db.Integer, default=0)


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), default="Cơm gia đình")
    time = db.Column(db.String(50), default="30 phút")
    servings = db.Column(db.String(50), default="2 người")
    difficulty = db.Column(db.String(50), default="Dễ")
    image = db.Column(db.String(500), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="approved")
    author_name = db.Column(db.String(100), default=BRAND_AUTHOR)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    steps = db.relationship('RecipeStep', backref='food', cascade="all, delete-orphan",
                            lazy=True, order_by='RecipeStep.step_number')
    likes = db.relationship('Like', backref='food', cascade="all, delete-orphan", lazy=True)
    comments = db.relationship('Comment', backref='food', cascade="all, delete-orphan", lazy=True)
    favorites = db.relationship('Favorite', backref='food', cascade="all, delete-orphan", lazy=True)


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
    escaped_text = str(markupsafe.escape(s))
    return markupsafe.Markup(escaped_text.replace('\n', '<br>\n'))


# ============================================================
# 3. BẢO MẬT: CSRF, HEADER, RATE LIMIT
# ============================================================
def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(32)
    return session['_csrf']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def csrf_protect():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        expected = session.get('_csrf')
        sent = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not expected or not sent or not hmac.compare_digest(expected, sent):
            abort(400)


@app.after_request
def security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if IS_PROD:
        resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return resp


_attempts = {}


def rate_limited(key, limit, window):
    now = time.time()
    if len(_attempts) > 20000:
        for k in list(_attempts):
            _attempts[k] = [t for t in _attempts[k] if now - t < 3600]
            if not _attempts[k]:
                del _attempts[k]
    recent = [t for t in _attempts.get(key, []) if now - t < window]
    _attempts[key] = recent
    return len(recent) >= limit


def hit(key):
    _attempts.setdefault(key, []).append(time.time())


def client_ip():
    return request.remote_addr or 'unknown'


# ============================================================
# 4. NGƯỜI DÙNG & PHÂN QUYỀN
# ============================================================
def get_current_user():
    if 'current_user' not in g:
        uid = session.get('user_id')
        g.current_user = User.query.get(uid) if uid else None
    return g.current_user


@app.before_request
def load_user():
    if session.get('user_id'):
        user = get_current_user()
        if not user:
            session.clear()
        else:
            session['role'] = user.role


@app.context_processor
def inject_user():
    return {'current_user': get_current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for('login'))
        if user.role != 'admin':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def can_manage(food):
    user = get_current_user()
    if not user:
        return False
    return user.role == 'admin' or (food.author_id is not None and food.author_id == user.id)


def start_session(user):
    session.clear()
    session.permanent = True
    session['user_logged_in'] = True
    session['user_id'] = user.id
    session['user_name'] = user.full_name or user.username
    session['user_avatar'] = user.avatar or DEFAULT_AVATAR
    session['role'] = user.role


# ============================================================
# 5. UPLOAD ẢNH AN TOÀN
# ============================================================
class UploadError(Exception):
    pass


def _looks_like_image(head):
    return (head.startswith(b'\xff\xd8\xff')
            or head.startswith(b'\x89PNG\r\n\x1a\n')
            or head[:6] in (b'GIF87a', b'GIF89a')
            or (head[:4] == b'RIFF' and head[8:12] == b'WEBP'))


def save_uploaded_file(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXT:
        raise UploadError("Chỉ cho phép ảnh JPG, PNG, GIF hoặc WEBP!")
    head = file.stream.read(16)
    file.stream.seek(0)
    if not _looks_like_image(head):
        raise UploadError("File tải lên không phải ảnh hợp lệ!")
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"/static/uploads/{filename}"


def valid_external_image(url):
    url = (url or '').strip()
    return url if url.startswith('https://') and len
