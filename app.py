from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'bi_mat_admin'

# Danh sách bài viết dùng chung
foods_list = []

# 1. TRANG CHỦ (Hiển thị món ăn cho khách)
@app.route('/')
def index():
    query = request.args.get('query', '').strip()
    if query:
        filtered_foods = [f for f in foods_list if query.lower() in f['name'].lower()]
    else:
        filtered_foods = foods_list

    return render_template('index.html', foods=filtered_foods, query=query)


# 2. TRANG ADMIN (Thêm bài viết)
@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Nhận dữ liệu từ form admin
        name = request.form.get('name') or request.form.get('title')
        time = request.form.get('time')
        servings = request.form.get('servings')
        image = request.form.get('image') or request.form.get('image_url')
        ingredients = request.form.get('ingredients')
        steps = request.form.get('steps')

        # Tạo món ăn mới
        new_food = {
            "id": len(foods_list) + 1,
            "name": name if name else "Món ăn chưa đặt tên",
            "time": time if time else "30",
            "servings": servings if servings else "2 người",
            "image": image if image else "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500",
            "ingredients": ingredients,
            "steps": steps
        }
        
        # Thêm vào danh sách dùng chung
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

# 4. XÓA MÓN ĂN
@app.route('/delete/<int:food_id>')
def delete_food(food_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    global foods_list
    foods_list = [f for f in foods_list if f['id'] != food_id]
    return redirect(url_for('admin_dashboard'))
# 5. TRANG CHI TIẾT MÓN ĂN (Sửa lỗi 404 Không tìm thấy)
@app.route('/detail/<int:food_id>')
def detail(food_id):
    # Tìm món ăn theo ID
    food = next((f for f in foods_list if f['id'] == food_id), None)
    if not food:
        return "Không tìm thấy công thức món ăn này!", 404
    
    return render_template('detail.html', food=food)

if __name__ == '__main__':
    app.run(debug=True)