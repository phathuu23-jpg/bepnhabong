import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import markupsafe

app = Flask(__name__)
app.secret_key = 'bepnhabong_secret_key_2026'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bepnhabong.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Bảng Người dùng
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    avatar = db.Column(db.String(500), default="https://cdn-icons-png.flaticon.com/512/847/847969.png")
    role = db.Column(db.String(20), default="user") # 'admin' hoặc 'user'

# Bảng Món ăn
class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), default="30 phút")
    servings = db.Column(db.String(50), default="2 người")
    image = db.Column(db.String(500), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="approved") # 'approved' hoặc 'pending'
    author_name = db.Column(db.String(100), default="Bếp Nhà Bông")
    steps = db.relationship('RecipeStep', backref='food', cascade="all, delete-orphan", lazy=True)
    likes = db.relationship('Like', backref='food', cascade="all, delete-orphan", lazy=True)
    comments = db.relationship('Comment', backref='food', cascade="all, delete-orphan", lazy=True)

# Bảng Các bước nấu
class RecipeStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)

# Bảng Thả tim
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Bảng Bình luận
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
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
    # Tạo tài khoản Admin mặc định
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_pw = generate_password_hash('admin123')
        new_admin = User(username='admin', password=hashed_pw, full_name="Quản Trị Viên", role="admin")
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

# 1. TRANG CHỦ
@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    if query:
        foods = Food.query.filter(Food.status == 'approved', Food.name.ilike(f"%{query}%")).order_by(Food.id.desc()).all()
    else:
        foods = Food.query.filter_by(status='approved').order_by(Food.id.desc()).all()
    return render_template('index.html', foods=foods, query=query)

