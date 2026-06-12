# PaddleOCR Models

Place trained PaddleOCR inference models here.

Suggested recognition model path:

```text
models/paddleocr/rec/latest/
```

Point the app at that folder with:

```powershell
$env:RAPE_OCR_REC_MODEL_DIR = "models\paddleocr\rec\latest"
```

or set `text_recognition_model_dir` in `configs/ocr_models.json`.
