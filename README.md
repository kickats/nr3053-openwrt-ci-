# OpenWrt NR3053: Standard / Extended

Thấy em router này trên VOZ mà chưa có bản Openwrt public - Tạo bản này trong lúc rảnh rỗi cho mọi người nghịch

Thư mục Backup có : Uboot để nạp lần đầu và các file backup phân vùng đề phòng trong trường hợp các bạn nghịch đứt tay

Repo này có 2 lựa chọn build kèm kho kmod ngoài hoặc không cần . Mọi người có thể sửa seed để thêm hay chỉnh sửa gói mà mình thích

OpenWrt nên Ram trống rất nhiều ~ 360M - Ổ cứng trống ~168M . Đã cài sẵn Wireguard , PBR , CloudFlare , SQM .....
Hỗ trợ Hardware , Software offloading , wifi 802.11 r....

| Nhóm | Số gói |
|---|---:|
| Wi-Fi cfg80211/mac80211/mt76/mt7915e/MT7981 | 6 |
| Firewall/nft/flowtable/iptables | 17 |
| PPP/tun/WireGuard | 8 |
| SQM/CAKE/IFB/scheduler/BBR | 4 |
| USB core/NLS | 3 |
| Crypto | 28 |
| GPIO/thermal/MMC và phụ thuộc | 8 |

