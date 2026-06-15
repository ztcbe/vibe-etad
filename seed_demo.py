#!/usr/bin/env python3
"""Seed demo data: 52 users with diverse profiles, mutual matches, pending likes.

Run: cd backend && python ../seed_demo.py
Requires: PostgreSQL running, migrations applied.
"""
import asyncio
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from httpx import ASGITransport, AsyncClient
from app.main import app

DEMO_PASSWORD = "demo123456"

# ── Vietnamese user data — username is ASCII-only for easy login ──
USERS = [
    # (username, display_name, gender, interested_in, city, goal, hobbies, traits, bio, age)
    ("linh", "Linh", "female", "male", "Đà Lạt", "serious",
     ["Cà phê", "Đọc sách", "Trekking", "Nhạc indie"], ["Hướng nội nhẹ", "Chân thành"],
     "Yêu thiên nhiên, thích những buổi sáng yên tĩnh với sách và cà phê.", 27),

    ("khang", "Khang", "male", "female", "Đà Lạt", "serious",
     ["Trekking", "Cà phê", "Nhiếp ảnh", "Đọc sách"], ["Điềm tĩnh", "Sâu sắc"],
     "Làm việc theo ca nhưng luôn dành thời gian cho thiên nhiên và những cuốn sách hay.", 29),

    ("thao", "Thảo", "female", "male", "Hồ Chí Minh", "serious",
     ["Yoga", "Nấu ăn", "Du lịch", "Âm nhạc"], ["Năng động", "Chu đáo"],
     "Sáng yoga, tối nấu ăn. Đang tìm người đồng hành cho những chuyến đi xa.", 26),

    ("huy", "Huy", "male", "female", "Hồ Chí Minh", "casual",
     ["Gym", "Bơi lội", "Xem phim", "Cà phê"], ["Hài hước", "Thoải mái"],
     "Dân văn phòng năng động, thích giao lưu và gặp gỡ bạn mới.", 28),

    ("minh", "Minh", "male", "female", "Hà Nội", "serious",
     ["Đọc sách", "Viết lách", "Piano", "Thiền"], ["Trí thức", "Tinh tế"],
     "Yêu văn học, thích những cuộc trò chuyện sâu sắc về cuộc sống.", 31),

    ("trang", "Trang", "female", "male", "Hà Nội", "serious",
     ["Vẽ", "Âm nhạc", "Du lịch", "Đọc sách"], ["Sáng tạo", "Nhẹ nhàng"],
     "Họa sĩ tự do, mơ mộng nhưng thực tế. Yêu cái đẹp và sự chân thành.", 25),

    ("tung", "Tùng", "male", "female", "Đà Nẵng", "friends_first",
     ["Lặn biển", "Du lịch", "Nhiếp ảnh", "Cà phê"], ["Phiêu lưu", "Cởi mở"],
     "Sống ở biển, yêu biển. Công việc tự do, thích khám phá những điều mới.", 30),

    ("huong", "Hương", "female", "male", "Đà Nẵng", "not_sure",
     ["Bơi lội", "Yoga", "Nấu ăn"], ["Dịu dàng", "Kiên nhẫn"],
     "Giáo viên yoga, yêu sự cân bằng trong cuộc sống.", 24),

    ("phuc", "Phúc", "male", "female", "Hội An", "serious",
     ["Nhiếp ảnh", "Cà phê", "Du lịch", "Đọc sách"], ["Nghệ sĩ", "Lãng mạn"],
     "Nhiếp ảnh gia tự do, chuyên chụp ảnh cưới. Tin vào tình yêu đích thực.", 32),

    ("mai", "Mai", "female", "male", "Hội An", "serious",
     ["Nấu ăn", "Vẽ", "Yoga", "Du lịch"], ["Ấm áp", "Tận tâm"],
     "Đầu bếp yêu thích ẩm thực Việt, muốn tìm người cùng chia sẻ đam mê.", 28),

    ("long", "Long", "male", "female", "Nha Trang", "casual",
     ["Lặn biển", "Gym", "Du lịch"], ["Vui vẻ", "Nhiệt tình"],
     "Hướng dẫn viên lặn biển, sống hết mình với đam mê đại dương.", 27),

    ("nhung", "Nhung", "female", "male", "Nha Trang", "friends_first",
     ["Bơi lội", "Tennis", "Âm nhạc"], ["Hoạt bát", "Thân thiện"],
     "Sinh viên năm cuối, yêu thể thao và những buổi chiều trên bãi biển.", 22),

    ("son", "Sơn", "male", "female", "Huế", "serious",
     ["Đọc sách", "Thiền", "Viết lách", "Piano"], ["Trầm tính", "Sâu sắc"],
     "Giảng viên đại học, thích sự yên tĩnh và những cuộc trò chuyện có chiều sâu.", 35),

    ("ha01", "Hà", "female", "male", "Huế", "serious",
     ["Nấu ăn", "Đọc sách", "Du lịch"], ["Dịu dàng", "Truyền thống"],
     "Yêu văn hóa Huế, thích nấu những món ăn cung đình.", 26),

    ("duc", "Đức", "male", "female", "Cần Thơ", "serious",
     ["Cà phê", "Du lịch", "Nhiếp ảnh"], ["Chân thành", "Giản dị"],
     "Kỹ sư phần mềm yêu miền Tây, thích cuộc sống chậm rãi và bình yên.", 29),

    ("lan", "Lan", "female", "male", "Cần Thơ", "casual",
     ["Du lịch", "Chạy bộ", "Xem phim"], ["Năng động", "Vui tính"],
     "Nhân viên marketing, thích khám phá ẩm thực và du lịch bụi.", 25),

    ("viet", "Việt", "male", "female", "Hải Phòng", "serious",
     ["Gym", "Bơi lội", "Đọc sách"], ["Mạnh mẽ", "Quyết đoán"],
     "Doanh nhân trẻ, nghiêm túc trong công việc và tình cảm.", 33),

    ("chi", "Chi", "female", "male", "Hải Phòng", "serious",
     ["Yoga", "Nấu ăn", "Du lịch"], ["Đảm đang", "Thẳng thắn"],
     "Kế toán yêu sự ngăn nắp, mong tìm được người đàn ông trưởng thành.", 27),

    ("dung", "Dũng", "male", "female", "Vũng Tàu", "casual",
     ["Lướt sóng", "Bơi lội", "Cà phê"], ["Phóng khoáng", "Hài hước"],
     "Surfer chuyên nghiệp, sống theo con sóng và những chuyến đi.", 26),

    ("ngoc", "Ngọc", "female", "male", "Vũng Tàu", "friends_first",
     ["Bơi lội", "Yoga", "Vẽ"], ["Mộng mơ", "Dịu dàng"],
     "Kiến trúc sư yêu biển, thích vẽ tranh phong cảnh.", 24),

    ("binh", "Bình", "male", "female", "Hồ Chí Minh", "serious",
     ["Gym", "Đọc sách", "Du lịch", "Cà phê"], ["Kỷ luật", "Trung thành"],
     "Quân nhân đã nghỉ hưu, giờ làm PT. Nghiêm túc tìm bạn đời.", 34),

    ("an01", "An", "female", "male", "Hồ Chí Minh", "casual",
     ["Nhảy", "Âm nhạc", "Thời trang"], ["Sôi nổi", "Tự tin"],
     "Dancer kiêm stylist, yêu nghệ thuật và cuộc sống về đêm.", 23),

    ("thy", "Thy", "female", "male", "Đà Lạt", "serious",
     ["Trekking", "Cà phê", "Nhiếp ảnh", "Vẽ"], ["Lãng mạn", "Tinh tế"],
     "Florist yêu hoa và núi rừng. Mong tìm được người cùng ngắm bình minh trên đồi.", 26),

    ("khoa", "Khoa", "male", "female", "Hà Nội", "serious",
     ["Piano", "Đọc sách", "Thiền", "Cà phê"], ["Lịch lãm", "Kiên nhẫn"],
     "Luật sư yêu âm nhạc cổ điển, tìm người cùng chia sẻ gu thẩm mỹ.", 36),

    ("nhi", "Nhi", "female", "male", "Đà Nẵng", "friends_first",
     ["Du lịch", "Nhiếp ảnh", "Nấu ăn"], ["Tò mò", "Nhiệt huyết"],
     "Travel blogger, đã đi 20 nước. Giờ muốn tìm người đồng hành.", 28),

    ("phong", "Phong", "male", "female", "Hồ Chí Minh", "casual",
     ["Tennis", "Gym", "Xem phim", "Cà phê"], ["Lịch thiệp", "Thoải mái"],
     "Quản lý khách sạn, thích gặp gỡ và kết nối con người.", 30),

    ("van", "Vân", "female", "male", "Hà Nội", "serious",
     ["Đọc sách", "Viết lách", "Yoga"], ["Trí thức", "Độc lập"],
     "Nhà báo tự do, yêu sự thật và những câu chuyện đời thường.", 29),

    ("quan", "Quân", "male", "female", "Nha Trang", "not_sure",
     ["Lặn biển", "Du lịch", "Âm nhạc"], ["Bí ẩn", "Sâu sắc"],
     "Cựu thủy thủ, giờ mở quán bar bên biển. Chưa rõ mình muốn gì.", 31),

    ("giang", "Giang", "female", "male", "Hội An", "serious",
     ["Vẽ", "Yoga", "Nấu ăn", "Đọc sách"], ["Nghệ sĩ", "Chân thành"],
     "Họa sĩ minh họa sách thiếu nhi. Yêu trẻ con và mơ về một gia đình nhỏ.", 27),

    ("tam", "Tâm", "male", "female", "Cần Thơ", "serious",
     ["Cà phê", "Đọc sách", "Chạy bộ", "Thiền"], ["Điềm đạm", "Tử tế"],
     "Bác sĩ thú y, yêu động vật và cuộc sống miệt vườn.", 32),

    # ── 22 additional users (52 total) ──
    ("hoa", "Hoa", "female", "male", "Hà Nội", "serious",
     ["Đọc sách", "Cắm hoa", "Nấu ăn"], ["Nhẹ nhàng", "Kiên nhẫn"],
     "Giáo viên tiểu học, yêu trẻ con và mơ về một gia đình hạnh phúc.", 27),

    ("nam", "Nam", "male", "female", "Hồ Chí Minh", "friends_first",
     ["Bóng đá", "Gym", "Cà phê"], ["Vui tính", "Hòa đồng"],
     "Kiến trúc sư trẻ, thích thiết kế và gặp gỡ bạn bè cuối tuần.", 28),

    ("trinh", "Trinh", "female", "male", "Đà Nẵng", "serious",
     ["Yoga", "Du lịch", "Chụp ảnh"], ["Tinh tế", "Sâu sắc"],
     "Làm trong ngành truyền thông, yêu cái đẹp và sự chân thành.", 26),

    ("hieu", "Hiếu", "male", "female", "Hà Nội", "serious",
     ["Đọc sách", "Viết code", "Chạy bộ"], ["Chân thành", "Hướng nội"],
     "Lập trình viên đam mê công nghệ, tìm người cùng chia sẻ cuộc sống.", 29),

    ("tuyet", "Tuyết", "female", "male", "Đà Lạt", "serious",
     ["Nhiếp ảnh", "Trekking", "Vẽ"], ["Lãng mạn", "Mơ mộng"],
     "Photographer tự do, yêu khung cảnh Đà Lạt và những buổi sáng sương mù.", 25),

    ("thuan", "Thuận", "male", "female", "Cần Thơ", "casual",
     ["Cà phê", "Du lịch", "Âm nhạc"], ["Thoải mái", "Hài hước"],
     "Chủ quán cà phê nhỏ, thích giao lưu và gặp gỡ bạn mới mỗi ngày.", 30),

    ("my01", "Mỹ", "female", "male", "Huế", "serious",
     ["Nấu ăn", "Đọc sách", "Thiền"], ["Dịu dàng", "Truyền thống"],
     "Yêu ẩm thực cung đình Huế, mong tìm người cùng thưởng thức cuộc sống.", 24),

    ("hai", "Hải", "male", "female", "Vũng Tàu", "friends_first",
     ["Lướt sóng", "Bơi lội", "Du lịch"], ["Năng động", "Phóng khoáng"],
     "Hướng dẫn viên du lịch biển, thích cuộc sống tự do và những chuyến đi.", 28),

    ("thuy", "Thúy", "female", "male", "Hồ Chí Minh", "serious",
     ["Yoga", "Đọc sách", "Piano"], ["Thanh lịch", "Trí thức"],
     "Giảng viên âm nhạc, yêu cổ điển và những buổi hòa nhạc.", 31),

    ("cuong", "Cường", "male", "female", "Hải Phòng", "serious",
     ["Gym", "Bơi lội", "Đọc sách"], ["Kỷ luật", "Mạnh mẽ"],
     "Sĩ quan hải quân, nghiêm túc trong công việc và cuộc sống.", 33),

    ("yen", "Yến", "female", "male", "Nha Trang", "casual",
     ["Bơi lội", "Lặn biển", "Nấu ăn"], ["Vui vẻ", "Năng động"],
     "Huấn luyện viên bơi lội, yêu biển và các hoạt động ngoài trời.", 25),

    ("toan", "Toàn", "male", "female", "Đà Nẵng", "serious",
     ["Cà phê", "Đọc sách", "Du lịch", "Nhiếp ảnh"], ["Trầm tĩnh", "Sâu sắc"],
     "Chuyên viên phân tích dữ liệu, thích sự logic và những cuộc trò chuyện ý nghĩa.", 30),

    ("hanh", "Hạnh", "female", "male", "Hà Nội", "serious",
     ["Nấu ăn", "Yoga", "Từ thiện"], ["Ấm áp", "Chu đáo"],
     "Nhân viên tổ chức phi chính phủ, yêu công việc cộng đồng và trẻ em.", 29),

    ("bao", "Bảo", "male", "female", "Hồ Chí Minh", "friends_first",
     ["Nhiếp ảnh", "Cà phê", "Du lịch bụi"], ["Sáng tạo", "Tự do"],
     "Freelancer thiết kế đồ họa, thích khám phá văn hóa và con người mới.", 27),

    ("diep", "Diệp", "female", "male", "Đà Lạt", "serious",
     ["Vẽ", "Làm gốm", "Yoga"], ["Nghệ sĩ", "Tinh tế"],
     "Nghệ nhân gốm, yêu sự mộc mạc và những điều giản dị trong cuộc sống.", 26),

    ("hung", "Hùng", "male", "female", "Hội An", "casual",
     ["Cà phê", "Âm nhạc", "Du lịch"], ["Cởi mở", "Nhiệt tình"],
     "Barista kiêm nhạc công guitar, thích chill và những buổi tối bên phố cổ.", 29),

    ("thu", "Thư", "female", "male", "Huế", "friends_first",
     ["Đọc sách", "Viết lách", "Du lịch"], ["Trí thức", "Nhẹ nhàng"],
     "Biên tập viên nhà xuất bản, yêu sách và những câu chuyện lịch sử.", 28),

    ("dat", "Đạt", "male", "female", "Cần Thơ", "serious",
     ["Xe máy", "Du lịch", "Nhiếp ảnh", "Cà phê"], ["Mạnh mẽ", "Phóng khoáng"],
     "Kỹ sư cơ khí mê phượt, đã đi khắp Việt Nam bằng xe máy.", 31),

    ("kim", "Kim", "female", "male", "Hồ Chí Minh", "casual",
     ["Thời trang", "Nhảy", "Du lịch"], ["Tự tin", "Hiện đại"],
     "Fashion designer trẻ, yêu sự sáng tạo và phong cách sống năng động.", 24),

    ("vinh", "Vinh", "male", "female", "Nha Trang", "serious",
     ["Lặn biển", "Câu cá", "Nấu ăn"], ["Điềm đạm", "Chân thành"],
     "Ngư dân kiêm đầu bếp hải sản, yêu biển và cuộc sống giản dị.", 34),

    ("quynh", "Quỳnh", "female", "male", "Hà Nội", "serious",
     ["Piano", "Ballet", "Đọc sách"], ["Thanh lịch", "Kỷ luật"],
     "Nghệ sĩ ballet, sống kỷ luật nhưng lãng mạn trong tình yêu.", 26),

    ("tuan", "Tuấn", "male", "female", "Vũng Tàu", "not_sure",
     ["Gym", "Chạy bộ", "Xem phim"], ["Hướng nội", "Chân thành"],
     "Kỹ sư dầu khí, làm việc xa bờ. Chưa rõ mình muốn gì trong tình cảm.", 30),
]

