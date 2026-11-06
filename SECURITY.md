# Mô hình bảo mật khi repo public

## Vì sao có thể công khai

- Repo chỉ chứa source overlay/config và **public key**, không khóa ký,
  backup Factory/calibration, MAC/SSID/serial riêng, mật khẩu hoặc tài khoản
  quản trị. DTS đọc calibration từ Factory của từng thiết bị, không nhúng
  dữ liệu Factory. Mã nguồn công khai giúp review nhưng không tự chứng minh an toàn.
- Firmware công khai không được nhúng mật khẩu/SSH key/token; người dùng
  phải đặt mật khẩu quản trị và Wi-Fi riêng sau flash, đặc biệt khi không giữ
  cấu hình. Không nối WAN trước khi cấu hình bảo mật.
- Fork có thể build bản riêng nhưng không có environment secret của repo
  gốc. PR từ fork không được cấp khóa; không dùng `pull_request_target`,
  PR/push trigger hoặc `secrets: inherit`. Standard không nhận secret.
- Khóa chỉ đặt trong environment `kmod-signing`, restrict main và required
  reviewers nếu hỗ trợ. Manual dispatch vẫn cần quyền write; chỉ người
  tin cậy mới được quyền này. Branch protection/review là bắt buộc vận hành,
  file YAML không tự bật được các cài đặt GitHub đó.
- Actions ghim SHA, checkout không giữ credential; mặc định `contents:read`.
  Chỉ job deploy có `pages:write`, `id-token:write` và environment
  `github-pages`; không cấp `contents:write` hoặc token cá nhân.
- Public key/SHA256 công khai giúp đối chiếu ngoài băng; APK/index được ký,
  không bỏ xác minh trên router. Pages chỉ là phân phối, không phải nguồn
  chân lý về key. ABI-lock ngăn vô tình trộn kernel nhưng không ngăn mã độc.

## Rủi ro còn lại và xử lý

- Mất khóa hoặc bị chiếm tài khoản maintainer/runner có thể phát hành APK
  độc hại. Source build có thể thực thi mã tùy ý trong cùng job ký; dù chỉ
  đưa secret ở bước cuối, runner không phải ranh giới cô lập khỏi dependency
  độc hại đã chạy trước đó. Review source/tag/feeds/scripts, hạn chế write,
  bật MFA và environment approval; không ký build không tin cậy.
- Tag OpenWrt mặc định được kiểm với commit nền, feeds ghim commit của tag.
  Tag mới chỉ kiểm định dạng, chưa nằm trong allowlist commit: cần review
  SHA upstream trước khi phê duyệt environment. Pin không loại trừ lỗ hổng
  trong dependency hay tài khoản upstream; cập nhật có kiểm soát.
- Cache có thể bị đầu độc nếu cho người không tin cậy ghi workflow; chỉ
  dispatch main, bảo vệ branch, xóa cache khi nghi ngờ compromise.
- Nếu nghi lộ khóa: dừng deploy/ký, xóa Secret cũ, điều tra và thông báo.
  Tạo cặp khóa mới, review/commit public key, cập nhật environment Secret,
  phân phối key mới qua kênh tin cậy và xóa key cũ khỏi router (hoặc flash
  firmware tin cậy). Không chỉ thay key trên Pages rồi yêu cầu tin tự động.
- Pages công khai metadata package/kernel và thời điểm build; mọi người
  tải/fork được, không có cơ chế giữ firmware bí mật. Artifact/log Actions
  public cũng có thể đọc được: không đưa thông tin thiết bị vào build.
- Pages chỉ giữ deploy mới nhất; mất URL cũ gây lỗi tải chứ không được
  chữa bằng force-depends. Lưu artifact/mirror theo ABI nếu cần lâu dài.
- `.gitignore` loại logs, generated build/feed và private-key patterns;
  gitignore không xóa dữ liệu đã commit. Quét staged files **và lịch sử**
  trước lần push đầu và mỗi lần thay overlay. Không publish nếu phát hiện
  bí mật; revoke/rotate trước, rồi làm sạch lịch sử khi cần.

Không gửi bí mật qua issue công khai. Nếu phát hiện khóa bị lộ, ưu tiên
thu hồi khóa và thông báo maintainer qua kênh riêng đã được xác minh.
