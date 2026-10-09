# ScanXMLBHYT

Tool Python quét lỗi hồ sơ XML BHYT (chuẩn **QĐ 3176**, kế thừa **QĐ 4750 / QĐ 130**) trước khi gửi lên cổng [Giám định BHYT](https://gdbhyt.baohiemxahoi.gov.vn/).

## Cài đặt

```bash
cd ScanXMLBHYT
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Cách dùng

```bash
# Quét thư mục mẫu
python -m scan_xml_bhyt XML_Standard

# Quét một file
python -m scan_xml_bhyt path/to/hoso.xml

# Chỉ định Excel rule + thư mục báo cáo
python -m scan_xml_bhyt XML_Standard \
  --excel "Validate CTN QĐ 3176_20250906.xlsx" \
  --out reports \
  --rebuild-schema
```

## Kết quả

- Console: `[OK]` / `[FAIL]` từng file
- `reports/scan_YYYYMMDD_HHMMSS.xlsx` — báo cáo Excel (sheet `Tong_hop` + `Chi_tiet`)
- Tuỳ chọn: `--csv`, `--json`
- File có **error** được copy vào `XML_Error/` (tắt bằng `--no-copy-error`)

Exit code: `0` nếu không có error, `1` nếu có error, `2` lỗi cấu hình.

## Phạm vi kiểm tra (v1)

| Nhóm | Nội dung |
|------|----------|
| Envelope | `GIAMDINHHS`, `MACSKCB`, `SOLUONGHOSO`, decode base64 `NOIDUNGFILE` |
| Schema | Bắt buộc / kiểu / max length theo Excel 3176 |
| Điều kiện Excel | Parse rule cột Bắt buộc: `khi FIELD=…`, `trừ nhóm…`, `not null`, `có dữ liệu`, … |
| Format | Ngày 8/12 ký tự, `GIOI_TINH`, `SO_CCCD`, `MA_BAC_SI` (GPHN), `TT_THAU` |
| Logic XML1 | `MA_BENH_KT`≤12, tiền `T_BHTT` |
| Logic XML2/3 | Y lệnh, thầu, người thực hiện, DV/VTYT+tên, `SO_LUONG*DON_GIA≈THANH_TIEN` |
| Logic XML4 | `NGAY_KQ`, `TEN_CHI_SO`, `KET_LUAN` khi `MA_NHOM=2` |
| Thời gian | Ngày lịch hợp lệ; `VAO≤NT≤RA`; thẻ BHYT; `YL≤TH_YL≤KQ≤now`; YL/TH trong đợt XML1; `TU≤DEN` + số ngày; hẹn KL ≥ ra viện |
| Liên bảng | `MA_LK` khớp; thiếu XML7/13/14 |

**Chưa có:** verify chữ ký số đầy đủ, tra cứu danh mục `DM_*` (SQL).

## Cấu trúc

```
scan_xml_bhyt/     # mã nguồn tool
rules/             # schema_3176.json (cache từ Excel)
XML_Standard/      # XML mẫu / đầu vào
XML_Error/         # XML có lỗi (sau khi quét)
reports/           # báo cáo CSV
```
