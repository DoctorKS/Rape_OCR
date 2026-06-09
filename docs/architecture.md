# Architecture Flow

เอกสารนี้สรุป flow ทั้งหมดที่มีใน Rape OCR app ปัจจุบัน ตั้งแต่ทางเข้าแบบ GUI,
CLI และ Local API ไปจนถึง OCR, human review, DOCX export และ recycling dataset
สำหรับเทรนต่อ

## App Entry Points

```mermaid
flowchart TD
    A["PowerShell / User"] --> B{"เลือกโหมดใช้งาน"}
    B -->|"--gui"| C["Native GUI\nPySide6"]
    B -->|"--api"| D["Local API\nFastAPI 127.0.0.1:8765"]
    B -->|"--sample <image>"| E["CLI sample pipeline"]

    C --> F["Import image"]
    C --> G["OCR"]
    C --> H["Save Review"]
    C --> I["Export DOCX"]

    D --> J["GET /health"]
    D --> K["GET /patterns"]
    D --> L["POST /jobs"]
    D --> M["POST /jobs/{job_id}/review"]
    D --> N["POST /jobs/{job_id}/export"]

    E --> O["Run OCR service"]
    E --> P["Save SQLite job"]
    E --> Q["Save recycling metadata"]
```

## End-to-End GUI Workflow

```mermaid
flowchart TD
    A["ผู้ใช้เปิด GUI"] --> B["กด Import เลือกรูปเอกสาร"]
    B --> C["กด OCR"]
    C --> D["Pattern Detection"]
    D --> E{"ชนิดเอกสาร"}
    E -->|"ppk_rape"| F["โหลด ppk_rape config"]
    E -->|"rural_rape"| G["โหลด rural_rape config"]
    F --> H["Crop field zones ตาม config"]
    G --> H
    H --> I["Preprocess ต่อ field\nเช่น table_date / handwriting / result_choice"]
    I --> J["OCR Engine"]
    J -->|"PaddleOCR พร้อม"| K["OCR prediction + confidence"]
    J -->|"--placeholder-ocr หรือ PaddleOCR ไม่พร้อม"| K
    K --> L["เก็บ raw_prediction"]
    L --> M["Normalize field เฉพาะทาง\nเช่น positive / negative"]
    M --> N["แสดงผลในตาราง GUI\nField / OCR / Reviewed / Confidence / Status"]
    N --> O{"Reviewer แก้ช่อง Reviewed แล้วหรือยัง"}
    O -->|"ยัง"| N
    O -->|"Reviewed = '-'"| X["จำ field ลง skipped_fields\npattern + field_name"]
    O -->|"Save Review"| P["บันทึก reviewed job ลง SQLite"]
    X --> P
    P --> Q["Dataset Recycling Service"]
    Q --> R["metadata.json + original image copy"]
    O -->|"Export DOCX"| S["เลือก .docx template"]
    S --> T["Template Service\nแทนค่า docx_tag / placeholder"]
    T --> U["Generated .docx output"]
```

## Local Component Diagram

```mermaid
flowchart LR
    subgraph "Windows Local Machine"
        UI["PySide6 Desktop UI"]
        API["FastAPI Local API\n127.0.0.1 only"]
        CLI["CLI\n--sample / --placeholder-ocr / --verbose-ocr"]
        OCR["OCR Service\nPaddleOCR + OpenCV\nwith placeholder fallback"]
        CFG["Pattern Configs\nppk_rape / rural_rape"]
        TPL["Template Service\npython-docx / DOCX XML"]
        DB[("SQLite\njobs, fields, audit")]
        DS[("Recycling Dataset\nreviewed labels + metadata")]
        OUT["Generated .docx output"]
    end

    UI <--> API
    CLI --> OCR
    API --> CFG
    OCR --> CFG
    API --> OCR
    API --> TPL
    API --> DB
    API --> DS
    UI --> OCR
    UI --> DB
    UI --> DS
    UI --> TPL
    TPL --> OUT
```

## OCR Field Extraction Flow

```mermaid
flowchart TD
    A["Input image"] --> B["Detect pattern"]
    B --> C{"pattern"}
    C -->|"ppk_rape"| D["ppk_rape fields"]
    C -->|"rural_rape"| E["rural_rape fields"]
    D --> F["Crop bbox per field"]
    E --> F
    F --> G{"field kind / preprocess"}
    G -->|"field อยู่ใน skipped_fields"| X["ไม่ OCR\nprediction='-'\nstatus='skipped'"]
    G -->|"text"| H["OCR crop as-is"]
    G -->|"checkbox"| I["OpenCV dark-ratio checkbox detection"]
    G -->|"table_date"| J["Upscale + adaptive threshold\nfor lower table date/time"]
    G -->|"handwriting"| K["Upscale + adaptive threshold\nfor lower handwritten notes"]
    G -->|"result_choice"| L["Upscale + adaptive threshold\nthen normalize result"]
    H --> M["PaddleOCR prediction"]
    J --> M
    K --> M
    L --> M
    I --> N["checked / unchecked"]
    X --> S["FieldResult"]
    M --> O["raw_prediction"]
    O --> P{"special normalize"}
    P -->|"result_choice"| Q["positive / negative"]
    P -->|"normal field"| R["prediction = raw_prediction"]
    N --> S["FieldResult"]
    Q --> S
    R --> S
```

