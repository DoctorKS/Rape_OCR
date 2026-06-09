# Rape OCR

แอป Native บน Windows สำหรับ OCR เอกสารนิติเวชภาษาไทย/อังกฤษ ดึงข้อมูลจาก
เอกสารที่มีทั้งตัวพิมพ์ ลายมือ และ checkbox แล้วให้ผู้ใช้ตรวจทานก่อนนำข้อมูลไป
เติมลงในไฟล์ `.docx` template

## ภาพรวมระบบ

โปรเจกต์นี้ออกแบบสำหรับเอกสาร 2 pattern หลัก:

- `ppk_rape`: เอกสารรายงานผลแล็บ/ใบแสดงรายการชันสูตรและบริการทางนิติเวช
  รูปแบบโรงพยาบาลพระปกเกล้า
- `rural_rape`: เอกสาร specimen examination request form จากโรงพยาบาลหรือ
  หน่วยงานเครือข่าย

Workflow หลัก:

1. นำเข้ารูปภาพหรือเอกสาร scan
2. ตรวจว่าเป็น pattern `ppk_rape` หรือ `rural_rape`
3. ปรับภาพก่อน OCR เช่น หมุนภาพ ตัดขอบ แก้ perspective และลดเงา
4. OCR เฉพาะตำแหน่ง field ที่กำหนดไว้ใน template config
5. ตรวจและ normalize ค่าที่อ่านได้
6. แสดงผลทุก field ให้คนตรวจทาน
7. เติมค่าที่ตรวจแล้วลงใน `.docx` template
8. สร้างเอกสารใหม่ใน output folder
9. นำเอกสารที่ตรวจแล้วกลับเข้า recycling dataset เพื่อใช้เทรนต่อ

ถ้า reviewer ใส่ค่า `-` ในช่อง `Reviewed` ระบบจะจำว่า field นั้นไม่ต้อง OCR ใน
ครั้งต่อไปสำหรับ pattern เดียวกัน และจะแสดง field นั้นเป็น `skipped`

## หลักการออกแบบ

- Offline-first: ข้อมูลผู้ป่วยและข้อมูลคดีเป็นข้อมูลอ่อนไหว จึงไม่ควรส่งภาพ
  หรือข้อมูล OCR ออกนอกเครื่องโดย default
- Human review ก่อน export: ผล OCR เป็นเพียงคำแนะนำ ผู้ใช้ต้องตรวจทานก่อน
  generate `.docx`
- Template-driven extraction: แต่ละ pattern ต้องมี config ระบุ field zone,
  format ที่คาดหวัง, checkbox position และ field ปลายทางใน `.docx`
- Continuous improvement: เอกสารใหม่ทุกฉบับที่ผ่านการตรวจแล้วต้องถูกเก็บเป็น
  training candidate เพื่อปรับปรุง OCR และ field mapping ในอนาคต

## Tech Stack ที่แนะนำและเหตุผล

### PySide6

เลือก PySide6 สำหรับทำ native desktop app บน Windows เพราะฟรี ใช้กับ Python ได้
ตรง และเชื่อมกับ OCR pipeline, image processing, database และ document
generation ในเครื่องเดียวได้ง่าย เหมาะกับ workflow ในโรงพยาบาลที่ต้องการแอป
desktop แบบ offline มากกว่าเว็บที่ต้องพึ่ง server ภายนอก

### FastAPI

เลือก FastAPI สำหรับ local API เพราะแยกหน้าที่ระหว่าง UI กับ backend ได้ชัด
เขียน endpoint เองได้ง่าย test ได้ง่าย และสามารถเปิดเฉพาะ `127.0.0.1` เพื่อให้
ระบบยังเป็น local/offline ในเวอร์ชันแรก

### PaddleOCR

