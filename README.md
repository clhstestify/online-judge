# QTOJ: Quang Tri Online Judge

## Tổng quan
- Trang chủ: [https://quangtrioj.edu.vn](https://quangtrioj.edu.vn)
- Nền tảng được xây dựng trên [LQDOJ](https://lqdoj.edu.vn/) và mở rộng cho cả các kỳ thi lập trình lẫn kỳ thi trắc nghiệm chuẩn THPTQG 2025.

## Điểm nổi bật
### Nền tảng thi lập trình
- Trình chấm tự động hỗ trợ nhiều ngôn ngữ: Assembly (x64), AWK, Brainfxck, C, C++03/11/14/17/20, Java 8/11, Scratch, Pascal, Perl, Python 2/3, PyPy 2/3.
- Tích hợp phát hiện đạo văn thông qua [Stanford MOSS](https://theory.stanford.edu/~aiken/moss/).
- Bảng xếp hạng thời gian thực, sự kiện trực tiếp bằng WebSocket và hệ thống newsletter để tương tác với thí sinh.

### Thể thức trắc nghiệm THPTQG 2025
- Contest format **THPTQG Exam** chấm điểm theo thang 0–10 và hiển thị kết quả chi tiết theo từng phần trên bảng xếp hạng.
- Giao diện thi chuyên biệt gồm trình xem đề PDF song song với phiếu trả lời ba phần (trắc nghiệm 4 lựa chọn, Đúng/Sai và trả lời ngắn).
- Phiếu trả lời hỗ trợ lưu tạm, nộp bài một lần hoặc nhiều lần, tự động chuẩn hóa câu trả lời ngắn và thống kê số ý đúng trong phần Đúng/Sai.
- Ban tổ chức có thể thêm đáp án thủ công hoặc nhập từ file DOCX/PDF, hệ thống sẽ tạo câu hỏi, đáp án và cập nhật lại cơ cấu điểm.

## Thi trắc nghiệm THPTQG 2025
### Cấu trúc đề & chấm điểm
- **Phần I – Trắc nghiệm 4 lựa chọn:** mặc định 40 câu, mỗi câu đúng được 0,25 điểm.
- **Phần II – Đúng/Sai:** mỗi câu có 4 ý; 1 ý đúng được 0,1 điểm, 2 ý đúng được 0,25 điểm, 3 ý đúng được 0,5 điểm và 4 ý đúng được trọn 1 điểm.
- **Phần III – Trả lời ngắn:** điểm mỗi câu phụ thuộc môn thi (0,5 điểm cho Toán, 0,25 điểm cho các môn khác). Hệ thống bỏ khoảng trắng và không phân biệt hoa thường khi so đáp án.
- Điểm tổng cộng được quy đổi về thang 0–10 và hiển thị cùng tổng số ý đúng/tổng ý trên bảng xếp hạng.

### Quy trình dành cho thí sinh
1. Tham gia contest có format **THPTQG Exam** và mở giao diện thi.
2. Xem đề trực tiếp bằng PDF được nhúng bên trái, điền đáp án vào ba phần của phiếu trả lời bên phải.
3. Nhấn **Save answers** để lưu tạm thời hoặc **Submit and view ranking** khi đã hoàn thành. Thí sinh có thể trở lại cập nhật bài nếu contest vẫn còn thời gian.
4. Sau khi nộp, bảng xếp hạng hiển thị điểm từng phần và điểm quy đổi.

### Quy trình dành cho ban tổ chức
1. Tạo contest và chọn format `THPTQG` trong phần cấu hình.
2. Trong admin panel, truy cập **Exam papers** để tạo phiếu thi: chọn contest, môn thi (quy định điểm phần III), số câu mỗi phần và tải lên file PDF đề thi nếu có.
3. Nhập đáp án bằng một trong hai cách:
   - **Thủ công:** điền đáp án từng phần theo định dạng được hướng dẫn ngay trên form (ví dụ `1. A` cho Phần I, `1. Đ S S Đ` cho Phần II, `1. 12345` cho Phần III).
   - **Tải lên file:** gửi file `.docx` hoặc `.pdf` theo định dạng chuẩn phía dưới; hệ thống sẽ đọc và đồng bộ câu hỏi, đáp án, điểm số.
4. Lưu bản ghi để hệ thống tự sinh câu hỏi, đồng bộ lại số lượng câu hỏi từng phần và xuất hiện phiếu trả lời cho thí sinh.

### Định dạng file đáp án tải lên
Sử dụng các thẻ phần `[PART1]`, `[PART2]`, `[PART3]` (hoặc `[PHẦN 1]`…), mỗi dòng tương ứng một câu. Ví dụ:

```
[PART1]
1. A
2. C

[PART2]
1. Đ S S Đ
2. d d s s

[PART3]
1. 12345
2. AB-CD
```

- Có thể viết số câu dưới dạng `1.`, `Câu 1:`… Hệ thống chấp nhận các ký hiệu Đ/D/T/True (Đúng) và S/F/False (Sai) cho phần II.
- Phần III cho phép chữ hoa/thường hoặc có khoảng trắng, hệ thống sẽ tự chuẩn hóa trước khi chấm.

## Cài đặt nhanh
Phần lớn các bước giống hướng dẫn của DMOJ: <https://docs.dmoj.ca/#/site/installation>. Khác biệt chính là thay repo `https://github.com/DMOJ/site.git` bằng `https://github.com/TLEJudge/online-judge.git`. Sau khi tạo môi trường Python, cài đặt phụ thuộc bằng `pip install -r requirements.txt` (bao gồm `python-docx` và `pdfminer.six` phục vụ nhập đáp án trắc nghiệm).

### Một số lỗi thường gặp
1. Thiếu `local_settings.py`: sao chép file mẫu để vượt qua bước kiểm tra.
2. Chưa cấu hình đường dẫn thư mục bài tập trong `local_settings.py`.
3. Chưa cấu hình thư mục static trong `local_settings.py` (`STATIC_FILES`).
4. Thiếu file cấu hình cho judge: dùng `python dmojauto-conf` để sinh mẫu, tham khảo thêm tại <https://github.com/DMOJ/docs/tree/master/sample_files>.

## Vận hành cục bộ
1. Kích hoạt virtualenv:
   ```bash
   source dmojsite/bin/activate
   ```
2. Chạy server:
   ```bash
   python manage.py runserver 0.0.0.0:80
   ```
3. Mở cầu nối (bridge) ở một terminal khác:
   ```bash
   python manage.py runbridged
   ```
4. Khởi chạy judge (có thể chạy nhiều judge trên các terminal riêng):
   ```bash
   dmoj 0.0.0.0 -p 9999 -c <path-to-config.yml>
   ```
5. (Tuỳ chọn) Worker Celery cho các tác vụ nền:
   ```bash
   celery -A dmoj_celery worker
   ```
6. (Tuỳ chọn) Máy chủ sự kiện trực tuyến:
   ```bash
   node websocket/daemon.js
   ```

## Triển khai & bảo trì
1. **Cập nhật dịch thuật**
   ```bash
   python manage.py makemessages
   # chỉnh sửa locale/vi/LC_MESSAGES/django.po
   python manage.py compilemessages
   python manage.py compilejsi18n
   ```
2. **Biên dịch giao diện (SASS/CSS)**
   ```bash
   ./make_style && python manage.py collectstatic
   ```
   Làm mới trình duyệt (Ctrl + F5) nếu chưa thấy thay đổi giao diện.
