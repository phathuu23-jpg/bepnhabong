import os
import time
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import markupsafe
from email_validator import validate_email, EmailNotValidError

app = Flask(__name__)

# 1. BẢO MẬT SECRET KEY (Lấy từ môi trường hoặc dùng key mặc định)
app.secret_key = os.environ.get('SECRET_KEY', 'bepnhabong_secret_key_2026')

# 2. CẤU HÌNH DATABASE (Tự động thích ứng PostgreSQL trên Render & SQLite ở Local)
db_url = os.environ.get('DATABASE_URL')
if db_url:
    # Render trả về postgres:// nhưng SQLAlchemy cần postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bepnhabong.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cấu hình gửi Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# MODEL CƠ SỞ DỮ LIỆU
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(500), default="https://cdn-icons-png.flaticon.com/512/847/847969.png")
    role = db.Column(db.String(20), default="user")
    reset_otp = db.Column(db.String(6), nullable=True)

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
    author_name = db.Column(db.String(100), default="Bếp Nhà Bông")
    steps = db.relationship('RecipeStep', backref='food', cascade="all, delete-orphan", lazy=True)
    likes = db.relationship('Like', backref='food', cascade="all, delete-orphan", lazy=True)
    comments = db.relationship('Comment', backref='food', cascade="all, delete-orphan", lazy=True)

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

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Lưu id người dùng
    user_name = db.Column(db.String(100), nullable=False)
    user_avatar = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)

@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    escaped_text = str(markupsafe.escape(s))
    return markupsafe.Markup(escaped_text.replace('\n', '<br>\n'))

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_pw = generate_password_hash('admin123')
        new_admin = User(username='admin', email='admin@bepnhabong.com', password=hashed_pw, full_name="Quản Trị Viên", role="admin")
        db.session.add(new_admin)
        db.session.commit()

def save_uploaded_file(file):
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return f"/static/uploads/{filename}"
    return None

CATEGORIES = [
    "Tất cả",
    "Cơm gia đình",
    "Món sáng & Món nước",
    "Ăn vặt & Tráng miệng",
    "Món đãi tiệc & Cuối tuần"
]

# TRANG CHỦ CÓ PHÂN TRANG (PAGINATION)
@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    category = request.args.get('category', 'Tất cả').strip()
    page = request.args.get('page', 1, type=int) # Lấy số trang hiện tại

    foods_query = Food.query.filter_by(status='approved')

    if query:
        foods_query = foods_query.filter(Food.name.ilike(f"%{query}%"))
    
    if category and category != 'Tất cả':
        foods_query = foods_query.filter(Food.category == category)

    # Hiển thị 9 món ăn trên mỗi trang
    pagination = foods_query.order_by(Food.id.desc()).paginate(page=page, per_page=9, error_out=False)
    foods = pagination.items

    return render_template('index.html', 
                           foods=foods, 
                           pagination=pagination,
                           query=query, 
                           selected_category=category, 
                           categories=CATEGORIES)

@app.route('/submit-recipe', methods=['GET', 'POST'])
def submit_recipe():
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category') or "Cơm gia đình"
        time_req = request.form.get('time') or "30 phút"
        servings = request.form.get('servings') or "2 người"
        difficulty = request.form.get('difficulty') or "Dễ"
        ingredients = request.form.get('ingredients')

        main_image = save_uploaded_file(request.files.get('image_file')) or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500"

        is_admin = session.get('role') == 'admin'
        status = 'approved' if is_admin else 'pending'

        new_food = Food(
            name=name.strip(),
            category=category,
            time=time_req,
            servings=servings,
            difficulty=difficulty,
            image=main_image,
            ingredients=ingredients,
            status=status,
            author_name=session.get('user_name', 'Thành viên Bếp')
        )
        db.session.add(new_food)
        db.session.flush()

        step_descriptions = request.form.getlist('step_description[]')
        step_images = request.files.getlist('step_image[]')

        for idx, desc in enumerate(step_descriptions):
            if desc.strip():
                step_img_url = save_uploaded_file(step_images[idx]) if idx < len(step_images) else None
                step = RecipeStep(
                    food_id=new_food.id,
                    step_number=idx + 1,
                    description=desc.strip(),
                    image_url=step_img_url
                )
                db.session.add(step)

        db.session.commit()
        
        if is_admin:
            return redirect(url_for('admin_dashboard'))
        return render_template('submit_success.html', is_admin=is_admin)

    return render_template('submit_recipe.html', categories=CATEGORIES[1:])

@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    if food.status == 'pending' and session.get('role') != 'admin':
        return "Bài viết này đang chờ duyệt!", 403

    related_foods = Food.query.filter(Food.id != food_id, Food.status == 'approved', Food.category == food.category).order_by(Food.id.desc()).limit(3).all()
    user_liked = False
    if session.get('user_id'):
        user_liked = Like.query.filter_by(food_id=food_id, user_id=session.get('user_id')).first() is not None
    return render_template('detail.html', food=food, related_foods=related_foods, user_liked=user_liked)

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    pending_foods = Food.query.filter_by(status='pending').order_by(Food.id.desc()).all()
    approved_foods = Food.query.filter_by(status='approved').order_by(Food.id.desc()).all()
    users_list = User.query.order_by(User.id.desc()).all()
    
    return render_template('admin.html', pending_foods=pending_foods, approved_foods=approved_foods, users=users_list)

