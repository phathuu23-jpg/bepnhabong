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
    if low in ("tất cả", "all"):
        return "Tất cả"
    if any(k in low for k in ("công nghệ", "điện tử", "tai nghe", "sạc", "điện thoại", "laptop")):
        return "Công nghệ & Điện tử"
    if any(k in low for k in ("thời trang", "mỹ phẩm", "làm đẹp", "áo", "váy", "giày")):
        return "Thời trang & Mỹ phẩm"
    if any(k in low for k in ("gia dụng", "nhà cửa", "bếp", "nồi", "đời sống")):
        return "Gia dụng"
    if any(k in low for k in ("mã", "voucher", "giảm giá", "coupon")):
        return "Mã giảm giá & Voucher"
    return c if c in CATEGORIES else "Công nghệ & Điện tử"


def build_aff_url(raw_url, sub_id=None):
    url = (raw_url or "").strip()
    if not url:
        return "https://shopee.vn"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if not any(domain in host for domain in ("shopee", "lazada", "s.shopee.vn", "involvey", "goeco", "atplink", "shorten")):
        return url
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    tag = (sub_id or AFF_SUB_ID or "sansale247").strip()
    if tag and "sub_id1" not in query_params and "utm_source" not in query_params:
        query_params["sub_id1"] = tag
        query_params["utm_source"] = tag
    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))


def extract_voucher_code(deal):
    text = f"{deal.ingredients or ''} {deal.difficulty or ''}"
    m = re.search(r'(?:mã|code|voucher)\s*[:\-]?\s*([A-Z0-9_-]{4,24})', text, flags=re.IGNORECASE)
    return m.group(1).upper() if m else ""


def build_social_caption(deal, aff_url):
    code = extract_voucher_code(deal)
    lines = [
        f"🔥 {deal.name}",
        f"💰 Giá săn sale: {deal.price}" + (f" (Giá gốc: {deal.old_price})" if deal.old_price else ""),
    ]
    if deal.discount:
        lines.append(f"📉 Giảm sâu: {deal.discount}")
    if code:
        lines.append(f"🎟️ Nhập mã: {code}")
    lines.append(f"🛒 Link chốt deal: {aff_url}")
    return "\n".join(lines)


@app.route("/go/<int:deal_id>")
def go_deal(deal_id):
    deal = Food.query.get_or_404(deal_id)
    deal.clicks = (deal.clicks or 0) + 1
    db.session.commit()
    target_url = build_aff_url(deal.aff_link, sub_id=f"{AFF_SUB_ID}_deal{deal.id}")
    return redirect(target_url, code=302)


