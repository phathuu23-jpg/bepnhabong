from app import app, db, Food, RecipeStep

def init_database():
    with app.app_context():
        # Tạo cấu trúc bảng trong CSDL nếu chưa có
        db.create_all()
        
        # Kiểm tra nếu chưa có dữ liệu thì mới thêm
        if Food.query.count() == 0:
            print("Đang nạp dữ liệu món ăn...")
            
            # --- MÓN 1: PHỞ BÒ ---
            pho = Food(
                name="Phở Bò Hà Nội",
                description="Món phở bò truyền thống thơm ngon đậm đà phong vị Bắc.",
                image_url="https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=600",
                category="Món nước",
                cooking_time="120 phút",
                servings="4 người"
            )
            db.session.add(pho)
            db.session.flush()

            pho_steps = [
                RecipeStep(food_id=pho.id, step_number=1, instruction="Hầm xương bò với hành tây, gừng nướng trong 2 giờ để lấy nước dùng."),
                RecipeStep(food_id=pho.id, step_number=2, instruction="Chần bánh phở qua nước sôi rồi xếp vào tô."),
                RecipeStep(food_id=pho.id, step_number=3, instruction="Xếp thịt bò tái/chín lên trên, rắc hành lá và múc nước dùng đang sôi chế vào tô.")
            ]
            db.session.add_all(pho_steps)

            # --- MÓN 2: BÚN CHẢ ---
            buncha = Food(
                name="Bún Chả Hà Nội",
                description="Chả nướng than hoa thơm lừng ăn kèm bún và nước chấm chua ngọt.",
                image_url="https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=600",
                category="Món bún",
                cooking_time="45 phút",
                servings="2 người"
            )
            db.session.add(buncha)
            db.session.flush()

            buncha_steps = [
                RecipeStep(food_id=buncha.id, step_number=1, instruction="Ướp thịt băm và thịt miếng với sả, hành, nước mắm, đường, tiêu trong 30 phút."),
                RecipeStep(food_id=buncha.id, step_number=2, instruction="Nướng thịt trên bếp than hoa cho đến khi xém cạnh thơm lừng."),
                RecipeStep(food_id=buncha.id, step_number=3, instruction="Pha nước chấm chua ngọt, thêm đu đủ xanh tỏi ớt và dọn ăn kèm bún, rau sống.")
            ]
            db.session.add_all(buncha_steps)

            # Lưu tất cả vào Cơ sở dữ liệu
            db.session.commit()
            print("🎉 Nạp dữ liệu hoàn tất thành công!")
        else:
            print("Dữ liệu đã tồn tại, không cần nạp lại.")

if __name__ == '__main__':
    init_database()
