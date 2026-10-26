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
    # OTP quên mật khẩu: chỉ lưu bản băm, có hạn dùng và giới hạn số lần thử
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
    """Món yêu thích (lưu lại để xem sau)."""
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
    rating = db.Column(db.Integer, nullable=True)  # 1-5 sao, có thể bỏ trống


@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    escaped_text = str(markupsafe.escape(s))
    return markupsafe.Markup(escaped_text.replace('\n', '<br>\n'))


# ============================================================
# 3. BẢO MẬT: CSRF, HEADER, GIỚI HẠN TẦN SUẤT
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
    if len(_attempts) > 20000:  # dọn bớt để không phình bộ nhớ
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
            session.clear()  # tài khoản đã bị xóa
        else:
            session['role'] = user.role  # luôn lấy quyền thật từ database


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
    """Admin hoặc chính tác giả của món."""
    user = get_current_user()
    if not user:
        return False
    return user.role == 'admin' or (food.author_id is not None and food.author_id == user.id)


def start_session(user):
    session.clear()  # chống session fixation
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
    """Trả về đường dẫn ảnh, None nếu không chọn file, ném UploadError nếu file không hợp lệ."""
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
    return url if url.startswith('https://') and len(url) <= 500 else None


# ============================================================
# 6. KHỞI TẠO DATABASE + TỰ NÂNG CẤP BẢNG CŨ
# ============================================================
def ensure_columns():
    """db.create_all() không thêm cột mới vào bảng đã có, nên thêm thủ công."""
    wanted = {
        'user': {'otp_hash': 'VARCHAR(100)', 'otp_expires': 'TIMESTAMP', 'otp_attempts': 'INTEGER DEFAULT 0'},
        'food': {'author_id': 'INTEGER'},
        'comment': {'rating': 'INTEGER'},
    }
    insp = inspect(db.engine)
    for table, cols in wanted.items():
        if not insp.has_table(table):
            continue
        have = {c['name'] for c in insp.get_columns(table)}
        for name, ddl in cols.items():
            if name not in have:
                db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
    db.session.commit()


def backfill_authors():
    """Gán author_id cho bài cũ nếu tìm được đúng 1 tài khoản trùng tên tác giả."""
    orphans = Food.query.filter(Food.author_id.is_(None), Food.author_name != BRAND_AUTHOR).all()
    for f in orphans:
        matches = User.query.filter((User.full_name == f.author_name) | (User.username == f.author_name)).all()
        if len(matches) == 1:
            f.author_id = matches[0].id
    db.session.commit()


def ensure_admin():
    admin_pw = os.environ.get('ADMIN_PASSWORD')
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        pw = admin_pw or secrets.token_urlsafe(12)
        if not admin_pw:
            log.warning("Chưa đặt ADMIN_PASSWORD. Mật khẩu admin tạo ngẫu nhiên (ghi lại và đổi ngay): %s", pw)
        db.session.add(User(username='admin', email='admin@bepnhabong.com',
                            password=generate_password_hash(pw),
                            full_name="Quản Trị Viên", role="admin"))
        db.session.commit()
    elif admin.password and check_password_hash(admin.password, 'admin123'):
        if admin_pw:
            admin.password = generate_password_hash(admin_pw)
            db.session.commit()
            log.info("Đã thay mật khẩu admin mặc định bằng ADMIN_PASSWORD.")
        else:
            log.warning("CẢNH BÁO: admin vẫn dùng mật khẩu mặc định 'admin123'. Hãy đặt ADMIN_PASSWORD.")


def seed_initial_data():
    if Food.query.count() > 0:  # chỉ nạp món mẫu khi database còn trống
        return
    for item in SAMPLE_FOODS:
        f = Food(name=item["name"], category=item["category"], time=item["time"],
                 servings=item["servings"], difficulty=item["difficulty"],
                 image=item["image"], ingredients=item["ingredients"],
                 status="approved", author_name=BRAND_AUTHOR)
        db.session.add(f)
        db.session.flush()
        for idx, desc in enumerate(item["steps"]):
            db.session.add(RecipeStep(food_id=f.id, step_number=idx + 1, description=desc))
    db.session.commit()


with app.app_context():
    try:
        db.create_all()
        ensure_columns()
        ensure_admin()
        backfill_authors()
        seed_initial_data()
    except Exception:  # nhiều worker khởi động cùng lúc có thể va chạm, worker khác sẽ làm xong
        db.session.rollback()
        log.exception("Khởi tạo database gặp lỗi (có thể do worker khác đang chạy).")