## Rural Lower Fields

```mermaid
flowchart TD
    A["rural_rape lower area"] --> B["For laboratory officer table"]
    A --> C["Lower-left handwritten result"]
    A --> D["Lower-right handwritten date/note"]

    B --> B1["specimen_regis_date"]
    B --> B2["specimen_regis_time"]
    B --> B3["extraction_date"]
    B --> B4["extraction_time"]
    B --> B5["sperm_exam_date"]
    B --> B6["sperm_exam_time"]

    C --> C1["vaginal_result"]
    C --> C2["endocervical_result"]
    C1 --> C3["Normalize to positive / negative"]
    C2 --> C3

    D --> D1["lower_right_handwritten_date"]
    D --> D2["lower_right_handwritten_note"]
```

## Review and Training Loop

```mermaid
sequenceDiagram
    participant User as Reviewer
    participant App as Desktop App
    participant OCR as OCR Service
    participant DB as SQLite
    participant DS as Recycling Dataset
    participant Docx as DOCX Generator

    User->>App: Import document image
    App->>OCR: Detect pattern and extract fields
    OCR-->>App: raw_prediction, prediction, confidence, bbox
    User->>App: Review and correct values
    App->>DB: Save reviewed job and audit data
    App->>DS: Save training candidate metadata
    App->>Docx: Fill approved values
    Docx-->>User: New generated .docx
```

## API Flow

```mermaid
sequenceDiagram
    participant Client as Local client
    participant API as FastAPI app
    participant OCR as OCR Service
    participant DB as SQLite
    participant DS as Recycling Dataset
    participant DOCX as Template Service

    Client->>API: GET /health
    API-->>Client: status, offline, ocr_engine
    Client->>API: GET /patterns
    API-->>Client: ppk_rape, rural_rape
    Client->>API: POST /jobs {image_path, pattern_name?}
    API->>DB: read skipped_fields for pattern
    API->>OCR: process image
    OCR-->>API: reviewed_payload
    API->>DB: save pending job
    API-->>Client: job fields
    Client->>API: POST /jobs/{job_id}/review
    API->>DB: save reviewed values
    API->>DS: save metadata.json
    API-->>Client: metadata path
    Client->>API: POST /jobs/{job_id}/export
    API->>DOCX: fill template
    API-->>Client: output_path
```

## CLI Flow

```mermaid
flowchart TD
    A["PowerShell"] --> B["python -m rape_ocr.main --sample <image>"]
    B --> C{"OCR mode"}
    C -->|"default"| D["PaddleOCR\nlogs hidden"]
    C -->|"--verbose-ocr"| E["PaddleOCR\nshow model logs"]
    C -->|"--placeholder-ocr"| F["Placeholder OCR\nno model load"]
    D --> G["OCR service process image"]
    E --> G
    F --> G
    G --> H["Save job to data/app.db"]
    H --> I["Save metadata to data/recycling"]
    I --> J["Print job_id, pattern, ocr_engine, fields, metadata"]
```

## Storage and Output Paths

```mermaid
flowchart TD
    A["OCR job"] --> B[("data/app.db")]
    B --> B1[("skipped_fields\npattern_name + field_name")]
    A --> C["data/recycling/<pattern>/<timestamp_jobid>/metadata.json"]
    A --> D["data/recycling/<pattern>/<timestamp_jobid>/<original_image>"]
    A --> E["output/generated.docx\nหรือ path ที่ user เลือก"]
    A --> F["docs/example/\nlocal-only sample files"]
    F -. "ignored by git" .-> G["ไม่ push ขึ้น remote"]
```

## ขอบเขตข้อมูลที่ต้องระวัง

- `data/`, `output/` และ `docs/example/` เป็นข้อมูล local/runtime หรือไฟล์ตัวอย่าง
  ที่อาจมีข้อมูลอ่อนไหว จึงไม่ควร commit ขึ้น remote
- ค่าที่ใช้ train ต่อควรมาจาก human-reviewed label เท่านั้น
- ห้ามนำ recycling data เข้า frozen test set แบบอัตโนมัติ
- `raw_prediction` คือผล OCR ดิบ ส่วน `prediction` อาจเป็นค่าที่ normalize แล้ว
  เช่น `positive` หรือ `negative`
- ถ้า reviewer ใส่ `-` ใน `Reviewed` field นั้นจะถูกบันทึกใน `skipped_fields`
  และรอบถัดไปจะไม่ OCR field นั้นใน pattern เดียวกัน