เลือก PaddleOCR เป็น OCR หลัก เพราะมี pipeline รุ่นใหม่สำหรับ OCR และ document
recognition รวมถึงรองรับภาษาไทย เหมาะกับเอกสารที่มีไทย/อังกฤษปนกันและรูปถ่าย
จากสภาพจริงมากกว่า Tesseract โดยเฉพาะงาน layout/recognition ที่ซับซ้อน

### OpenCV

เลือก OpenCV สำหรับ preprocess ภาพ เพราะรูปจริงอาจเอียง มีเงา กระดาษยับ
ถ่ายไม่เต็มหน้า หรือมี perspective เพี้ยน ขั้นตอนอย่าง rotate correction,
perspective correction, crop, threshold และ shadow reduction ควรทำก่อนส่งเข้า OCR

### Tesseract

ใช้ Tesseract เป็น fallback เฉพาะบางกรณี เช่น ตัวพิมพ์ เลข หรือข้อความที่คล้าย
barcode ไม่ควรใช้เป็น OCR หลักสำหรับลายมือไทย เพราะความเสี่ยงเรื่อง accuracy สูง
กว่า PaddleOCR ใน use case นี้

### Ollama หรือ Local LLM

ใช้ LLM ที่รันในเครื่องผ่าน Ollama เพื่อช่วย normalize ข้อความ map field และ
ตรวจ consistency เท่านั้น ไม่ใช้แทน OCR และไม่ถือว่า LLM เป็น source of truth
ค่าที่ผู้ใช้ตรวจทานแล้วเท่านั้นคือค่าจริงสำหรับ export และ training label

### SQLite

เลือก SQLite เพราะฟรี เบา ใช้งานใน local app ได้ทันที ไม่ต้องติดตั้ง database
server เพิ่ม และเพียงพอสำหรับเก็บ job, OCR result, confidence, correction,
review status, export history และ audit log

### python-docx และ DOCX XML

ใช้ `python-docx` สำหรับสร้างหรือแก้เอกสาร Word และใช้การแก้ DOCX XML เพิ่มเติม
เมื่อจำเป็น โดยเฉพาะกรณีที่ต้อง fill content controls หรือ custom tag ใน `.docx`
ควรกำหนด tag ที่เสถียร เช่น `lab_no`, `patient_name`, `hn`, `collection_date`
และ `item_1_result`

### PyInstaller

เลือก PyInstaller สำหรับ package แอปเป็น `.exe` บน Windows เพื่อให้ deploy ไปยัง
เครื่องใช้งานจริงได้ง่าย

## แนวทาง Dataset

ช่วงแรกควรเริ่มโดยยังไม่ fine-tune model ก่อน ใช้ข้อมูลชุดแรกเพื่อทำ template
coordinate วัด baseline accuracy และหา field ที่ OCR ยาก

- Baseline: เอกสารที่ตรวจแล้ว 30-50 ใบต่อ pattern
- Early production: เอกสารที่ตรวจแล้ว 200-300 ใบต่อ pattern
- Fine-tune ลายมือ: อย่างน้อย 1,000-2,000 crop ที่ label ถูกต้องต่อกลุ่ม field
  สำคัญ
- รองรับลายมือหลากหลาย: ควรมี 5,000+ crop เมื่อมีหลายคนเขียน หลายโรงพยาบาล
  หรือหลายสภาพแสง/กล้อง

ข้อมูลที่ควรเก็บจากเอกสารที่ review แล้ว:

- รูปต้นฉบับ
- document pattern
- bounding box ของแต่ละ field
- OCR prediction เดิม
- label ที่ผู้ใช้ยืนยันหรือแก้ไข
- checkbox state
- mapping ไปยัง field ใน `.docx`
- confidence score และ correction status

ห้ามนำ recycling data ไปรวมกับ test set แบบอัตโนมัติ ควรมีขั้นตอน dataset
promotion เพื่อเลือกว่าจะเข้า train, validation หรือเก็บเป็น candidate ต่อ

## Architecture ที่คาดหวัง