# ============================================================
# 7. TRANG CHỦ, CHI TIẾT
# ============================================================
@app.route('/')
def index():
    query = request.args.get('query', '').strip()[:100]
    category = request.args.get('category', 'Tất cả').strip()
    page = max(request.args.get('page', 1, type=int), 1)

    foods_query = Food.query.filter_by(status='approved')
    if query:
        foods_query = foods_query.filter(func.lower(Food.name).contains(query.lower(), autoescape=True))
    if category in CATEGORIES and category != 'Tất cả':
        foods_query = foods_query.filter(Food.category == category)

    pagination = foods_query.order_by(Food.id.desc()).paginate(page=page, per_page=9, error_out=False)
    return render_template('index.html', foods=pagination.items, pagination=pagination,
                           query=query, selected_category=category, categories=CATEGORIES)


@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    if food.status != 'approved' and not can_manage(food):
        abort(403)

    related_foods = (Food.query.filter(Food.id != food_id, Food.status == 'approved',
                                       Food.category == food.category)
                     .order_by(Food.id.desc()).limit(3).all())

    user = get_current_user()
    user_liked = user_favorited = False
    if user:
        user_liked = Like.query.filter_by(food_id=food_id, user_id=user.id).first() is not None
        user_favorited = Favorite.query.filter_by(food_id=food_id, user_id=user.id).first() is not None

    avg, count = (db.session.query(func.avg(Comment.rating), func.count(Comment.rating))
                  .filter(Comment.food_id == food_id, Comment.rating.isnot(None)).first())
    avg_rating = round(float(avg), 1) if avg else None

    return render_template('detail.html', food=food, related_foods=related_foods,
                           user_liked=user_liked, user_favorited=user_favorited,
                           avg_rating=avg_rating, rating_count=count or 0,
                           can_edit=can_manage(food))


# ============================================================
# 8. ĐĂNG / SỬA / XÓA MÓN
# ============================================================
def parse_recipe_form():
    category = request.form.get('category') or CATEGORIES[1]
    if category not in CATEGORIES[1:]:
        category = CATEGORIES[1]
    data = {
        'name': (request.form.get('name') or '').strip(),
        'category': category,
        'time': (request.form.get('time') or '30 phút').strip()[:50],
        'servings': (request.form.get('servings') or '2 người').strip()[:50],
        'difficulty': (request.form.get('difficulty') or 'Dễ').strip()[:50],
        'ingredients': (request.form.get('ingredients') or '').strip()[:5000],
    }
    error = None
    if not data['name'] or len(data['name']) > 200:
        error = "Tên món không được để trống (tối đa 200 ký tự)!"
    elif not data['ingredients']:
        error = "Vui lòng nhập nguyên liệu!"
    return data, error


def read_steps(existing_images=None):
    """Đọc các bước làm. Giữ lại ảnh cũ nếu không tải ảnh mới."""
    descs = request.form.getlist('step_description[]')[:MAX_STEPS]
    files = request.files.getlist('step_image[]')
    keeps = request.form.getlist('step_image_keep[]')
    steps = []
    for idx, desc in enumerate(descs):
        desc = desc.strip()[:2000]
        if not desc:
            continue
        img = save_uploaded_file(files[idx]) if idx < len(files) else None
        if not img:
            if keeps:
                if idx < len(keeps) and keeps[idx].startswith('/static/uploads/'):
                    img = keeps[idx]
            elif existing_images and idx < len(existing_images):
                img = existing_images[idx]
        steps.append((desc, img))
    return steps


@app.route('/submit-recipe', methods=['GET', 'POST'])
@login_required
def submit_recipe():
    user = get_current_user()
    if request.method == 'POST':
        if rate_limited(f"post:{user.id}", 10, 3600):
            return render_template('submit_recipe.html', categories=CATEGORIES[1:],
                                   error="Bạn đăng bài quá nhanh, vui lòng thử lại sau."), 429
        data, error = parse_recipe_form()
        if error:
            return render_template('submit_recipe.html', categories=CATEGORIES[1:], error=error), 400
        try:
            main_image = save_uploaded_file(request.files.get('image_file')) or DEFAULT_FOOD_IMAGE
            steps = read_steps()
        except UploadError as e:
            return render_template('submit_recipe.html', categories=CATEGORIES[1:], error=str(e)), 400

        hit(f"post:{user.id}")
        is_admin = user.role == 'admin'
        food = Food(**data, image=main_image,
                    status='approved' if is_admin else 'pending',
                    author_name=user.full_name or user.username, author_id=user.id)
        db.session.add(food)
        db.session.flush()
        for idx, (desc, img) in enumerate(steps):
            db.session.add(RecipeStep(food_id=food.id, step_number=idx + 1,
                                      description=desc, image_url=img))
        db.session.commit()

        if is_admin:
            return redirect(url_for('admin_dashboard'))
        return render_template('submit_success.html', is_admin=is_admin)

    return render_template('submit_recipe.html', categories=CATEGORIES[1:])


