#!/usr/bin/env python3
"""Seed demo data: 30 users with diverse profiles, 5 mutual matches, 10 pending likes.

Run: cd backend && python ../scripts/seed_demo.py
Requires: PostgreSQL running (docker compose up -d db), migrations applied.
"""
import asyncio
import random
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from httpx import ASGITransport, AsyncClient
from app.main import app

DEMO_PASSWORD = "demo123456"

# ── Vietnamese user data ──
USERS = [
    {"name": "Linh", "gender": "female", "interested_in": "male", "city": "Đà Lạt", "goal": "serious",
     "hobbies": ["Cà phê", "Đọc sách", "Trekking", "Nhạc indie"], "traits": ["Hướng nội nhẹ", "Chân thành"],
     "bio": "Yêu thiên nhiên, thích những buổi sáng yên tĩnh với sách và cà phê.", "age": 27},

    {"name": "Khang", "gender": "male", "interested_in": "female", "city": "Đà Lạt", "goal": "serious",
     "hobbies": ["Trekking", "Cà phê", "Nhiếp ảnh", "Đọc sách"], "traits": ["Điềm tĩnh", "Sâu sắc"],
     "bio": "Làm việc theo ca nhưng luôn dành thời gian cho thiên nhiên và những cuốn sách hay.", "age": 29},

    {"name": "Thảo", "gender": "female", "interested_in": "male", "city": "Hồ Chí Minh", "goal": "serious",
     "hobbies": ["Yoga", "Nấu ăn", "Du lịch", "Âm nhạc"], "traits": ["Năng động", "Chu đáo"],
     "bio": "Sáng yoga, tối nấu ăn. Đang tìm người đồng hành cho những chuyến đi xa.", "age": 26},

    {"name": "Huy", "gender": "male", "interested_in": "female", "city": "Hồ Chí Minh", "goal": "casual",
     "hobbies": ["Gym", "Bơi lội", "Xem phim", "Cà phê"], "traits": ["Hài hước", "Thoải mái"],
     "bio": "Dân văn phòng năng động, thích giao lưu và gặp gỡ bạn mới.", "age": 28},

    {"name": "Minh", "gender": "male", "interested_in": "female", "city": "Hà Nội", "goal": "serious",
     "hobbies": ["Đọc sách", "Viết lách", "Piano", "Thiền"], "traits": ["Trí thức", "Tinh tế"],
     "bio": "Yêu văn học, thích những cuộc trò chuyện sâu sắc về cuộc sống.", "age": 31},

    {"name": "Trang", "gender": "female", "interested_in": "male", "city": "Hà Nội", "goal": "serious",
     "hobbies": ["Vẽ", "Âm nhạc", "Du lịch", "Đọc sách"], "traits": ["Sáng tạo", "Nhẹ nhàng"],
     "bio": "Họa sĩ tự do, mơ mộng nhưng thực tế. Yêu cái đẹp và sự chân thành.", "age": 25},

    {"name": "Tùng", "gender": "male", "interested_in": "female", "city": "Đà Nẵng", "goal": "friends_first",
     "hobbies": ["Lặn biển", "Du lịch", "Nhiếp ảnh", "Cà phê"], "traits": ["Phiêu lưu", "Cởi mở"],
     "bio": "Sống ở biển, yêu biển. Công việc tự do, thích khám phá những điều mới.", "age": 30},

    {"name": "Hương", "gender": "female", "interested_in": "male", "city": "Đà Nẵng", "goal": "not_sure",
     "hobbies": ["Bơi lội", "Yoga", "Nấu ăn"], "traits": ["Dịu dàng", "Kiên nhẫn"],
     "bio": "Giáo viên yoga, yêu sự cân bằng trong cuộc sống.", "age": 24},

    {"name": "Phúc", "gender": "male", "interested_in": "female", "city": "Hội An", "goal": "serious",
     "hobbies": ["Nhiếp ảnh", "Cà phê", "Du lịch", "Đọc sách"], "traits": ["Nghệ sĩ", "Lãng mạn"],
     "bio": "Nhiếp ảnh gia tự do, chuyên chụp ảnh cưới. Tin vào tình yêu đích thực.", "age": 32},

    {"name": "Mai", "gender": "female", "interested_in": "male", "city": "Hội An", "goal": "serious",
     "hobbies": ["Nấu ăn", "Vẽ", "Yoga", "Du lịch"], "traits": ["Ấm áp", "Tận tâm"],
     "bio": "Đầu bếp yêu thích ẩm thực Việt, muốn tìm người cùng chia sẻ đam mê.", "age": 28},

    {"name": "Long", "gender": "male", "interested_in": "female", "city": "Nha Trang", "goal": "casual",
     "hobbies": ["Lặn biển", "Gym", "Du lịch"], "traits": ["Vui vẻ", "Nhiệt tình"],
     "bio": "Hướng dẫn viên lặn biển, sống hết mình với đam mê đại dương.", "age": 27},

    {"name": "Nhung", "gender": "female", "interested_in": "male", "city": "Nha Trang", "goal": "friends_first",
     "hobbies": ["Bơi lội", "Tennis", "Âm nhạc"], "traits": ["Hoạt bát", "Thân thiện"],
     "bio": "Sinh viên năm cuối, yêu thể thao và những buổi chiều trên bãi biển.", "age": 22},

    {"name": "Sơn", "gender": "male", "interested_in": "female", "city": "Huế", "goal": "serious",
     "hobbies": ["Đọc sách", "Thiền", "Viết lách", "Piano"], "traits": ["Trầm tính", "Sâu sắc"],
     "bio": "Giảng viên đại học, thích sự yên tĩnh và những cuộc trò chuyện có chiều sâu.", "age": 35},

    {"name": "Hà", "gender": "female", "interested_in": "male", "city": "Huế", "goal": "serious",
     "hobbies": ["Nấu ăn", "Đọc sách", "Du lịch"], "traits": ["Dịu dàng", "Truyền thống"],
     "bio": "Yêu văn hóa Huế, thích nấu những món ăn cung đình.", "age": 26},

    {"name": "Đức", "gender": "male", "interested_in": "female", "city": "Cần Thơ", "goal": "serious",
     "hobbies": ["Cà phê", "Du lịch", "Nhiếp ảnh"], "traits": ["Chân thành", "Giản dị"],
     "bio": "Kỹ sư phần mềm yêu miền Tây, thích cuộc sống chậm rãi và bình yên.", "age": 29},

    {"name": "Lan", "gender": "female", "interested_in": "male", "city": "Cần Thơ", "goal": "casual",
     "hobbies": ["Du lịch", "Chạy bộ", "Xem phim"], "traits": ["Năng động", "Vui tính"],
     "bio": "Nhân viên marketing, thích khám phá ẩm thực và du lịch bụi.", "age": 25},

    {"name": "Việt", "gender": "male", "interested_in": "female", "city": "Hải Phòng", "goal": "serious",
     "hobbies": ["Gym", "Bơi lội", "Đọc sách"], "traits": ["Mạnh mẽ", "Quyết đoán"],
     "bio": "Doanh nhân trẻ, nghiêm túc trong công việc và tình cảm.", "age": 33},

    {"name": "Chi", "gender": "female", "interested_in": "male", "city": "Hải Phòng", "goal": "serious",
     "hobbies": ["Yoga", "Nấu ăn", "Du lịch"], "traits": ["Đảm đang", "Thẳng thắn"],
     "bio": "Kế toán yêu sự ngăn nắp, mong tìm được người đàn ông trưởng thành.", "age": 27},

    {"name": "Dũng", "gender": "male", "interested_in": "female", "city": "Vũng Tàu", "goal": "casual",
     "hobbies": ["Lướt sóng", "Bơi lội", "Cà phê"], "traits": ["Phóng khoáng", "Hài hước"],
     "bio": "Surfer chuyên nghiệp, sống theo con sóng và những chuyến đi.", "age": 26},

    {"name": "Ngọc", "gender": "female", "interested_in": "male", "city": "Vũng Tàu", "goal": "friends_first",
     "hobbies": ["Bơi lội", "Yoga", "Vẽ"], "traits": ["Mộng mơ", "Dịu dàng"],
     "bio": "Kiến trúc sư yêu biển, thích vẽ tranh phong cảnh.", "age": 24},

    {"name": "Bình", "gender": "male", "interested_in": "female", "city": "Hồ Chí Minh", "goal": "serious",
     "hobbies": ["Gym", "Đọc sách", "Du lịch", "Cà phê"], "traits": ["Kỷ luật", "Trung thành"],
     "bio": "Quân nhân đã nghỉ hưu, giờ làm PT. Nghiêm túc tìm bạn đời.", "age": 34},

    {"name": "An", "gender": "female", "interested_in": "male", "city": "Hồ Chí Minh", "goal": "casual",
     "hobbies": ["Nhảy", "Âm nhạc", "Thời trang"], "traits": ["Sôi nổi", "Tự tin"],
     "bio": "Dancer kiêm stylist, yêu nghệ thuật và cuộc sống về đêm.", "age": 23},

    {"name": "Thy", "gender": "female", "interested_in": "male", "city": "Đà Lạt", "goal": "serious",
     "hobbies": ["Trekking", "Cà phê", "Nhiếp ảnh", "Vẽ"], "traits": ["Lãng mạn", "Tinh tế"],
     "bio": "Florist yêu hoa và núi rừng. Mong tìm được người cùng ngắm bình minh trên đồi.", "age": 26},

    {"name": "Khoa", "gender": "male", "interested_in": "female", "city": "Hà Nội", "goal": "serious",
     "hobbies": ["Piano", "Đọc sách", "Thiền", "Cà phê"], "traits": ["Lịch lãm", "Kiên nhẫn"],
     "bio": "Luật sư yêu âm nhạc cổ điển, tìm người cùng chia sẻ gu thẩm mỹ.", "age": 36},

    {"name": "Nhi", "gender": "female", "interested_in": "male", "city": "Đà Nẵng", "goal": "friends_first",
     "hobbies": ["Du lịch", "Nhiếp ảnh", "Nấu ăn"], "traits": ["Tò mò", "Nhiệt huyết"],
     "bio": "Travel blogger, đã đi 20 nước. Giờ muốn tìm người đồng hành.", "age": 28},

    {"name": "Phong", "gender": "male", "interested_in": "female", "city": "Hồ Chí Minh", "goal": "casual",
     "hobbies": ["Tennis", "Gym", "Xem phim", "Cà phê"], "traits": ["Lịch thiệp", "Thoải mái"],
     "bio": "Quản lý khách sạn, thích gặp gỡ và kết nối con người.", "age": 30},

    {"name": "Vân", "gender": "female", "interested_in": "male", "city": "Hà Nội", "goal": "serious",
     "hobbies": ["Đọc sách", "Viết lách", "Yoga"], "traits": ["Trí thức", "Độc lập"],
     "bio": "Nhà báo tự do, yêu sự thật và những câu chuyện đời thường.", "age": 29},

    {"name": "Quân", "gender": "male", "interested_in": "female", "city": "Nha Trang", "goal": "not_sure",
     "hobbies": ["Lặn biển", "Du lịch", "Âm nhạc"], "traits": ["Bí ẩn", "Sâu sắc"],
     "bio": "Cựu thủy thủ, giờ mở quán bar bên biển. Chưa rõ mình muốn gì.", "age": 31},

    {"name": "Giang", "gender": "female", "interested_in": "male", "city": "Hội An", "goal": "serious",
     "hobbies": ["Vẽ", "Yoga", "Nấu ăn", "Đọc sách"], "traits": ["Nghệ sĩ", "Chân thành"],
     "bio": "Họa sĩ minh họa sách thiếu nhi. Yêu trẻ con và mơ về một gia đình nhỏ.", "age": 27},

    {"name": "Tâm", "gender": "male", "interested_in": "female", "city": "Cần Thơ", "goal": "serious",
     "hobbies": ["Cà phê", "Đọc sách", "Chạy bộ", "Thiền"], "traits": ["Điềm đạm", "Tử tế"],
     "bio": "Bác sĩ thú y, yêu động vật và cuộc sống miệt vườn.", "age": 32},
]

