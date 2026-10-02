import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import markupsafe

app = Flask(__name__)
app.secret_key = 'bepnhabong_secret_key_2026'

# Cấu hình CSDL SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'bepnhabong.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cấu hình thư mục lưu ảnh
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Bảng lưu Người dùng / Admin
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Bảng lưu Bài viết / Món ăn
class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), default="30 phút")
    servings = db.Column(db.String(50), default="2 người")
    image = db.Column(db.String(500), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    steps = db.Column(db.Text, nullable=False)

# Bộ lọc tự động đổi ký tự xuống dòng (\n) thành thẻ <br> trong HTML
@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    escaped_text = str(markupsafe.escape(s))
    return markupsafe.Markup(escaped_text.replace('\n', '<br>\n'))

# Khoi tao CSDL va Tai khoan Admin bao mat
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_pw = generate_password_hash('admin123')
        new_admin = User(username='admin', password=hashed_pw)
        db.session.add(new_admin)
        db.session.commit()

# 1. TRANG CHỦ
@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    if query:
        foods = Food.query.filter(Food.name.ilike(f"%{query}%")).order_by(Food.id.desc()).all()
    else:
        foods = Food.query.order_by(Food.id.desc()).all()
    return render_template('index.html', foods=foods, query=query)

# 2. TRANG ADMIN & ĐĂNG BÀI
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        time = request.form.get('time') or "30 phút"
        servings = request.form.get('servings') or "2 người"
        ingredients = request.form.get('ingredients')
        steps = request.form.get('steps')

        image_url = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500"
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_url = f"/static/uploads/{filename}"

        new_food = Food(
            name=name.strip(),
            time=time,
            servings=servings,
            image=image_url,
            ingredients=ingredients,
            steps=steps
        )
        db.session.add(new_food)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    foods = Food.query.order_by(Food.id.desc()).all()
    return render_template('admin.html', foods=foods)

# 3. CHỈNH SỬA MÓN ĂN
@app.route('/edit/<int:food_id>', methods=['GET', 'POST'])
def edit_food(food_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    food = Food.query.get_or_404(food_id)
    if request.method == 'POST':
        food.name = request.form.get('name')
        food.time = request.form.get('time')
        food.servings = request.form.get('servings')
        food.ingredients = request.form.get('ingredients')
        food.steps = request.form.get('steps')

        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            food.image = f"/static/uploads/{filename}"

        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    return render_template('edit.html', food=food)

# 4. XÓA MÓN ĂN
@app.route('/delete/<int:food_id>')
def delete_food(food_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    food = Food.query.get_or_404(food_id)
    db.session.delete(food)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# 5. ĐĂNG NHẬP / ĐĂNG XUẤT (BẢO MẬT TÀI KHOẢN)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html', error="Tên đăng nhập hoặc mật khẩu không chính xác!")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 6. CHI TIẾT MÓN ĂN (CÓ MÓN GỢI Ý)
@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    # Lấy 3 món ăn khác làm món gợi ý
    related_foods = Food.query.filter(Food.id != food_id).order_by(Food.id.desc()).limit(3).all()
    return render_template('detail.html', food=food, related_foods=related_foods)

# 7. TRANG LỖI 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
