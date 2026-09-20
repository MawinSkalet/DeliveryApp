# CP1 team handoff

This repository has a working Compose setup, an Orders API, and PostgreSQL migration `0001_order_baseline`. Users and Products APIs, CP1 seed scripts, and MongoDB indexes are still missing.

**แบ่งทีมเป็นเจ้าของงาน**

สมมติทีม 4 คน โดยเปลี่ยน A–D เป็นชื่อจริงใน README และบอร์ดงาน

| สมาชิก                          | รับผิดชอบหลัก                         | ผลงาน Sprint 1                              |
| ------------------------------- | ------------------------------------- | ------------------------------------------- |
| **A — Backend / Relational DB** | Users, restaurants, PostgreSQL schema | DDL, migrations, Users API                  |
| **B — Catalog / Tracking**      | MongoDB, เมนู, พิกัด                  | Products API, tracking API, MongoDB indexes |
| **C — Orders / Transactions**   | ออร์เดอร์ สต็อก การจัดส่ง             | Orders API, rollback, ป้องกันคำขอซ้ำ        |
| **D — Frontend / Integration**  | React, Compose, CI, เชื่อมระบบ        | Project setup, หน้า demo พื้นฐาน, CI        |

**ทุกคนเขียน tests และ README ของส่วนตัวเอง** ส่วน seed ให้ A ดูแลข้อมูล PostgreSQL และ B ดูแล MongoDB โดย C ตรวจว่าออร์เดอร์กับสต็อกสัมพันธ์กัน

ถ้ามี 3 คน ให้กระจายงาน D: A ดู Compose, B ดูแผนที่, C ดูหน้า checkout และทุกคนช่วย CI

**มาตรฐาน setup ที่ต้องส่งมอบให้เพื่อน**

คนตั้ง repo ต้องเตรียมให้เพื่อนทำตามขั้นตอนนี้ได้จริง โดยคำสั่งด้านล่างเป็น **เป้าหมายของ repository ที่จะสร้าง** ไม่ใช่ไฟล์ที่มีพร้อมแล้วตอนนี้

1. ติดตั้ง Git และ Docker Desktop
2. Clone repository
3. คัดลอก `.env.example` เป็น `.env` และกำหนดค่าที่จำเป็น
4. เปิดระบบ สร้าง schema และ seed
5. เปิด Swagger และทดสอบออร์เดอร์ตัวอย่าง

หลัง clone และเตรียม `.env` แล้ว ใช้:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed
docker compose exec api python -m scripts.verify_seed
```

| สิ่งที่จะเปิด | URL ที่กำหนด                   |
| ------------- | ------------------------------ |
| Frontend      | `http://localhost:5173`        |
| Swagger       | `http://localhost:8000/docs`   |
| Health        | `http://localhost:8000/health` |

ต้องมี **DDL baseline ตาม requirement พร้อม migration history** โดย README อธิบายเส้นทาง setup ให้ชัด ไม่ให้ผู้ใช้รัน DDL และ migration สร้างตารางชุดเดียวกันซ้ำ

ฐานข้อมูลของแต่ละคนรันในเครื่องตัวเอง ส่วน CI ใช้ฐานข้อมูลทดสอบแยกต่างหาก