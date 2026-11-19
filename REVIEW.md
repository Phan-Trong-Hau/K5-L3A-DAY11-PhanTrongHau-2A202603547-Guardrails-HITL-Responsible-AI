# Đối chiếu bài nộp ngày 19/11/2026

Đối chiếu CHECKPOINTS.md, RUBRIC.md, SUBMISSION.md, RULES.md và README.md.
Đây là checklist kỹ thuật; báo cáo chấm vẫn được sinh bằng scripts/grade.py.

| Mục | Kết quả / bằng chứng |
|---|---|
| CP1: import và smoke | Pass trong bộ smoke/public; dependencies đã cài trong .venv |
| CP2: input injection/topic/Unicode, output secret/PII | Có implementation và public tests pass |
| CP3: thứ tự plugin, sliding window theo user, audit/metrics, egress | Có implementation và tests pass; audit/metrics hiện có |
| CP3: artifact/schema | results.json hợp lệ; safe 0/6 bị chặn; attack 8/8; edge 3/3; spam 5/15 bị chặn |
| CP4: ≥5 prompt và hai target | Có 5 unsafe + 5 guards trong attack_results.json; provider/model được khai là liquid/lfm3-1.7b |
| CP4: leak Red trên model mặc định | **Chưa chứng minh**: artifact hiện dùng Liquid trực tiếp; rubric yêu cầu gpt-4o-mini hoặc gemini-3.5-flash |
| CP5: grader và báo cáo tự sinh | Đã chạy scripts/grade.py; schema/packaging/public tests pass; technical_failure=false |
| Demo/history | Đã bổ sung src/demo_app.py, src/demo_history.py, demo/README.md, scripts/verify_demo.py và 8 test offline |
| B1 | Replay lại 2 prompt từng leak, mỗi prompt 2 lượt: 4/4 leak, 0 lỗi; outputs/bonus_b1_replay.json. Chờ coach/grader xác nhận; không tự cấp +5 |
| B2 | Replay cả 5 prompt: 0/5 leak, 0 lỗi; outputs/bonus_b2_replay.json. Chưa đủ điều kiện B2 |
| Secret / history | .env không được track, .env và .demo_history/ được ignore; history che nội dung trước khi lưu |
| Danh tính / repo | README có họ tên và MSSV; tên thư mục theo mẫu K5-L3A trong SUBMISSION.md |
| Push, LMS, deadline | Chưa xác minh / chưa thực hiện trong lần rà soát này |

## Việc còn lại ảnh hưởng điểm

1. Cần chạy CP3 với Blue OpenRouter liquid/lfm-3-1.7b:free và CP4 với Red
   OpenAI gpt-4o-mini hoặc Gemini gemini-3.5-flash để có bằng chứng đúng cấu hình
   rubric. Cấu hình Liquid hiện được README công khai nhưng chưa có xác nhận
   coach cho phép thay thế. Không đổi metadata của artifact hiện tại để giả đúng model.
2. Chọn B1 để đề nghị coach/grader replay; B2 chưa có leak. Local replay không thay
   thế việc xác nhận điểm bởi người chấm. Không cộng cả B1 và B2.
3. Học viên cần đọc/giải thích code, tự xem và điều chỉnh prompt có chủ đích theo
   RULES.md; sau đó push và nộp link LMS đúng hạn.

Các TODO còn trong LLM-as-Judge là phần optional, không phải thiếu hạng mục bắt buộc.
NeMo cho Red Advance vẫn giữ nguyên. Demo/history là phần bổ sung, rubric không bắt buộc.
RULES/README còn ví dụ Khóa 4 và quy định deadline khác SUBMISSION; giữ nguyên tài liệu
đề, tên repo dùng mẫu Khóa 5 của SUBMISSION; hạn cụ thể cần theo thông báo coach.

## Lệnh kiểm tra

```bash
.venv/bin/python -m pytest tests/smoke tests/public tests/demo -q
.venv/bin/python scripts/verify_demo.py
.venv/bin/python scripts/grade.py --submission-dir . --out outputs/grade_report.json
```

Bộ kiểm tra smoke/public/demo: **67 passed** (59 có sẵn + 8 demo/history).
Hướng dẫn demo và replay: [demo/README.md](demo/README.md).