- Desktop UI: หน้าจอ Windows สำหรับ import, review, correction และ export
- Local API: FastAPI ที่รันบน localhost
- OCR service: preprocess ภาพ, detect pattern, extract field, OCR และ detect
  checkbox
- Template service: map ค่าที่ตรวจแล้วไปยัง content controls หรือ tag ใน `.docx`
- Dataset recycling service: เก็บรูป crop label correction และ metadata สำหรับ
  training รอบถัดไป
- Storage: SQLite database และ folder ภายในเครื่องสำหรับ raw image, reviewed
  crop, template, generated document และ model version

ดู flow chart และ Mermaid diagram เพิ่มเติมได้ที่ [docs/architecture.md](docs/architecture.md)
ไฟล์นี้ครอบคลุม flow ปัจจุบันทั้งหมดของ app ได้แก่ GUI, CLI, Local API,
PaddleOCR/fallback, DOCX export, recycling dataset, และ field ล่างของ
`rural_rape`

## วิธีรัน MVP

ติดตั้ง dependency พื้นฐาน:

```powershell
python -m pip install -e .
```

ถ้าต้องการ GUI, API, OpenCV และ OCR stack เต็ม ให้ติดตั้ง optional dependencies:

```powershell
python -m pip install -e ".[app]"
```

แนะนำให้ใช้ virtual environment แยกของโปรเจกต์:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[app]"
```

เปิด native GUI:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --gui
```

เปิด local API ที่ `127.0.0.1:8765`:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --api
```

ประมวลผลรูปตัวอย่างด้วย PaddleOCR จริง เพื่อทดสอบ pipeline, SQLite และ recycling
dataset:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --sample docs\example\S__29351955_0.jpg
```

โดย default ระบบจะซ่อน log ยาวจาก PaddleOCR เพื่อให้อ่านผลลัพธ์ง่าย ถ้าต้องการดู
log เต็มให้เพิ่ม `--verbose-ocr`:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --sample docs\example\S__29351955_0.jpg --verbose-ocr
```

ถ้าต้องการทดสอบ pipeline โดยไม่โหลด PaddleOCR ให้ใช้ placeholder mode:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --sample docs\example\S__29351955_0.jpg --placeholder-ocr
```

ตรวจรายการ recycling dataset ที่เก่ากว่า 90 วันแบบ dry-run:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --cleanup-recycling-days 90
```

ลบจริงต้องเพิ่ม `--confirm-delete` เท่านั้น:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --cleanup-recycling-days 90 --confirm-delete
```

ลบ recycling entry รายตัวแบบ dry-run:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --delete-recycling-entry rural_rape/20260609T115856Z_d01b8adcfb8740a8a8acb261b617d65d
```

ลบรายตัวจริงต้องเพิ่ม `--confirm-delete`:

```powershell
.\.venv\Scripts\python.exe -m rape_ocr.main --delete-recycling-entry rural_rape/20260609T115856Z_d01b8adcfb8740a8a8acb261b617d65d --confirm-delete
```

หมายเหตุ: PaddleOCR จะดาวน์โหลดโมเดลครั้งแรกลงใน cache ของผู้ใช้ เช่น
`C:\Users\User\.paddlex\official_models`

ไฟล์ใน `docs/example/` ใช้เป็นข้อมูลตัวอย่าง local เท่านั้น และไม่ควร commit หรือ
push หากมีข้อมูลผู้ป่วย/ข้อมูลคดีจริง

รัน test ด้วยเครื่องมือมาตรฐานของ Python:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Safety Rules

- ไม่ส่งภาพผู้ป่วยหรือข้อมูล OCR ออก internet โดย default
- ต้องมีขั้นตอน review ก่อน generate เอกสาร
- ต้องเก็บ audit log ของเอกสารที่ generate และ correction ที่ผู้ใช้แก้
- ต้องแยก raw OCR prediction ออกจาก human-approved label
- ก่อนเปลี่ยน model ที่ใช้งานจริง ต้องเทียบ model ใหม่กับ model เดิมบน golden
  document set เดียวกัน
