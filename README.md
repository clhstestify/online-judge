# TLEOJ: TLE Online Judge

## Tổng quan
- Trang chủ: [https://tleoj.edu.vn](https://tleoj.edu.vn)
- Nền tảng dựa trên mã nguồn mở DMOJ/LQDOJ và được mở rộng để phục vụ đồng thời các kỳ thi lập trình lẫn thể thức trắc nghiệm THPTQG 2025.

## Tính năng nổi bật
### Nền tảng thi lập trình
- Trình chấm tự động hỗ trợ nhiều ngôn ngữ: Assembly (x64), AWK, Brainfxck, C, C++03/11/14/17/20, Java 8/11, Scratch, Pascal, Perl, Python 2/3, PyPy 2/3.
- Tích hợp phát hiện đạo văn thông qua [Stanford MOSS](https://theory.stanford.edu/~aiken/moss/).
- Hệ thống bảng xếp hạng thời gian thực, event trực tiếp bằng WebSocket và newsletter tương tác với thí sinh.

### Thể thức trắc nghiệm THPTQG 2025
- Contest format **THPTQG Exam** chấm điểm theo thang 0–10 dựa trên tổng điểm tối đa của từng phần và hiển thị chi tiết số điểm/ý đúng trên bảng xếp hạng.
- Giao diện thi chuyên biệt hiển thị đề dưới dạng PDF cùng phiếu trả lời 3 phần: trắc nghiệm bốn lựa chọn, Đúng/Sai và trả lời ngắn.
- Mỗi thí sinh được gán ngẫu nhiên mã đề khi vào phòng thi và chỉ có thể nộp một lần; sau khi nộp bài, phiếu trả lời chuyển về chế độ chỉ đọc.
- Chế độ giám sát bắt buộc full screen, ghi nhận việc chuyển tab/ẩn cửa sổ, cảnh cáo 4 lần và khóa bài ở lần vi phạm thứ 5.

## Luồng thi THPTQG 2025
### Cấu trúc đề & chấm điểm
- **Phần I – Trắc nghiệm 4 lựa chọn:** mặc định 40 câu, mỗi câu đúng được 0,25 điểm.
- **Phần II – Đúng/Sai:** mỗi câu có 4 ý; 1 ý đúng được 0,1 điểm, 2 ý đúng được 0,25 điểm, 3 ý đúng được 0,5 điểm và đủ 4 ý đúng được 1 điểm.
- **Phần III – Trả lời ngắn:** điểm tối đa phụ thuộc môn (0,5 điểm đối với Toán, 0,25 điểm đối với môn khác).
- Hệ thống tự quy đổi tổng điểm về thang 10, đồng thời hiển thị tổng số ý đúng/tổng ý trên bảng xếp hạng.

### Trải nghiệm của thí sinh
1. Tham gia contest có format **THPTQG** để được gán mã đề ngẫu nhiên và truy cập giao diện thi.
2. Đề thi PDF hiển thị song song với phiếu trả lời; thí sinh có thể lưu tạm (**Save answers**) hoặc nộp bài (**Submit and view ranking**).
3. Hệ thống yêu cầu giữ chế độ toàn màn hình, cảnh báo ngay khi chuyển tab/ẩn cửa sổ và khóa bài khi vượt quá 5 vi phạm.
4. Sau khi chọn **Submit**, bài làm bị khóa (`exam_finalized_at`) và chỉ cho phép xem lại kết quả.

### Bảng xếp hạng và báo cáo
- Mỗi phần thi xuất hiện như một cột ảo, hiển thị điểm đạt được, số ý đúng và tổng số câu/ý.
- Khi kỳ thi kết thúc, bảng xếp hạng thêm cột mã đề để tiện đối soát giấy thi của từng thí sinh.
- Admin có thể xem mã đề, số lần vi phạm và trạng thái khóa/nộp bài của từng thí sinh trong trang quản trị contest.

## Quản trị & soạn đề thi
1. Vào admin panel, tạo **Exam paper** cho contest: đặt mã đề, môn thi (để xác định điểm phần III), số câu từng phần và tùy chọn tải PDF đề thi.
2. Nhập đáp án bằng một trong hai cách:
   - **Thủ công:** điền đáp án vào ba vùng nhập, hệ thống tự đồng bộ câu hỏi theo định dạng THPTQG.
   - **Tải file DOCX/PDF:** sử dụng mẫu có các thẻ `[PART1]`, `[PART2]`, `[PART3]`; công cụ parser sẽ đọc và cập nhật toàn bộ câu hỏi/đáp án.
3. Sau khi lưu, hệ thống sinh dữ liệu câu hỏi, thiết lập lại số câu mỗi phần và phục vụ phiếu trả lời cho thí sinh.
4. Từ trang contest admin, có thể gán lại mã đề cụ thể cho thí sinh, xem nhật ký vi phạm hoặc khóa/mở khóa quyền làm bài nếu cần.

## Định dạng file đáp án mẫu
```
[PART1]
1. A
2. C

[PART2]
1. Đ S S Đ
2. D D S S

[PART3]
1. 12345
2. AB-CD
```
- Hỗ trợ tiền tố như `Câu 1:`, `Question 1 -`, v.v.; ký tự Đ/D/T/True cho Đúng và S/F/False cho Sai.
- Phần III tự loại bỏ khoảng trắng và không phân biệt hoa thường khi so đáp án.

## Cài đặt nhanh
Làm theo hướng dẫn cài đặt DMOJ tại <https://docs.dmoj.ca/#/site/installation> và thay repository thành `https://github.com/TLEJudge/online-judge.git`. Sau khi tạo môi trường Python:
```bash
pip install -r requirements.txt
```
Các gói bổ sung `python-docx` và `pdfminer.six` được sử dụng để nhập đáp án từ file Word/PDF.

## Vận hành cục bộ
1. Kích hoạt virtualenv:
   ```bash
   source dmojsite/bin/activate
   ```
2. Chạy server:
   ```bash
   python manage.py runserver 0.0.0.0:80
   ```
3. Mở cầu nối (bridge) ở terminal khác:
   ```bash
   python manage.py runbridged
   ```
4. Khởi chạy judge (có thể chạy nhiều judge ở các terminal riêng):
   ```bash
   dmoj 0.0.0.0 -p 9999 -c <path-to-config.yml>
   ```
5. (Tuỳ chọn) Worker Celery xử lý tác vụ nền:
   ```bash
   celery -A dmoj_celery worker
   ```
6. (Tuỳ chọn) Máy chủ sự kiện trực tuyến:
   ```bash
   node websocket/daemon.js
   ```

## Bảo trì
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
