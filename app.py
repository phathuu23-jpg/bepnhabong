import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
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

# Bảng Admin
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Bảng Món ăn
class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), default="30 phút")
    servings = db.Column(db.String(50), default="2 người")
    image = db.Column(db.String(500), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    steps = db.relationship('RecipeStep', backref='food', cascade="all, delete-orphan", lazy=True)

# Bảng Lưu các bước nấu kèm Ảnh
class RecipeStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)

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
        new_admin = User(username='admin', password=hashed_pw)
        db.session.add(new_admin)
        db.session.commit()

# Hàm hỗ trợ lưu file ảnh
def save_uploaded_file(file):
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        # Thêm timestamp tránh trùng tên file
        import time
        filename = f"{int(time.time())}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return f"/static/uploads/{filename}"
    return None

@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    if query:
        foods = Food.query.filter(Food.name.ilike(f"%{query}%")).order_by(Food.id.desc()).all()
    else:
        foods = Food.query.order_by(Food.id.desc()).all()
    return render_template('index.html', foods=foods, query=query)

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        time = request.form.get('time') or "30 phút"
        servings = request.form.get('servings') or "2 người"
        ingredients = request.form.get('ingredients')

        # Ảnh đại diện món ăn
        main_image = save_uploaded_file(request.files.get('image_file')) or "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500"

        new_food = Food(
            name=name.strip(),
            time=time,
            servings=servings,
            image=main_image,
            ingredients=ingredients
        )
        db.session.add(new_food)
        db.session.flush() # Lấy new_food.id

        # Xử lý các bước nấu ăn đính kèm ảnh
        step_descriptions = request.form.getlist('step_description[]')
        step_images = request.files.getlist('step_image[]')

        for idx, desc in enumerate(step_descriptions):
            if desc.strip():
                step_img_url = None
                if idx < len(step_images):
                    step_img_url = save_uploaded_file(step_images[idx])
                
                step = RecipeStep(
                    food_id=new_food.id,
                    step_number=idx + 1,
                    description=desc.strip(),
                    image_url=step_img_url
                )
                db.session.add(step)

        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    foods = Food.query.order_by(Food.id.desc()).all()
    return render_template('admin.html', foods=foods)

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

        main_img = save_uploaded_file(request.files.get('image_file'))
        if main_img:
            food.image = main_img

        # Xóa các bước cũ để cập nhật các bước mới
        RecipeStep.query.filter_by(food_id=food.id).delete()

        step_descriptions = request.form.getlist('step_description[]')
        step_images = request.files.getlist('step_image[]')

        for idx, desc in enumerate(step_descriptions):
            if desc.strip():
                step_img_url = save_uploaded_file(step_images[idx]) if idx < len(step_images) else None
                # Nếu không tải ảnh mới, giữ ảnh cũ (nếu có hidden input)
                existing_img = request.form.get(f'existing_step_image_{idx}')
                if not step_img_url and existing_img:
                    step_img_url = existing_img

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
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    food = Food.query.get_or_404(food_id)
    db.session.delete(food)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

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

@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = Food.query.get_or_404(food_id)
    related_foods = Food.query.filter(Food.id != food_id).order_by(Food.id.desc()).limit(3).all()
    return render_template('detail.html', food=food, related_foods=related_foods)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