# ── Match pairs (indices into USERS array) ──
MATCH_PAIRS = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]  # Linh-Khang, Thảo-Huy, v.v.
PENDING_LIKES = [(10, 11), (12, 13), (14, 15), (16, 17), (18, 19), (20, 21), (22, 23), (24, 25), (26, 27), (28, 29)]


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
        # Manually set admin role via DB later, skip for now

        # ── Create 30 users ──
        for i, u in enumerate(USERS):
            username = u["name"].lower()
            print(f"  [{i+1}/30] Creating {u['name']} ({username})...")

            r = await client.post("/api/auth/register", json={
                "username": username, "password": DEMO_PASSWORD,
                "confirm_password": DEMO_PASSWORD, "date_of_birth": random_dob(u["age"]),
            })
            if r.status_code != 200:
                print(f"    ERROR: {r.status_code} {r.text[:200]}")
                continue
            data = r.json()
            token = data["data"]["access_token"]
            tokens.append({"token": token, "username": username, "name": u["name"], "idx": i})
            h = {"Authorization": f"Bearer {token}"}

            # Update profile
            prefs = {
                "preferred_age_min": max(18, u["age"] - 5),
                "preferred_age_max": u["age"] + 5,
                "preferred_distance_km": random.choice([30, 50, 100, 200]),
                "preferred_gender": u["interested_in"],
            }
            r = await client.patch("/api/profile/me", headers=h, json={
                "display_name": u["name"],
                "gender": u["gender"],
                "interested_in": u["interested_in"],
                "city": u["city"],
                "dating_goal": u["goal"],
                "bio": u["bio"],
                "hobbies": u["hobbies"],
                "personality_traits": u["traits"],
                "preferences": prefs,
                "public_summary": u["bio"],
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

                # Add a chat message for some matches
                if len(match_ids) <= 3:
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

            await client.post(f"/api/matches/{to_uid}/like", headers=ha)
            print(f"  💖 {tokens[from_idx]['name']} → {tokens[to_idx]['name']} (pending)")

        print()
        print("=" * 50)
        print("🌱 SEED COMPLETE!")
        print(f"   {len(tokens)} regular users")
        print(f"   {len(match_ids)} mutual matches")
        print(f"   {len(PENDING_LIKES)} pending likes")
        print()
        print("Demo accounts (password: demo123456):")
        print(f"   🌿 Linh (linh) — primary demo user")
        print(f"   💞 Khang (khang) — matched with Linh")
        for t in tokens[:5]:
            print(f"   👤 {t['name']} ({t['username']})")
        print()
        print("Admin: username 'admin' / password 'demo123456' (set role=admin via DB)")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())