# 2. ĐĂNG BÀI (Cho cả Admin và Khách hàng)
@app.route('/submit-recipe', methods=['GET', 'POST'])
def submit_recipe():
    # Nếu chưa đăng nhập thì bắt đăng nhập
    if not session.get('user_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        time_req = request.form.get('time') or "30 phút"
        servings = request.form.get('servings') or "2 người"
        ingredients = request.form.get('ingredients')

        main_image = save_uploaded_file(request.files.get('image_file')) or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500"

        # Nếu là ADMIN thì tự động duyệt (approved), nếu là KHÁCH thì (pending)
        is_admin = session.get('role') == 'admin'
        status = 'approved' if is_admin else 'pending'

        new_food = Food(
            name=name.strip(),
            time=time_req,
            servings=servings,
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

    return render_template('submit_recipe.html')

# 3. TRANG CHI TIẾT MÓN ĂN (Cho phép Admin xem cả bài chờ duyệt)
@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    
    # Kiểm tra: nếu bài chưa duyệt (pending) mà không phải Admin thì không cho xem
    if food.status == 'pending' and session.get('role') != 'admin':
        return "Bài viết này đang chờ duyệt!", 403

    related_foods = Food.query.filter(Food.id != food_id, Food.status == 'approved').order_by(Food.id.desc()).limit(3).all()
    user_liked = False
    if session.get('user_id'):
        user_liked = Like.query.filter_by(food_id=food_id, user_id=session.get('user_id')).first() is not None
    return render_template('detail.html', food=food, related_foods=related_foods, user_liked=user_liked)

# 4. TRANG QUẢN TRỊ ADMIN (Xem & Duyệt bài)
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    pending_foods = Food.query.filter_by(status='pending').order_by(Food.id.desc()).all()
    approved_foods = Food.query.filter_by(status='approved').order_by(Food.id.desc()).all()
    return render_template('admin.html', pending_foods=pending_foods, approved_foods=approved_foods)

@app.route('/admin/approve/<int:food_id>')
def approve_food(food_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    food = Food.query.get_or_404(food_id)
    food.status = 'approved'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# 5. XỬ LÝ ĐĂNG NHẬP & TỰ ĐỘNG TẠO TÀI KHỎAN CHO KHÁCH
# 5. XỬ LÝ ĐĂNG NHẬP & ĐĂNG KÝ TÀI KHỎAN CHUẨN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if action == 'register':
            full_name = request.form.get('full_name', '').strip()
            # Kiểm tra xem tên đăng nhập đã tồn tại chưa
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return render_template('login.html', error="Tên đăng nhập này đã có người dùng, vui lòng chọn tên khác!")
            
            hashed_pw = generate_password_hash(password)
            new_user = User(
                username=username,
                password=hashed_pw,
                full_name=full_name or username,
                role="user"
            )
            db.session.add(new_user)
            db.session.commit()

            # Đăng ký xong tự động đăng nhập luôn
            session['user_logged_in'] = True
            session['user_id'] = new_user.id
            session['user_name'] = new_user.full_name
            session['user_avatar'] = new_user.avatar
            session['role'] = new_user.role
            return redirect(url_for('index'))

        else: # Đăng nhập
            user = User.query.filter_by(username=username).first()
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
                return render_template('login.html', error="Tên đăng nhập hoặc mật khẩu không chính xác!")

    return render_template('login.html')
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            if user.password and check_password_hash(user.password, password):
                session['user_logged_in'] = True
                session['user_id'] = user.id
                session['user_name'] = user.full_name or user.username
                session['user_avatar'] = user.avatar
                session['role'] = user.role
                
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Mật khẩu không chính xác!")
        else:
            # Nếu chưa có tài khoản, tự động tạo mới tài khoản Khách hàng
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw, full_name=username, role="user")
            db.session.add(new_user)
            db.session.commit()

            session['user_logged_in'] = True
            session['user_id'] = new_user.id
            session['user_name'] = new_user.full_name
            session['user_avatar'] = new_user.avatar
            session['role'] = new_user.role
            return redirect(url_for('index'))

    return render_template('login.html')

# 6. ĐĂNG NHẬP NHANH GOOGLE / FACEBOOK
@app.route('/login-social/<provider>')
def login_social(provider):
    if provider == 'google':
        username = "google_user"
        full_name = "Thành viên Google"
        avatar = "https://cdn-icons-png.flaticon.com/512/300/300221.png"
    else:
        username = "facebook_user"
        full_name = "Thành viên Facebook"
        avatar = "https://cdn-icons-png.flaticon.com/512/5968/5968764.png"

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, full_name=full_name, avatar=avatar, role="user")
        db.session.add(user)
        db.session.commit()

    session['user_logged_in'] = True
    session['user_id'] = user.id
    session['user_name'] = user.full_name
    session['user_avatar'] = user.avatar
    session['role'] = user.role

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 7. THẢ TIM & BÌNH LUẬN
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
            user_name=session.get('user_name', 'Khách'),
            user_avatar=session.get('user_avatar', 'https://cdn-icons-png.flaticon.com/512/847/847969.png'),
            content=content.strip()
        )
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for('detail', food_id=food_id))

@app.route('/edit/<int:food_id>', methods=['GET', 'POST'])
def edit_food(food_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    food = Food.query.get_or_404(food_id)
    if request.method == 'POST':
        food.name = request.form.get('name')
        food.time = request.form.get('time')
        food.servings = request.form.get('servings')
        food.ingredients = request.form.get('ingredients')
        main_img = save_uploaded_file(request.files.get('image_file'))
        if main_img:
            food.image = main_img

        RecipeStep.query.filter_by(food_id=food.id).delete()
        step_descriptions = request.form.getlist('step_description[]')
        step_images = request.files.getlist('step_image[]')

        for idx, desc in enumerate(step_descriptions):
            if desc.strip():
                step_img_url = save_uploaded_file(step_images[idx]) if idx < len(step_images) else None
                step = RecipeStep(
                    food_id=food.id,
                    step_number=idx + 1,
                    description=desc.strip(),
                    image_url=step_img_url
                )
                db.session.add(step)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('edit.html', food=food)

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
