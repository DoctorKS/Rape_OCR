# CODEX Guide

ไฟล์นี้เป็นคู่มือเฉพาะโปรเจกต์สำหรับ Codex, AI agent และ developer ที่ทำงานใน
repository นี้ โดยไม่แทนที่ `AGENTS.md` แต่เพิ่มบริบทของระบบและ workflow ที่ควร
ทำตาม

## Agent Rules

1. อ่าน `README.md` ก่อนเริ่มงานทุกครั้ง
2. อธิบายงานเป็นภาษาไทย เว้นแต่ผู้ใช้ขอภาษาอื่นชัดเจน
3. แยกงานเป็น block ให้ชัดเจน เช่น:
   - debugging block
   - coding block
   - review block
4. หลังจบแต่ละ block ต้องทำ checklist ว่าทำอะไรเสร็จแล้ว
5. ต้องถามก่อนใช้ `git add` หรือ `git commit`
6. ถ้าผู้ใช้พิมพ์ `[dks]` ให้ข้าม requirement การถามก่อน commit เฉพาะคำสั่งนั้น
7. ถ้า instruction ไม่ชัด ต้องถาม clarification ก่อนเดินหน้าต่อ
8. ห้าม revert งานของผู้ใช้ เว้นแต่ผู้ใช้สั่งชัดเจน
9. จำกัดการแก้ไขให้อยู่ใน scope ของงานที่ขอ

## Project Goal

สร้าง native Windows OCR app สำหรับเอกสารนิติเวช 2 pattern:

- `ppk_rape`
- `rural_rape`

แอปต้องอ่านข้อมูลตัวพิมพ์และลายมือไทย/อังกฤษ ให้ผู้ใช้ตรวจทานและแก้ไขผล OCR
เติมข้อมูลที่ยืนยันแล้วลงใน `.docx` template และเก็บข้อมูลที่ review แล้วกลับไป
เป็น dataset สำหรับเทรนต่อ

## Architecture Guide

ระบบที่ตั้งใจใช้แบ่งเป็น service ย่อยในเครื่อง:

- Desktop UI: PySide6 app สำหรับ import รูป, review OCR, แก้ field และ generate
  เอกสาร
- Local API: FastAPI server ที่ bind เฉพาะ `127.0.0.1`
- OCR service: ใช้ PaddleOCR เป็นหลัก ร่วมกับ OpenCV สำหรับ preprocess
- Template service: map ค่าที่ review แล้วไปยัง `.docx` content controls หรือ XML
  tags
- Dataset recycling service: เก็บเอกสารที่ review แล้วทุกฉบับเป็น training
  candidate
- Storage service: ใช้ SQLite database และ folder ภายในเครื่อง

## Coding Conventions

- ใช้ typed Python functions เมื่อเหมาะสม
- แยก logic เป็น service เล็ก ๆ ที่ test ได้ง่าย
- เก็บ behavior เฉพาะเอกสารไว้ใน config แทน hard-code ใน source code
- ใช้ config-driven templates สำหรับ field boxes, expected formats, checkbox
  positions และ destination `.docx` tags
- แยกค่า OCR prediction, validation result, reviewer correction และ final export
  state ออกจากกัน
- ใส่ comment เฉพาะจุดที่ logic ไม่ชัดจาก code เอง

## Data Safety

- ไม่ส่งรูป, OCR output, ข้อมูลผู้ป่วย หรือข้อมูลคดีออก external service โดย
  default
- OCR, LLM และ document generation ต้องรัน local เว้นแต่ผู้ใช้เปลี่ยน privacy
  requirement ชัดเจน
- เก็บ raw image แยกจาก reviewed label
- เก็บ audit log สำหรับ:
  - imported files
  - OCR predictions
  - reviewer corrections
  - generated `.docx` files
  - model version ที่ใช้กับแต่ละ job
- ถือว่า human-reviewed label เป็น source of truth

## Dataset Recycling

เอกสารทุกฉบับที่ผ่าน human review ต้องถูกนำกลับเข้า dataset เป็น training
candidate โดยเก็บข้อมูลต่อไปนี้:

- original image
- document pattern
- field bounding boxes
- OCR prediction
- reviewer-approved value
- checkbox state
- confidence score
- correction status
- destination `.docx` field

ห้ามนำเอกสารใหม่ที่ recycle แล้วไปรวมกับ frozen test set อัตโนมัติ ต้องมีขั้นตอน
dataset promotion ที่ควบคุมได้สำหรับ train, validation และ test split

## Testing Expectations

ควรมี test แยกตาม layer:

- OCR golden document tests สำหรับ sample input ที่คงที่
- Template fill tests เพื่อยืนยันว่า `.docx` output ลง field ถูกต้อง
- API tests สำหรับ FastAPI endpoints ที่รันใน local
- Dataset recycling tests เพื่อยืนยันว่า reviewed value ถูกบันทึกพร้อม metadata
  ที่ถูกต้อง
- Regression tests ก่อนเปลี่ยน OCR model หรือปรับ template coordinates

ก่อน deploy model ใหม่ ต้องเทียบกับ model เดิมบน golden document set เดียวกัน

## Review Checklist

หลังจบแต่ละ block ให้ review:

- เปลี่ยนอะไรไปบ้าง
- แตะไฟล์ไหนบ้าง
- ตรวจสอบอะไรแล้ว
- ยังมี risk หรือจุดที่ยังไม่ได้ test อะไร
- ผู้ใช้ขอ `git add` หรือ `git commit` หรือไม่

