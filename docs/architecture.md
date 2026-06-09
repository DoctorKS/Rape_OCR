# Architecture Flow

เอกสารนี้สรุป flow หลักของ Rape OCR MVP ตั้งแต่ import เอกสารจนถึง export `.docx`
และ recycling dataset สำหรับเทรนต่อ

## End-to-End Workflow

```mermaid
flowchart TD
    A["ผู้ใช้ import รูป/scan เอกสาร"] --> B["Desktop UI (PySide6)"]
    B --> C["Local API / App Service"]
    C --> D["Pattern Detection"]
    D --> E{"ชนิดเอกสาร"}
    E -->|"ppk_rape"| F["โหลด ppk_rape template config"]
    E -->|"rural_rape"| G["โหลด rural_rape template config"]
    F --> H["Preprocess ภาพด้วย OpenCV"]
    G --> H
    H --> I["Crop เฉพาะ field zones"]
    I --> J["OCR Engine"]
    J -->|"PaddleOCR เมื่อพร้อม"| K["OCR prediction + confidence"]
    J -->|"Placeholder/Fallback"| K
    K --> L["Validation + normalization"]
    L --> M["Human Review UI"]
    M --> N{"Reviewer ยืนยันแล้ว?"}
    N -->|"ยัง"| M
    N -->|"ใช่"| O["บันทึก reviewed labels ลง SQLite"]
    O --> P["Fill .docx template"]
    P --> Q["Generate output document"]
    O --> R["Dataset Recycling Service"]
    R --> S["เก็บ original image, crops, prediction, correction, metadata"]
    S --> T["Training candidate pool"]
    T --> U["Controlled dataset promotion"]
    U --> V["Train / Validation"]
    U --> W["Frozen Test Set"]
```

## Local Component Diagram

```mermaid
flowchart LR
    subgraph "Windows Local Machine"
        UI["PySide6 Desktop UI"]
        API["FastAPI Local API\n127.0.0.1 only"]
        OCR["OCR Service\nPaddleOCR + OpenCV"]
        TPL["Template Service\npython-docx / DOCX XML"]
        DB[("SQLite\njobs, fields, audit")]
        DS[("Recycling Dataset\nreviewed labels + metadata")]
        OUT["Generated .docx output"]
    end

    UI <--> API
    API --> OCR
    API --> TPL
    API --> DB
    API --> DS
    TPL --> OUT
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
    OCR-->>App: Field predictions with confidence
    User->>App: Review and correct values
    App->>DB: Save reviewed job and audit data
    App->>DS: Save training candidate metadata
    App->>Docx: Fill approved values
    Docx-->>User: New generated .docx
```

## ขอบเขตข้อมูลที่ต้องระวัง

- `data/`, `output/` และ `docs/example/` เป็นข้อมูล local/runtime หรือไฟล์ตัวอย่าง
  ที่อาจมีข้อมูลอ่อนไหว จึงไม่ควร commit ขึ้น remote
- ค่าที่ใช้ train ต่อควรมาจาก human-reviewed label เท่านั้น
- ห้ามนำ recycling data เข้า frozen test set แบบอัตโนมัติ