@app.route('/edit-recipe/<int:food_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(food_id):
    food = Food.query.get_or_404(food_id)
    if not can_manage(food):
        abort(403)
    user = get_current_user()

    if request.method == 'POST':
        data, error = parse_recipe_form()
        if error:
            return render_template('edit_recipe.html', food=food, categories=CATEGORIES[1:], error=error), 400
        try:
            new_image = save_uploaded_file(request.files.get('image_file'))
            steps = read_steps([s.image_url for s in food.steps])
        except UploadError as e:
            return render_template('edit_recipe.html', food=food, categories=CATEGORIES[1:], error=str(e)), 400

        for k, v in data.items():
            setattr(food, k, v)
        if new_image:
            food.image = new_image
        else:
            ext_url = valid_external_image(request.form.get('image_url'))
            if ext_url:
                food.image = ext_url

        RecipeStep.query.filter_by(food_id=food.id).delete()
        for idx, (desc, img) in enumerate(steps):
            db.session.add(RecipeStep(food_id=food.id, step_number=idx + 1,
                                      description=desc, image_url=img))
        # Thành viên sửa bài thì phải chờ admin duyệt lại
        if user.role != 'admin':
            food.status = 'pending'
        db.session.commit()
        return redirect(url_for('detail', food_id=food.id))

    return render_template('edit_recipe.html', food=food, categories=CATEGORIES[1:])


@app.route('/delete/<int:food_id>', methods=['POST'])
@login_required
def delete_food(food_id):
    food = Food.query.get_or_404(food_id)
    if not can_manage(food):
        abort(403)
    db.session.delete(food)
    db.session.commit()
    if get_current_user().role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('my_recipes'))


@app.route('/my-recipes')
@login_required
def my_recipes():
    user = get_current_user()
    page = max(request.args.get('page', 1, type=int), 1)
    pagination = (Food.query.filter_by(author_id=user.id)
                  .order_by(Food.id.desc()).paginate(page=page, per_page=9, error_out=False))
    return render_template('my_recipes.html', foods=pagination.items, pagination=pagination)


# ============================================================
# 9. LIKE, YÊU THÍCH, BÌNH LUẬN + ĐÁNH GIÁ
# ============================================================
def approved_food_or_404(food_id):
    food = Food.query.get_or_404(food_id)
    if food.status != 'approved':
        abort(404)
    return food


