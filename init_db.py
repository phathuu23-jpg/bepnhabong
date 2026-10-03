from app import app, db, Food, RecipeStep

# Danh sách dữ liệu mẫu theo đúng 4 nhóm danh mục
DATA = [
    # -------------------------------------------------------------
    # 1. CƠM GIA ĐÌNH
    # -------------------------------------------------------------
    {
        "name": "Thịt kho tàu nước dừa trứng cút",
        "category": "Cơm gia đình",
        "time": "45 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800",
        "ingredients": "500g thịt ba chỉ\n15 quả trứng cút luộc\n1 quả dừa tươi\nHành, tỏi, nước mắm, đường, tiêu",
        "steps": [
            "Thịt ba chỉ rửa sạch, thái miếng vuông vừa ăn.",
            "Ướp thịt với nước mắm, đường, hành tỏi băm trong 20 phút.",
            "Thắng nước màu, cho thịt vào đảo săn rồi đổ nước dừa ngập thịt.",
            "Kho nhỏ lửa 30 phút, cho trứng cút vào kho thêm 15 phút đến khi cạn sóng sánh."
        ]
    },
    {
        "name": "Sườn xào chua ngọt",
        "category": "Cơm gia đình",
        "time": "35 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800",
        "ingredients": "500g sườn non\nHành, tỏi, giấm, đường, tương cà, nước mắm",
        "steps": [
            "Sườn chần qua nước sôi, rán vàng đều các mặt.",
            "Pha sốt chua ngọt gồm giấm, đường, tương cà và nước mắm.",
            "Phi thơm hành tỏi, cho sườn và sốt vào đảo đều đến khi sốt sệt lại."
        ]
    },
    {
        "name": "Cá lóc kho tộ đậm đà",
        "category": "Cơm gia đình",
        "time": "40 phút",
        "servings": "3 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=800",
        "ingredients": "1 con cá lóc (600g)\nThịt ba chỉ 100g\nNước mắm, đường, tiêu, ớt, hành lá",
        "steps": [
            "Cá làm sạch, cắt khúc. Ướp gia vị trong 20 phút.",
            "Lót thịt ba chỉ dưới đáy tộ, xếp cá lên trên.",
            "Đun sôi rồi hạ nhỏ lửa hầm liu riu đến khi nước kho kẹo lại, rắc tiêu và hành lá."
        ]
    },
    {
        "name": "Gà chiên mắm tỏi ớt",
        "category": "Cơm gia đình",
        "time": "30 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800",
        "ingredients": "500g cánh/đùi gà\nTỏi, ớt băm\nNước mắm, đường, tương ớt",
        "steps": [
            "Gà rửa sạch, chiên giòn vàng các mặt.",
            "Pha hỗn hợp nước mắm, đường, tương ớt.",
            "Phi thơm tỏi ớt, cho sốt vào đun sôi rồi cho gà chiên vào đảo đều."
        ]
    },
    {
        "name": "Thịt rang cháy cạnh",
        "category": "Cơm gia đình",
        "time": "20 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800",
        "ingredients": "400g thịt ba chỉ\nHành khô, hành lá\nNước mắm, đường, tiêu",
        "steps": [
            "Thịt ba chỉ thái mỏng, cho vào chảo rang đến khi xém cạnh và ra bớt mỡ.",
            "Cho hành khô băm vào phi thơm cùng thịt.",
            "Nêm nước mắm, chút đường đảo nhanh tay rồi rắc hành lá cắt nhỏ."
        ]
    },
    {
        "name": "Canh chua cá lóc",
        "category": "Cơm gia đình",
        "time": "30 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "1 khúc cá lóc\nDứa, cà chua, giá đỗ, bạc hà, me chua\nRau nổ, ngò gai",
        "steps": [
            "Nấu nước me chua, cho cá lóc vào luộc chín tới rồi vớt ra.",
            "Cho dứa, cà chua vào đun sôi, nêm gia vị vừa ăn.",
            "Thêm bạc hà, giá đỗ và cá vào đun lại, tắt bếp rắc ngò gai."
        ]
    },
    {
        "name": "Canh cua mồng tơi mướp",
        "category": "Cơm gia đình",
        "time": "25 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "300g cua đồng xay\n1 mớ rau mồng tơi\n1 quả mướp hương\nGia vị, mắm tôm (tùy chọn)",
        "steps": [
            "Lọc cua lấy nước, đun nhỏ lửa đến khi gạch cua đóng thành mảng.",
            "Thả mướp hương thái miếng và rau mồng tơi vào.",
            "Nêm gia vị vừa ăn, đun sôi lại rồi tắt bếp."
        ]
    },
    {
        "name": "Canh sườn nấu sấu",
        "category": "Cơm gia đình",
        "time": "35 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "400g sườn thăn\n5 quả sấu tươi\nCà chua, hành lá, mùi tàu",
        "steps": [
            "Sườn chần sạch, ninh mềm với nước.",
            "Cho sấu và cà chua xào sơ vào nồi sườn đun tiếp.",
            "Dầm sấu lấy độ chua vừa ăn, rắc hành lá mùi tàu."
        ]
    },
    {
        "name": "Canh tôm nấu bầu",
        "category": "Cơm gia đình",
        "time": "20 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "200g tôm tươi\n1/2 quả bầu\nHành khô, hành lá, gia vị",
        "steps": [
            "Tôm bóc vỏ, giã nhẹ rồi băm nhỏ.",
            "Phi thơm hành, xào tôm rồi đổ nước vào đun sôi.",
            "Cho bầu băm nhỏ/băm sợi vào, nêm gia vị vừa ăn."
        ]
    },
    {
        "name": "Rau muống xào tỏi",
        "category": "Cơm gia đình",
        "time": "15 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800",
        "ingredients": "1 mớ rau muống\n2 củ tỏi đập dập\nHạt nêm, dầu ăn",
        "steps": [
            "Rau muống luộc sơ qua nước sôi có chút muối, vớt ra ngâm nước đá.",
            "Phi tỏi thơm vàng trên chảo.",
            "Cho rau muống vào xào lửa lớn, nêm gia vị đảo nhanh tay."
        ]
    },
    {
        "name": "Đậu hũ xào nấm tươi",
        "category": "Cơm gia đình",
        "time": "20 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800",
        "ingredients": "3 bìa đậu hũ chiên\n200g nấm đùi gà/nấm rơm\nDầu hào, hành tỏi",
        "steps": [
            "Đậu hũ thái miếng, nấm rửa sạch cắt nhỏ.",
            "Phi thơm hành tỏi, cho nấm vào xào chín tới.",
            "Cho đậu hũ và dầu hào vào đảo đều cho thấm gia vị."
        ]
    },
    {
        "name": "Bông cải xanh xào thịt bò",
        "category": "Cơm gia đình",
        "time": "25 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800",
        "ingredients": "200g thịt bò\n1 cây bông cải xanh\nTỏi, dầu hào, tiêu",
        "steps": [
            "Thịt bò thái mỏng ướp tỏi, gia vị và tí dầu ăn.",
            "Xào thịt bò lửa lớn đến khi tái rồi trút ra đĩa.",
            "Xào bông cải xanh chín tới, cho thịt bò vào đảo lại rồi tắt bếp."
        ]
    },

    # -------------------------------------------------------------
    # 2. MÓN ĂN SÁNG & MÓN NƯỚC
    # -------------------------------------------------------------
    {
        "name": "Phở bò gia truyền",
        "category": "Món sáng & Món nước",
        "time": "60 phút",
        "servings": "4 người",
        "difficulty": "Khó",
        "image": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800",
        "ingredients": "500g bánh phở\n300g thịt bò tái/nạm\nXương ống hầm lấy nước dùng\nHành tây, gừng nướng, hoa hồi, thảo quả",
        "steps": [
            "Hầm xương ống cùng gừng nướng, hoa hồi trong nhiều giờ.",
            "Chần bánh phở xếp vào bát, thêm thịt bò thái mỏng.",
            "Múc nước dùng đang sôi sùng sục chan vào bát, rắc hành lá."
        ]
    },
    {
        "name": "Bún riêu cua đồng",
        "category": "Món sáng & Món nước",
        "time": "45 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800",
        "ingredients": "Bún tươi, cua đồng xay, giò sống, đậu hũ chiên, cà chua, giấm nhút, rau sống",
        "steps": [
            "Đun nước cua lấy gạch. Xào cà chua tạo màu.",
            "Cho giò sống, đậu hũ vào nồi nước dùng đun sôi.",
            "Xếp bún ra bát, chan nước dùng và ăn kèm rau sống."
        ]
    },
    {
        "name": "Bún bò Huế",
        "category": "Món sáng & Món nước",
        "time": "60 phút",
        "servings": "4 người",
        "difficulty": "Khó",
        "image": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800",
        "ingredients": "Bún sợi to, nạm bò, giò heo, chả cua, mắm ruốc Huế, sả củ",
        "steps": [
            "Hầm giò heo và thịt bò với sả đập dập.",
            "Pha mắm ruốc Huế lọc lấy nước trong chắt vào nồi nước dùng.",
            "Trình bày bún, thịt, chả ra bát rồi chan nước dùng đậm đà."
        ]
    },
    {
        "name": "Bún mọc sườn chua",
        "category": "Món sáng & Món nước",
        "time": "40 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800",
        "ingredients": "Bún, sườn thăn, mọc (giò sống trộn mộc nhĩ), dọc mùng, quả dọc/sấu",
        "steps": [
            "Ninh sườn lấy nước ngọt, thả viên mọc vào đun nổi.",
            "Thêm sấu và dọc mùng đã tước vỏ làm sạch.",
            "Chan nước dùng chua thanh lên bát bún sườn mọc."
        ]
    },
    {
        "name": "Bánh mì chảo",
        "category": "Món sáng & Món nước",
        "time": "20 phút",
        "servings": "2 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1509722747041-616f39b57569?w=800",
        "ingredients": "Bánh mì, trứng gà, pate, xúc xích, sốt cà chua, bơ",
        "steps": [
            "Làm nóng chảo nhỏ, cho bơ vào đun chảy.",
            "Ốp la trứng, rán xúc xích và pate nóng.",
            "Rưới sốt cà chua đậm đà lên trên, ăn kèm bánh mì giòn."
        ]
    },
    {
        "name": "Xôi mặn thập cẩm",
        "category": "Món sáng & Món nước",
        "time": "30 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1509722747041-616f39b57569?w=800",
        "ingredients": "Gạo nếp, chả lợn, lạp xưởng, ruốc, mỡ hành, đậu phụng",
        "steps": [
            "Gạo nếp đồ chín thành xôi dẻo.",
            "Lạp xưởng chiên thái mỏng, chả thái sợi.",
            "Xới xôi ra đĩa, xếp topping và rưới mỡ hành lên."
        ]
    },
    {
        "name": "Cháo sườn sụn",
        "category": "Món sáng & Món nước",
        "time": "50 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1509722747041-616f39b57569?w=800",
        "ingredients": "Bột gạo xay/Gạo tẻ, sườn sụn, ruốc, quẩy giòn",
        "steps": [
            "Sườn sụn ninh nhừ lấy nước nấu cháo bột mịn.",
            "Xé sườn sụn cho vào cháo đun quyện.",
            "Múc cháo ra bát, ăn cùng quẩy giòn và ruốc thịt."
        ]
    },

    # -------------------------------------------------------------
    # 3. ĂN VẶT & TRÁNG MIỆNG
    # -------------------------------------------------------------
    {
        "name": "Bánh tráng trộn",
        "category": "Ăn vặt & Tráng miệng",
        "time": "15 phút",
        "servings": "2 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
        "ingredients": "Bánh tráng cắt sợi, trứng cút, xoài xanh, bò khô, rau rau răm, nước sốt tắc",
        "steps": [
            "Cho bánh tráng, xoài bào, bò khô, rau răm vào thau lớn.",
            "Rưới nước sốt sa tế tắc vào trộn đều tay.",
            "Cho trứng cút luộc vào và thưởng thức."
        ]
    },
    {
        "name": "Chân gà sả tắc",
        "category": "Ăn vặt & Tráng miệng",
        "time": "30 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
        "ingredients": "500g chân gà, sả, tắc, ớt, lá chanh, nước mắm, đường, giấm",
        "steps": [
            "Chân gà luộc chín tới với gừng sả, vớt ra ngâm đá cho giòn.",
            "Pha nước sốt chua ngọt đậm đà.",
            "Trộn chân gà với sả thái mỏng, tắc thái lát và nước sốt trong 2 tiếng."
        ]
    },
    {
        "name": "Phô mai que giòn rụm",
        "category": "Ăn vặt & Tráng miệng",
        "time": "20 phút",
        "servings": "3 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
        "ingredients": "Phô mai Mozzarella cắt thỏi, trứng gà, bột xù, bột mì",
        "steps": [
            "Lăn phô mai qua bột mì, trứng rồi bột xù.",
            "Cho phô mai vào tủ đông 30 phút cho cứng lại.",
            "Chiên ngập dầu lửa lớn đến khi vỏ vàng giòn."
        ]
    },
    {
        "name": "Chè bưởi An Giang",
        "category": "Ăn vặt & Tráng miệng",
        "time": "45 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=800",
        "ingredients": "Cùi bưởi, bột năng, đậu xanh bóc vỏ, nước cốt dừa, đường thốt nốt",
        "steps": [
            "Cùi bưởi sơ chế hết đắng, luộc chín lăn qua bột năng.",
            "Nấu đậu xanh chín mềm, thêm đường thốt nốt.",
            "Cho cùi bưởi vào đun sánh lại, ăn cùng nước cốt dừa béo ngậy."
        ]
    },
    {
        "name": "Chè khúc bạch trái cây",
        "category": "Ăn vặt & Tráng miệng",
        "time": "40 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=800",
        "ingredients": "Sữa tươi, whipping cream, gelatin, nhãn/vải, hạnh nhân lát",
        "steps": [
            "Đun nhẹ sữa tươi, whipping cream và đun chảy gelatin rồi đổ khuôn làm đông.",
            "Nấu nước đường nhãn thanh mát.",
            "Cắt khúc bạch ra bát, thêm nhãn, nước đường và hạnh nhân rang."
        ]
    },
    {
        "name": "Bánh flan caramel",
        "category": "Ăn vặt & Tráng miệng",
        "time": "35 phút",
        "servings": "4 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=800",
        "ingredients": "Trứng gà, sữa tươi không đường, sữa đặc, đường làm caramel",
        "steps": [
            "Thắng đường làm caramel tráng đáy khuôn.",
            "Khuấy nhẹ trứng với sữa ấm rồi lọc qua rây.",
            "Đổ hỗn hợp vào khuôn và hấp nhỏ lửa 20 phút."
        ]
    },

    # -------------------------------------------------------------
    # 4. MÓN ĐÃI TIỆC & CUỐI TUẦN
    # -------------------------------------------------------------
    {
        "name": "Lẩu thái hải sản chua cay",
        "category": "Món đãi tiệc & Cuối tuần",
        "time": "45 phút",
        "servings": "6 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "Tôm, mực, nghêu, riềng, sả, lá chanh, gói gối lẩu Thái, rau nhúng lẩu",
        "steps": [
            "Phi thơm sả riềng lá chanh, cho nước dùng xương vào đun sôi.",
            "Nêm gói sốt lẩu Thái, nước mắm, đường chua cay vừa vị.",
            "Bày hải sản và rau ra đĩa, nhúng ăn nóng."
        ]
    },
    {
        "name": "Lẩu gà lá giang",
        "category": "Món đãi tiệc & Cuối tuần",
        "time": "50 phút",
        "servings": "5 người",
        "difficulty": "Dễ",
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
        "ingredients": "1 con gà ta, 1 mớ lá giang, sả, tỏi, ớt, nước mắm",
        "steps": [
            "Gà chặt miếng xào săn với sả tỏi.",
            "Đổ nước vào ninh chín mềm gà.",
            "Vò nát lá giang thả vào nồi lẩu tạo độ chua thanh tự nhiên."
        ]
    },
    {
        "name": "Tôm hùm bỏ lò phô mai",
        "category": "Món đãi tiệc & Cuối tuần",
        "time": "30 phút",
        "servings": "2 người",
        "difficulty": "Khó",
        "image": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800",
        "ingredients": "1 con tôm hùm, phô mai Mozzarella bào, bơ tỏi, sốt mayonnaise",
        "steps": [
            "Tôm hùm bổ đôi dọc lưng, rửa sạch.",
            "Phết bơ tỏi và sốt mayonnaise lên thịt tôm.",
            "Phủ kín phô mai Mozzarella rồi nướng ở 200 độ C trong 15 phút."
        ]
    },
    {
        "name": "Gà nướng muối ớt",
        "category": "Món đãi tiệc & Cuối tuần",
        "time": "50 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1562967914-608f82629710?w=800",
        "ingredients": "1 con gà nguyên con, sốt muối ớt, nghệ tươi, tỏi ớt băm",
        "steps": [
            "Gà mổ phanh, đập dập xương xường.",
            "Ướp gà với sốt muối ớt tỏi nghệ trong 1 tiếng.",
            "Nướng gà trên than hoa hoặc nồi chiên không dầu đến khi da giòn vàng."
        ]
    },
    {
        "name": "Cá chép om dưa",
        "category": "Món đãi tiệc & Cuối tuần",
        "time": "40 phút",
        "servings": "4 người",
        "difficulty": "Trung bình",
        "image": "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=800",
        "ingredients": "1 con cá chép giòn, dưa chua, thịt ba chỉ, cà chua, hành thì là",
        "steps": [
            "Cá chép rán sơ vàng hai mặt.",
            "Xào thịt ba chỉ, dưa chua và cà chua cho ngấm gia vị.",
            "Cho cá vào om cùng dưa chua nhỏ lửa 20 phút, rắc hành thì là."
        ]
    }
]

def run_import():
    with app.app_context():
        print("Đang xóa dữ liệu món ăn cũ...")
        db.session.query(RecipeStep).delete()
        db.session.query(Food).delete()
        db.session.commit()

        print("Đang thêm danh sách món ăn mới vào CSDLN...")
        for item in DATA:
            food = Food(
                name=item["name"],
                category=item["category"],
                time=item["time"],
                servings=item["servings"],
                difficulty=item["difficulty"],
                image=item["image"],
                ingredients=item["ingredients"],
                status="approved",
                author_name="Bếp Nhà Bông"
            )
            db.session.add(food)
            db.session.flush()

            for idx, step_desc in enumerate(item["steps"]):
                step = RecipeStep(
                    food_id=food.id,
                    step_number=idx + 1,
                    description=step_desc
                )
                db.session.add(step)

        db.session.commit()
        print("🎉 Nạp dữ liệu hoàn tất thành công!")

if __name__ == '__main__':
    run_import()