@app.route('/admin/reset-user-password/<int:user_id>', methods=['POST'])
def admin_reset_user_password(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    new_password = request.form.get('new_password', '').strip()
    if new_password and len(new_password) >= 6:
        user = User.query.get_or_404(user_id)
        user.password = generate_password_hash(new_password)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    if user.role != 'admin':
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/approve/<int:food_id>')
def approve_food(food_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    food = Food.query.get_or_404(food_id)
    food.status = 'approved'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username_input = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if action == 'register':
            full_name = request.form.get('full_name', '').strip()
            email_input = request.form.get('email', '').strip().lower()
            confirm_pw = request.form.get('confirm_password', '').strip()

            try:
                valid = validate_email(email_input, check_deliverability=True)
                email_input = valid.normalized
            except EmailNotValidError as e:
                return render_template('login.html', error=f"Email không tồn tại hoặc sai định dạng! ({str(e)})")

            if password != confirm_pw:
                return render_template('login.html', error="Mật khẩu và Xác nhận mật khẩu không khớp!")
            
            if len(password) < 6:
                return render_template('login.html', error="Mật khẩu phải chứa ít nhất 6 ký tự!")

            if User.query.filter_by(username=username_input).first():
                return render_template('login.html', error="Tên đăng nhập này đã được sử dụng!")

            if User.query.filter_by(email=email_input).first():
                return render_template('login.html', error="Địa chỉ Email này đã được đăng ký tài khoản khác!")

            hashed_pw = generate_password_hash(password)
            new_user = User(
                username=username_input,
                email=email_input,
                password=hashed_pw,
                full_name=full_name or username_input,
                role="user"
            )
            db.session.add(new_user)
            db.session.commit()

            session['user_logged_in'] = True
            session['user_id'] = new_user.id
            session['user_name'] = new_user.full_name
            session['user_avatar'] = new_user.avatar
            session['role'] = new_user.role
            return redirect(url_for('index'))

        else:
            user = User.query.filter((User.username == username_input) | (User.email == username_input.lower())).first()
            if user and user.password and check_password_hash(user.password, password):
                session['user_logged_in'] = True
                session['user_id'] = user.id
                session['user_name'] = user.full_name or user.username
                session['user_avatar'] = user.avatar
                session['role'] = user.role

                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Email / Tên đăng nhập hoặc mật khẩu không chính xác!")

    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return render_template('forgot_password.html', error="Email này chưa đăng ký trên hệ thống!")

        otp = str(random.randint(100000, 999999))
        user.reset_otp = otp
        db.session.commit()

        try:
            msg = Message("Mã xác nhận khôi phục mật khẩu - Bếp Nhà Bông", recipients=[email])
            msg.body = f"Mã OTP để khôi phục mật khẩu của bạn là: {otp}"
            mail.send(msg)
        except Exception:
            pass

        session['reset_email'] = email
        return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        new_password = request.form.get('password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()

        user = User.query.filter_by(email=email).first()

        if not user or user.reset_otp != otp:
            return render_template('reset_password.html', error="Mã OTP không chính xác!")

        if new_password != confirm_pw:
            return render_template('reset_password.html', error="Mật khẩu không khớp!")

        if len(new_password) < 6:
            return render_template('reset_password.html', error="Mật khẩu tối thiểu 6 ký tự!")

        user.password = generate_password_hash(new_password)
        user.reset_otp = None
        db.session.commit()

        session.pop('reset_email', None)
        return render_template('login.html', success="Đặt lại mật khẩu thành công! Vui lòng đăng nhập lại.")

    return render_template('reset_password.html', email=email)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/like/<int:food_id>', methods=['POST'])
def like_food(food_id):
    if not session.get('user_logged_in'):
        return jsonify({'error': 'unauthorized'}), 401
    
    user_id = session.get('user_id')
    existing_like = Like.query.filter_by(food_id=food_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        new_like = Like(food_id=food_id, user_id=user_id)
        db.session.add(new_like)
        liked = True

    db.session.commit()
    total_likes = Like.query.filter_by(food_id=food_id).count()
    return jsonify({'liked': liked, 'total_likes': total_likes})

@app.route('/comment/<int:food_id>', methods=['POST'])
def add_comment(food_id):
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))

    content = request.form.get('content')
    if content and content.strip():
        comment = Comment(
            food_id=food_id,
            user_id=session.get('user_id'),
            user_name=session.get('user_name', 'Khách'),
            user_avatar=session.get('user_avatar', 'https://cdn-icons-png.flaticon.com/512/847/847969.png'),
            content=content.strip()
        )
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for('detail', food_id=food_id))

# THÊM ROUTE XÓA BÌNH LUẬN
@app.route('/comment/delete/<int:comment_id>')
def delete_comment(comment_id):
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))
        
    comment = Comment.query.get_or_404(comment_id)
    # Cho phép xóa nếu là chủ bình luận hoặc là admin
    if session.get('user_id') == comment.user_id or session.get('role') == 'admin':
        food_id = comment.food_id
        db.session.delete(comment)
        db.session.commit()
        return redirect(url_for('detail', food_id=food_id))
    
    return "Bạn không có quyền xóa bình luận này!", 403

@app.route('/delete/<int:food_id>')
def delete_food(food_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    food = Food.query.get_or_404(food_id)
    db.session.delete(food)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
