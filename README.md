# OpenWrt NR3053: Standard / Extended

Thấy em router này trên VOZ mà chưa có bản Openwrt public - Tạo bản này trong lúc rảnh rỗi cho mọi người nghịch

Thư mục Backup có : Uboot để nạp lần đầu và các file backup phân vùng đề phòng trong trường hợp các bạn nghịch đứt tay

Repo này có 2 lựa chọn build kèm kho kmod ngoài hoặc không cần . Mọi người có thể sửa seed để thêm hay chỉnh sửa gói mà mình thích

OpenWrt nên Ram, và ổ cứng trống nhiều - xem ảnh dưới nhé

<img width="3816" height="2099" alt="image" src="https://github.com/user-attachments/assets/f8a70225-7629-40d9-94c4-1f92d30399ae" />

<img width="3782" height="2045" alt="image" src="https://github.com/user-attachments/assets/f4250747-4fd2-4055-8252-a5c1685edddc" />

### 1. Tiện ích mở rộng

| Tiện ích | Gói chính | Tác dụng và ảnh hưởng CPU |
| --- | --- | --- |
| **WireGuard** | `wireguard-tools`, `kmod-wireguard`, `luci-proto-wireguard` | VPN mã hóa giữa router và máy/địa điểm khác. Khi có traffic VPN, CPU phải xử lý mã hóa; không nên kỳ vọng toàn bộ đường hầm được PPE offload |
| **PBR** | `pbr`, `luci-app-pbr` | Định tuyến theo chính sách: chọn WAN/VPN cho từng thiết bị, địa chỉ hoặc loại traffic. Cần cấu hình rule; không tự tăng tốc mạng |
| **Cloudflare Tunnel** | `cloudflared`, `luci-app-cloudflared` | Công bố dịch vụ nội bộ qua tunnel tới Cloudflare. Đây **không phải WARP VPN hay DNS Cloudflare**. Khi tunnel hoạt động sẽ dùng RAM/CPU và mã hóa |
| **SQM** | `sqm-scripts`, `luci-app-sqm`, `kmod-sched-cake` | Quản lý hàng đợi, giảm bufferbloat và độ trễ khi mạng đầy tải. Khi bật, thường đánh đổi throughput/CPU; flow offload có thể đi vòng qua shaping nên cần cấu hình phối hợp |
| **File Manager** | `luci-app-filemanager` | Quản lý file qua LuCI. Chủ yếu tạo tải khi đang sử dụng |
| **BBR** | `kmod-tcp-bbr` | Cung cấp thuật toán kiểm soát nghẽn TCP BBR. Cài module **không đồng nghĩa đã chọn BBR**; chủ yếu liên quan TCP kết thúc trên router |
| **Công cụ mạng** | `ip-full`, `iw`, `tc-tiny`, nhóm `iptables-nft` | Quản lý interface, WiFi, hàng đợi và hỗ trợ các công cụ dùng iptables trên nền nftables |


### 2. Các gói đã thêm hoặc thay thế

| Gói | Tác dụng | Liên quan hiệu năng |
| --- | --- | --- |
| `bridger` | Hỗ trợ tăng tốc luồng qua bridge, như WiFi ↔ LAN cùng subnet, khi phần cứng/driver hỗ trợ | Có ích cho **traffic chuyển tiếp**, không tăng tốc iperf3 kết thúc trên router |
| `ethtool` | Kiểm tra link và bật các offload Ethernet được driver hỗ trợ | Giảm một phần công xử lý Ethernet |
| `htop` | Xem tải từng CPU, tiến trình và RAM | Chỉ theo dõi, không tăng tốc |
| `iperf3` | Đo throughput, nhiều luồng, hai chiều | Công cụ đo; tự tạo tải CPU khi chạy |
| `openssl-util` | Tạo chứng chỉ/khóa để `uhttpd` phục vụ HTTPS | Sửa HTTPS, không tăng tốc mạng |
| `dnsmasq-full` thay `dnsmasq` | Thêm tính năng DNS/DHCP như DNSSEC, nftset… | Không trực tiếp tăng tốc iperf3 |
| `wpad-openssl` thay `wpad-basic-mbedtls` | Bộ xác thực WiFi đầy đủ hơn, dùng OpenSSL | Không có bằng chứng việc đổi này tự làm throughput cao hơn |
| `libustream-openssl` thay `libustream-mbedtls` | Cung cấp TLS cho các dịch vụ sử dụng libustream | Phục vụ HTTPS/TLS |
| `kmod-nf-nathelper` | Helper cho FTP/TFTP qua NAT | Không tăng tốc iperf3 |
| `kmod-nf-nathelper-extra` | Thêm helper cho SIP, H.323, PPTP, IRC… | Không cần cho nhu cầu đo hiện tại; vẫn đang giữ |
| `luci-theme-glass` | Giao diện Glass cho LuCI | Hiệu ứng chủ yếu chạy trên trình duyệt, không phải tối ưu CPU router |

### 3. Tăng tốc phần cứng và tuning đã áp dụng

| Thay đổi | Giá trị hiện đã lưu | Tác dụng |
| --- | --- | --- |
| **WED** | Driver mt7915e nạp với `wed_enable=Y` | Hỗ trợ đường tăng tốc WiFi phối hợp với WO/PPE |
| **Software flow offload** | `flow_offloading=1` | Rút ngắn xử lý các luồng chuyển tiếp đủ điều kiện |
| **Hardware flow offload** | `flow_offloading_hw=1` | Cho phép đẩy luồng chuyển tiếp đủ điều kiện xuống PPE |
| **irqbalance** | Dịch vụ bật | Phân bố các IRQ có thể di chuyển giữa CPU; **gói vốn đã có**, trước đó mặc định tắt |
| **Packet steering** | `network.globals.packet_steering=2` | Chế độ chuẩn OpenWrt cho phép RPS dùng mọi CPU; trên NR3053 đã kiểm tra mask **`3`** |
| **RFS từng RX queue** | `steering_flows=4096` | Cấp bảng theo dõi luồng cho RFS; đặc biệt liên quan ứng dụng nhận dữ liệu trên router |
| **Bảng RFS tổng** | `rps_sock_flow_entries=8192` | `4096 × 2 CPU`; hỗ trợ RFS, không tự bảo đảm cân bằng CPU |
| **Ethernet offload** | Checksum, scatter-gather, GSO/TSO được yêu cầu bật và đã kiểm tra trên driver hiện tại | Giảm công tính checksum, sao chép và phân đoạn dữ liệu Ethernet |