# ── Match pairs (indices into USERS array) ──
MATCH_PAIRS = [
    (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),     # original 5 pairs
    (10, 11), (12, 13), (14, 15), (16, 17),        # +4 pairs
    (20, 21), (22, 23),                              # +2 pairs
    (30, 31), (32, 33), (34, 35),                   # new users paired
    (36, 37), (38, 39), (40, 41),
]

PENDING_LIKES = [
    (18, 19), (24, 25), (26, 27), (28, 29),
    (42, 43), (44, 45), (46, 47), (48, 49),
    (50, 51), (0, 3), (2, 5), (7, 9), (11, 14),
    (13, 16), (30, 5), (31, 22), (33, 27),
]


def random_dob(age: int) -> str:
    year = 2026 - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


async def seed():
    print("🌱 Seeding demo data...")

    transport = ASGITransport(app=app)
    tokens: list[dict] = []

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Create admin ──
        print("Creating admin account...")
        r = await client.post("/api/auth/register", json={
            "username": "admin", "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD, "date_of_birth": "1990-01-01",
        })
        if r.status_code == 200:
            print("  ✅ admin created")
        else:
            # Might already exist
            print(f"  ⚠️  admin: {r.json().get('error', {}).get('message', r.status_code)}")

        # ── Create users ──
        total = len(USERS)
        for i, (username, name, gender, interested_in, city, goal, hobbies, traits, bio, age) in enumerate(USERS):
            print(f"  [{i+1}/{total}] Creating {name} ({username})...")

            r = await client.post("/api/auth/register", json={
                "username": username, "password": DEMO_PASSWORD,
                "confirm_password": DEMO_PASSWORD, "date_of_birth": random_dob(age),
            })
            if r.status_code != 200:
                print(f"    ERROR: {r.status_code} {r.text[:200]}")
                continue
            data = r.json()
            token = data["data"]["access_token"]
            tokens.append({"token": token, "username": username, "name": name, "idx": i})
            h = {"Authorization": f"Bearer {token}"}

            # Update profile
            prefs = {
                "preferred_age_min": max(18, age - 5),
                "preferred_age_max": age + 5,
                "preferred_distance_km": random.choice([30, 50, 100, 200]),
                "preferred_gender": interested_in,
            }
            r = await client.patch("/api/profile/me", headers=h, json={
                "display_name": name,
                "gender": gender,
                "interested_in": interested_in,
                "city": city,
                "dating_goal": goal,
                "bio": bio,
                "hobbies": hobbies,
                "personality_traits": traits,
                "preferences": prefs,
                "public_summary": bio,
            })
            if r.status_code != 200:
                print(f"    Profile error: {r.status_code} {r.text[:100]}")

        print(f"  ✅ {len(tokens)} users created")

        # ── Create mutual matches ──
        print("Creating mutual matches...")
        match_ids = []
        for a_idx, b_idx in MATCH_PAIRS:
            if a_idx >= len(tokens) or b_idx >= len(tokens):
                continue
            ta, tb = tokens[a_idx], tokens[b_idx]
            ha = {"Authorization": f"Bearer {ta['token']}"}
            hb = {"Authorization": f"Bearer {tb['token']}"}

            # Get B's user_id
            r = await client.get("/api/auth/me", headers=hb)
            if r.status_code != 200: continue
            b_uid = r.json()["data"]["id"]

            r = await client.get("/api/auth/me", headers=ha)
            if r.status_code != 200: continue
            a_uid = r.json()["data"]["id"]

            # A likes B
            await client.post(f"/api/matches/{b_uid}/like", headers=ha)
            # B likes A → mutual
            r = await client.post(f"/api/matches/{a_uid}/like", headers=hb)
            if r.status_code == 200 and r.json()["data"]["is_mutual"]:
                match_ids.append(r.json()["data"]["match_id"])
                print(f"  💞 {ta['name']} ↔ {tb['name']} matched!")

                # Add chat message for some matches
                if len(match_ids) <= 5:
                    await client.post(f"/api/chats/{r.json()['data']['match_id']}/messages", headers=ha, json={
                        "content": f"Chào {tb['name']}! Rất vui được làm quen với bạn 👋",
                    })

        # ── Create pending likes ──
        print("Creating pending likes...")
        for from_idx, to_idx in PENDING_LIKES:
            if from_idx >= len(tokens) or to_idx >= len(tokens):
                continue
            ha = {"Authorization": f"Bearer {tokens[from_idx]['token']}"}
            r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens[to_idx]['token']}"})
            if r.status_code != 200: continue
            to_uid = r.json()["data"]["id"]

            r = await client.post(f"/api/matches/{to_uid}/like", headers=ha)
            if r.status_code == 200:
                print(f"  💖 {tokens[from_idx]['name']} → {tokens[to_idx]['name']} (pending)")

        print()
        print("=" * 50)
        print("🌱 SEED COMPLETE!")
        print(f"   {len(tokens)} regular users")
        print(f"   {len(match_ids)} mutual matches")
        print(f"   {len(PENDING_LIKES)} pending likes attempted")
        print()
        print("Demo accounts (password: demo123456):")
        print(f"   🌿 linh    — Linh (primary demo user)")
        print(f"   💞 khang   — Khang (matched with Linh)")
        print(f"   👤 admin   — Admin (set role=admin via DB manually)")
        print()
        print("All usernames are ASCII (no accents) for easy login:")
        for t in tokens[:10]:
            print(f"   {t['username']:<10} — {t['name']}")
        print(f"   ... + {len(tokens) - 10} more")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())