@app.route('/like/<int:food_id>', methods=['POST'])
def like_food(food_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    approved_food_or_404(food_id)

    existing = Like.query.filter_by(food_id=food_id, user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(food_id=food_id, user_id=user.id))
        liked = True
    db.session.commit()
    return jsonify({'liked': liked, 'total_likes': Like.query.filter_by(food_id=food_id).count()})


@app.route('/favorite/<int:food_id>', methods=['POST'])
def toggle_favorite(food_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    approved_food_or_404(food_id)

    existing = Favorite.query.filter_by(food_id=food_id, user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        favorited = False
    else:
        db.session.add(Favorite(food_id=food_id, user_id=user.id))
        favorited = True
    db.session.commit()
    return jsonify({'favorited': favorited})


@app.route('/my-favorites')
@login_required
def my_favorites():
    user = get_current_user()
    page = max(request.args.get('page', 1, type=int), 1)
    pagination = (Food.query.join(Favorite, Favorite.food_id == Food.id)
                  .filter(Favorite.user_id == user.id, Food.status == 'approved')
                  .order_by(Favorite.id.desc()).paginate(page=page, per_page=9, error_out=False))
    return render_template('my_favorites.html', foods=pagination.items, pagination=pagination)


@app.route('/comment/<int:food_id>', methods=['POST'])
@login_required
def add_comment(food_id):
    user = get_current_user()
    approved_food_or_404(food_id)

    if rate_limited(f"cmt:{user.id}", 10, 60):
        abort(429)
    content = (request.form.get('content') or '').strip()[:1000]
    rating = request.form.get('rating', type=int)
    if rating is not None and not 1 <= rating <= 5:
        rating = None

    if content:
        hit(f"cmt:{user.id}")
        db.session.add(Comment(food_id=food_id, user_id=user.id,
                               user_name=user.full_name or user.username,
                               user_avatar=user.avatar or DEFAULT_AVATAR,
                               content=content, rating=rating))
        db.session.commit()
    return redirect(url_for('detail', food_id=food_id))


@app.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    user = get_current_user()
    comment = Comment.query.get_or_404(comment_id)
    if user.id != comment.user_id and user.role != 'admin':
        abort(403)
    food_id = comment.food_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('detail', food_id=food_id))


# ============================================================
# 10. QUẢN TRỊ
# ============================================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    pending_foods = Food.query.filter_by(status='pending').order_by(Food.id.desc()).all()
    approved_foods = Food.query.filter_by(status='approved').order_by(Food.id.desc()).all()
    users_list = User.query.order_by(User.id.desc()).all()
    return render_template('admin.html', pending_foods=pending_foods,
                           approved_foods=approved_foods, users=users_list)


@app.route('/admin/reset-user-password/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_user_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) >= MIN_PASSWORD:
        user = User.query.get_or_404(user_id)
        user.password = generate_password_hash(new_password)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != 'admin':
        # dọn dữ liệu liên quan để không bị lỗi khóa ngoại
        Like.query.filter_by(user_id=user.id).delete()
        Favorite.query.filter_by(user_id=user.id).delete()
        Comment.query.filter_by(user_id=user.id).update({'user_id': None})
        Food.query.filter_by(author_id=user.id).update({'author_id': None})
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/approve/<int:food_id>', methods=['POST'])
@admin_required
def approve_food(food_id):
    food = Food.query.get_or_404(food_id)
    food.status = 'approved'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# ============================================================
# 11. ĐĂNG NHẬP / ĐĂNG KÝ / QUÊN MẬT KHẨU
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username_input = request.form.get('username', '').strip()[:120]
        password = request.form.get('password', '').strip()
        ip = client_ip()

        if action == 'register':
            if rate_limited(f"reg:{ip}", 5, 3600):
                return render_template('login.html', error="Bạn đăng ký quá nhiều lần. Vui lòng thử lại sau!"), 429
            hit(f"reg:{ip}")

            full_name = request.form.get('full_name', '').strip()[:100]
            email_input = request.form.get('email', '').strip().lower()
            confirm_pw = request.form.get('confirm_password', '').strip()

            if not USERNAME_RE.match(username_input):
                return render_template('login.html', error="Tên đăng nhập gồm 3-30 ký tự: chữ, số, dấu _ hoặc dấu chấm!")
            try:
                valid = validate_email(email_input, check_deliverability=True)
                email_input = valid.normalized
            except EmailNotValidError as e:
                return render_template('login.html', error=f"Email không tồn tại hoặc sai định dạng! ({str(e)})")

            if password != confirm_pw:
                return render_template('login.html', error="Mật khẩu và Xác nhận mật khẩu không khớp!")
            if len(password) < MIN_PASSWORD:
                return render_template('login.html', error=f"Mật khẩu phải chứa ít nhất {MIN_PASSWORD} ký tự!")
            if password.lower() == username_input.lower():
                return render_template('login.html', error="Mật khẩu không được trùng tên đăng nhập!")
            if User.query.filter(func.lower(User.username) == username_input.lower()).first():
                return render_template('login.html', error="Tên đăng nhập này đã được sử dụng!")
            if User.query.filter_by(email=email_input).first():
                return render_template('login.html', error="Địa chỉ Email này đã được đăng ký tài khoản khác!")

            new_user = User(username=username_input, email=email_input,
                            password=generate_password_hash(password),
                            full_name=full_name or username_input, role="user")
            db.session.add(new_user)
            db.session.commit()
            start_session(new_user)
            return redirect(url_for('index'))

        # ---- Đăng nhập ----
        key_user = f"login:{ip}:{username_input.lower()}"
        key_ip = f"login-ip:{ip}"
        if rate_limited(key_user, 5, 600) or rate_limited(key_ip, 30, 600):
            return render_template('login.html',
                                   error="Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 10 phút!"), 429

        user = User.query.filter((User.username == username_input) |
                                 (User.email == username_input.lower())).first()
        if user and user.password and check_password_hash(user.password, password):
            _attempts.pop(key_user, None)
            start_session(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))

        if not user:  # tốn thời gian như khi có user, tránh dò tên đăng nhập qua độ trễ
            check_password_hash(_DUMMY_HASH, password)
        hit(key_user)
        hit(key_ip)
        return render_template('login.html', error="Email / Tên đăng nhập hoặc mật khẩu không chính xác!")

    return render_template('login.html')


_DUMMY_HASH = generate_password_hash(secrets.token_hex(8))


def _hash_otp(otp):
    return hmac.new(app.secret_key.encode(), otp.encode(), hashlib.sha256).hexdigest()


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()[:120]
        ip = client_ip()
        if rate_limited(f"forgot:{ip}", 5, 900) or rate_limited(f"forgot-mail:{email}", 3, 900):
            return render_template('forgot_password.html',
                                   error="Bạn yêu cầu quá nhiều lần. Vui lòng thử lại sau 15 phút!"), 429
        hit(f"forgot:{ip}")
        hit(f"forgot-mail:{email}")

        user = User.query.filter_by(email=email).first()
        if user:
            otp = str(secrets.randbelow(900000) + 100000)
            user.otp_hash = _hash_otp(otp)
            user.otp_expires = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
            user.otp_attempts = 0
            db.session.commit()
            if app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'):
                try:
                    msg = Message("Mã xác nhận khôi phục mật khẩu - Bếp Nhà Bông", recipients=[email])
                    msg.body = (f"Mã OTP để khôi phục mật khẩu của bạn là: {otp}\n"
                                f"Mã có hiệu lực trong {OTP_TTL_MINUTES} phút. "
                                "Nếu không phải bạn yêu cầu, hãy bỏ qua email này.")
                    mail.send(msg)
                except Exception:
                    log.exception("Gửi email OTP thất bại")
            else:
                log.error("Chưa cấu hình MAIL_USERNAME / MAIL_PASSWORD nên không gửi được OTP.")

        # Luôn chuyển sang bước nhập mã dù email có tồn tại hay không (không để lộ email nào đã đăng ký)
        session['reset_email'] = email
        return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        if rate_limited(f"reset:{client_ip()}", 10, 900):
            return render_template('reset_password.html', email=email,
                                   error="Bạn thử quá nhiều lần. Vui lòng thử lại sau!"), 429
        hit(f"reset:{client_ip()}")

        otp = request.form.get('otp', '').strip()
        new_password = request.form.get('password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()

        if new_password != confirm_pw:
            return render_template('reset_password.html', email=email, error="Mật khẩu không khớp!")
        if len(new_password) < MIN_PASSWORD:
            return render_template('reset_password.html', email=email,
                                   error=f"Mật khẩu tối thiểu {MIN_PASSWORD} ký tự!")

        bad_otp = "Mã OTP không chính xác hoặc đã hết hạn!"
        user = User.query.filter_by(email=email).first()
        if (not user or not user.otp_hash or not user.otp_expires
                or user.otp_expires < datetime.utcnow()
                or (user.otp_attempts or 0) >= OTP_MAX_ATTEMPTS):
            return render_template('reset_password.html', email=email, error=bad_otp)

        if not hmac.compare_digest(user.otp_hash, _hash_otp(otp)):
            user.otp_attempts = (user.otp_attempts or 0) + 1
            if user.otp_attempts >= OTP_MAX_ATTEMPTS:
                user.otp_hash = None
                user.otp_expires = None
            db.session.commit()
            return render_template('reset_password.html', email=email, error=bad_otp)

        user.password = generate_password_hash(new_password)
        user.otp_hash = None
        user.otp_expires = None
        user.otp_attempts = 0
        db.session.commit()

        session.pop('reset_email', None)
        return render_template('login.html', success="Đặt lại mật khẩu thành công! Vui lòng đăng nhập lại.")

    return render_template('reset_password.html', email=email)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


# ============================================================
# 12. TRANG LỖI
# ============================================================
@app.errorhandler(400)
def err_400(e):
    return "Yêu cầu không hợp lệ hoặc phiên làm việc đã hết hạn. Hãy quay lại, tải lại trang rồi thử lại.", 400


@app.errorhandler(403)
def err_403(e):
    return "Bạn không có quyền thực hiện thao tác này.", 403


@app.errorhandler(404)
def err_404(e):
    return "Không tìm thấy trang hoặc món ăn này.", 404


@app.errorhandler(413)
def err_413(e):
    return "File tải lên quá lớn (tối đa 25MB mỗi lần gửi).", 413


@app.errorhandler(429)
def err_429(e):
    return "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.", 429


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
