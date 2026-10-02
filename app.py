import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'bi_mat_admin'

# Cấu hình thư mục lưu ảnh tải lên
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Danh sách món ăn dùng chung
foods_list = []

# 1. TRANG CHỦ
@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    if query:
        filtered_foods = [f for f in foods_list if query.lower() in f['name'].lower()]
    else:
        filtered_foods = foods_list
    return render_template('index.html', foods=filtered_foods, query=query)

# 2. TRANG ADMIN & ĐĂNG BÀI
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name') or request.form.get('title')
        time = request.form.get('time')
        servings = request.form.get('servings')
        ingredients = request.form.get('ingredients')
        steps = request.form.get('steps')

        # Xử lý tải file ảnh trực tiếp từ máy/điện thoại
        image_url = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500" # Ảnh mặc định
        file = request.files.get('image_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Thêm id vào tên file để tránh trùng tên ảnh
            save_name = f"{len(foods_list) + 1}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], save_name)
            file.save(file_path)
            image_url = f"/static/uploads/{save_name}"

        new_food = {
            "id": len(foods_list) + 1,
            "name": name.strip() if name else "Món ăn chưa đặt tên",
            "time": time if time else "30 phút",
            "servings": servings if servings else "2 người",
            "image": image_url,
            "ingredients": ingredients,
            "steps": steps
        }
        
        foods_list.append(new_food)
        return redirect(url_for('admin_dashboard'))

    return render_template('admin.html', foods=foods_list)

# 3. ĐĂNG NHẬP
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == '123456':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return "Sai tài khoản hoặc mật khẩu!"
    return render_template('login.html')

# 4. ĐĂNG XUẤT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 5. XÓA MÓN ĂN
@app.route('/delete/<int:food_id>')
def delete_food(food_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    global foods_list
    foods_list = [f for f in foods_list if f['id'] != food_id]
    return redirect(url_for('admin_dashboard'))

# 6. TRANG CHI TIẾT
@app.route('/detail/<int:food_id>')
def detail(food_id):
    food = next((f for f in foods_list if f['id'] == food_id), None)
    if not food:
        return "Không tìm thấy công thức món ăn này!", 404
    return render_template('detail.html', food=food)

if __name__ == '__main__':
    app.run(debug=True)
