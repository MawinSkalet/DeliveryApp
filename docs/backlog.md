**Backlog ที่นำไปเปิด Issue ได้ทันที**

| ID       | งาน                                       | เสร็จเมื่อ                                         |
| -------- | ----------------------------------------- | -------------------------------------------------- |
| SETUP-01 | สร้าง monorepo และ Compose                | เปิด `api`, `frontend`, `postgres`, `mongo` ได้    |
| SETUP-02 | ทำ health checks และ environment template | ไม่มี secrets ใน Git และ API รอ DB พร้อม           |
| DB-01    | ทำ PostgreSQL schema                      | มี PK, FK, unique, check constraints และ indexes   |
| DB-02    | ทำ MongoDB collections/indexes            | อ่านเมนูและพิกัดตาม query ที่ออกแบบได้             |
| DATA-01  | ทำ seed และ verify script                 | จำนวนครบ รันซ้ำได้ และข้อมูลสัมพันธ์กัน            |
| API-01   | Users API                                 | สร้าง/อ่านผู้ใช้และจัดการ email ซ้ำได้             |
| API-02   | Products API                              | สร้าง dynamic attributes และอ่านแบบ pagination ได้ |
| API-03   | Orders API                                | ใช้ข้อมูลสอง DB และบันทึกธุรกรรมถูกต้อง            |
| TRACK-01 | Location API                              | บันทึกพิกัดและไม่ให้ข้อมูลเก่าทับใหม่              |
| TEST-01  | Integration tests                         | ทดสอบสำเร็จ ล้มเหลว rollback และคำขอซ้ำ            |
| CI-01    | PR checks                                 | ตรวจโค้ด tests และ frontend build อัตโนมัติ        |
| DOC-01   | README / ERD / demo script                | สมาชิกอีกคน setup และ demo ตามเอกสารได้            |

ใช้บอร์ดเพียง **Todo → Doing → Review → Done** และให้แต่ละคนมีงานใน Doing ครั้งละหนึ่งงานหลัก