@app.route("/")
def index():
    q = (request.args.get("q") or "").strip()
    cat = (request.args.get("cat") or "").strip()
    platform = (request.args.get("platform") or "").strip().lower()
    deal_type = (request.args.get("type") or "").strip().lower()

    cat_map = {
        "dien-tu": "Công nghệ & Điện tử",
        "gia-dung": "Gia dụng",
        "thoi-trang": "Thời trang & Mỹ phẩm",
        "my-pham": "Thời trang & Mỹ phẩm",
    }
    active_cat = cat_map.get(cat, cat)

    query = Food.query.filter(Food.status == "approved")
    if q:
        like_q = f"%{q}%"
        query = query.filter(
            db.or_(
                Food.name.ilike(like_q),
                Food.ingredients.ilike(like_q),
                Food.difficulty.ilike(like_q),
            )
        )
    if active_cat and active_cat != "Tất cả":
        query = query.filter(Food.category == active_cat)
    if platform in ("shopee", "lazada"):
        query = query.filter(
            db.or_(
                Food.servings.ilike(f"%{platform}%"),
                Food.aff_link.ilike(f"%{platform}%"),
            )
        )
    if deal_type == "voucher":
        query = query.filter(
            db.or_(
                Food.category == "Mã giảm giá & Voucher",
                Food.ingredients.ilike("%mã%"),
                Food.ingredients.ilike("%voucher%"),
                Food.difficulty.ilike("%mã%"),
            )
        )

    rows = query.order_by(Food.clicks.desc(), Food.id.desc()).limit(60).all()
    deals = []
    for r in rows:
        plat = "lazada" if "lazada" in (r.aff_link or "").lower() or "lazada" in (r.servings or "").lower() else "shopee"
        aff_url = build_aff_url(r.aff_link, sub_id=f"{AFF_SUB_ID}_deal{r.id}")
        deals.append({
            "id": r.id,
            "title": r.name,
            "sale_price": r.price,
            "original_price": r.old_price,
            "discount": (r.discount or "").replace("-", "").replace("%", "").strip(),
            "sold_text": r.sold,
            "platform": plat,
            "image_url": r.image or DEFAULT_DEAL_IMAGE,
            "voucher_code": extract_voucher_code(r),
            "aff_url": aff_url,
            "social_caption": build_social_caption(r, aff_url),
            "is_hot": bool((r.clicks or 0) >= 5 or "hot" in (r.difficulty or "").lower()),
            "clicks": r.clicks or 0,
        })

    return render_template(
        "index.html",
        deals=deals,
        q=q,
        active_cat=cat or active_cat,
        categories=CATEGORIES,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next") or url_for("index")
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter(
            db.or_(User.username == username, User.email == username)
        ).first()
        if user and user.password and check_password_hash(user.password, password):
            session.permanent = True
            session["user_id"] = user.id
            return redirect(next_url if next_url.startswith("/") else url_for("index"))
        return render_template_string(
            "<h3>Sai tài khoản hoặc mật khẩu</h3><a href='/login'>Thử lại</a>",
        ), 401
    return render_template_string("""
        <form method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <h2>Đăng nhập Săn Sale 247</h2>
            <input type="text" name="username" placeholder="Username hoặc Email" required>
            <input type="password" name="password" placeholder="Mật khẩu" required>
            <button type="submit">Đăng nhập</button>
        </form>
    """)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        action = request.form.get("action") or "create"
        if action == "delete":
            deal_id = request.form.get("deal_id", type=int)
            item = Food.query.get(deal_id)
            if item:
                db.session.delete(item)
                db.session.commit()
            return redirect(url_for("admin"))

        name = (request.form.get("name") or "").strip()
        if not name:
            return redirect(url_for("admin"))

        category = normalize_category(request.form.get("category"))
        price = (request.form.get("price") or "0đ").strip()
        old_price = (request.form.get("old_price") or "").strip()
        discount = (request.form.get("discount") or "").strip()
        sold = (request.form.get("sold") or "Deal Hot").strip()
        servings = (request.form.get("servings") or "Shopee").strip()
        difficulty = (request.form.get("difficulty") or "Hot Deal").strip()
        image = (request.form.get("image") or DEFAULT_DEAL_IMAGE).strip()
        aff_link = (request.form.get("aff_link") or "https://shopee.vn").strip()
        ingredients = (request.form.get("ingredients") or "").strip()

        new_deal = Food(
            name=name,
            category=category,
            price=price,
            old_price=old_price,
            discount=discount,
            sold=sold,
            servings=servings,
            difficulty=difficulty,
            image=image,
            aff_link=aff_link,
            ingredients=ingredients,
            status="approved",
            author_name=BRAND_AUTHOR,
            author_id=get_current_user().id if get_current_user() else None,
        )
        db.session.add(new_deal)
        db.session.commit()
        return redirect(url_for("admin"))

    all_deals = Food.query.order_by(Food.id.desc()).limit(100).all()
    enriched = []
    for d in all_deals:
        aff = build_aff_url(d.aff_link, sub_id=f"{AFF_SUB_ID}_deal{d.id}")
        enriched.append({
            "obj": d,
            "aff_url": aff,
            "caption": build_social_caption(d, aff),
        })
    return render_template_string("""
        <h2>Quản trị Deal - Săn Sale 247</h2>
        <p><a href="/">Về trang chủ</a> | <a href="/logout">Đăng xuất</a></p>
        <form method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <input type="hidden" name="action" value="create">
            <input type="text" name="name" placeholder="Tên sản phẩm / deal" required><br>
            <input type="text" name="category" placeholder="Danh mục (VD: Công nghệ & Điện tử, Gia dụng...)" value="Công nghệ & Điện tử"><br>
            <input type="text" name="price" placeholder="Giá sale (VD: 149.000đ)" required><br>
            <input type="text" name="old_price" placeholder="Giá gốc (VD: 269.000đ)"><br>
            <input type="text" name="discount" placeholder="% giảm (VD: 45%)"><br>
            <input type="text" name="servings" placeholder="Sàn (Shopee / Lazada)" value="Shopee"><br>
            <input type="text" name="difficulty" placeholder="Nhãn / Mã (VD: HOT DEAL | Mã: SALE50K)"><br>
            <input type="text" name="image" placeholder="Link ảnh sản phẩm"><br>
            <input type="text" name="aff_link" placeholder="Link Affiliate Shopee / Lazada" required><br>
            <textarea name="ingredients" placeholder="Ghi chú & mã giảm giá (VD: Mã: SALE50K, freeship đơn 0đ)"></textarea><br>
            <button type="submit">Đăng Deal</button>
        </form>
        <hr>
        <h3>Danh sách Deal ({{ enriched|length }})</h3>
        {% for row in enriched %}
        <div style="border:1px solid #ccc;padding:10px;margin:10px 0;">
            <strong>#{{ row.obj.id }} - {{ row.obj.name }}</strong> | Giá: {{ row.obj.price }} | Click: <b>{{ row.obj.clicks or 0 }}</b><br>
            <small>Link Aff: {{ row.aff_url }}</small><br>
            <textarea rows="5" cols="60" readonly>{{ row.caption }}</textarea><br>
            <form method="post" style="display:inline;">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="deal_id" value="{{ row.obj.id }}">
                <button type="submit">Xóa</button>
            </form>
        </div>
        {% endfor %}
    """, enriched=enriched)


@app.route("/export.csv")
@admin_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "category", "price", "old_price", "discount", "clicks", "aff_link"])
    for d in Food.query.order_by(Food.id.desc()).all():
        writer.writerow([d.id, d.name, d.category, d.price, d.old_price, d.discount, d.clicks or 0, d.aff_link])
    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sansale247_deals.csv"},
    )


with app.app_context():
    db.create_all()
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    admin_pass = os.environ.get("ADMIN_PASSWORD")
    if admin_pass and not User.query.filter_by(username=admin_user).first():
        u = User(
            username=admin_user,
            password=generate_password_hash(admin_pass),
            full_name=BRAND_AUTHOR,
            role="admin",
        )
        db.session.add(u)
        db.session.commit()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=not IS_PROD)
