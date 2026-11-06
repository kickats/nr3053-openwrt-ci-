# OpenWrt NR3053: Standard / Extended

Repo overlay công khai cho **OpenWrt v25.12.6 / kernel 6.12**, không chứa
source OpenWrt, firmware binary, backup Factory, calibration hay khóa riêng.
Giữ NAND Dosilicon, layout flash và aliases `viettel,nr3053` / `sdmc,nr3053`.
Không có script truy cập/flash router; không xuất factory.bin.
Hiện chỉ chuẩn bị cục bộ, chưa push hoặc chạy GitHub Actions/Pages.

## Hai bản build

| Workflow thủ công | Kết quả | Secret |
|---|---|---|
| A - Standard firmware | Firmware cơ bản, không kho kmod | Không |
| B - Extended firmware and signed Pages feed | Firmware + seed kmod mở rộng + kho ký trên Pages | Environment `kmod-signing` |

Hai workflow gọi `.github/workflows/build-core.yml` (`workflow_call`).
Input tag mặc định `v25.12.6`; core giữ `build_kmod_feed` boolean nội bộ.
Standard dùng `nr3053.seed.config`: bỏ Tailscale, thêm cloudflared,
luci-app-cloudflared, pbr, luci-app-pbr; chưa thêm usteer/wpad đầy đủ.
Extended thêm `nr3053.kmods.config` trước defconfig và nhúng public key.
Chỉ cho build từ `main`; không chạy khi push hoặc pull request.

## Thiết lập repo public

1. Tạo repo **public, trống**. Trong thư mục clone cục bộ:

   ```sh
   cd /path/to/nr3053-openwrt-ci
   git status --short
   git remote add origin https://github.com/YOUR-ACCOUNT/YOUR-REPO.git
   git push -u origin main
   ```

   Không ghi token vào URL/commit. Bản chuẩn bị đã có commit cục bộ.
2. Bật ruleset/branch protection cho `main`: required reviews, chặn force
   push/delete và hạn chế người có quyền ghi. Review đặc biệt workflows,
   scripts, seed, overlay và public key.
3. Tạo environment **`kmod-signing`**, chỉ cho nhánh `main`; thêm required
   reviewers và prevent self-review nếu gói/tài khoản hỗ trợ. Đặt
   **environment secret `KMOD_SIGNING_KEY`** chứa PEM khóa riêng tương ứng
   với `keys/nr3053-kmods.pub`. Không đặt khóa này ở repository secret.
   Fork phải tự tạo khóa riêng; không bao giờ chia sẻ khóa chủ repo.
4. Bật **Settings → Pages → Source: GitHub Actions**. Với environment
   **`github-pages`**, giới hạn deployment branch `main`, thêm reviewers
   nếu cần. Environment `standard-build` không chứa secret.
5. Chạy **Actions → A / B → Run workflow**, giữ tag mặc định lần đầu.
   B cần duyệt environment trước khi job chạy. Người chỉ có read access
   không được dispatch trên repo gốc; người có write access là trust boundary.
6. Tải artifact firmware và kiểm tra `sha256sum -c sha256sums`.
   Gồm sysupgrade/initramfs, `.config`, manifest/metadata/FIT và build info;
   không factory.bin. B còn có artifact kho kmod đầy đủ để lưu trữ riêng.

Khóa riêng lưu ngoài repo với quyền 0600; sao lưu an toàn, không gửi vào
chat/log/artifact. Workflow chỉ đưa khóa vào bước ký sau build, đối chiếu
public key, xóa file tạm kể cả lỗi. Xem [SECURITY.md](SECURITY.md) trước khi
bật ký và xuất bản.

## Kho kmod và ABI

Đo từ bản build nền: **74 kmod / 2.146.797 byte APK** (~2,05 MiB),
tất cả đã có trong firmware, 0 gói chỉ build rời; 109 file `.ko`.
Kho đã ký: 2.154.593 byte APK; cả thư mục archive khoảng 2,41 MiB.

| Nhóm | Số gói |
|---|---:|
| Wi-Fi cfg80211/mac80211/mt76/mt7915e/MT7981 | 6 |
| Firewall/nft/flowtable/iptables | 17 |
| PPP/tun/WireGuard | 8 |
| SQM/CAKE/IFB/scheduler/BBR | 4 |
| USB core/NLS | 3 |
| Crypto | 28 |
| GPIO/thermal/MMC và phụ thuộc | 8 |

Seed Extended có 17 lựa chọn USB/storage/Ethernet/ext4/vfat/exfat/NLS
dạng `=m`; resolve thành **102 kmod = 74 trong firmware + 28 rời/phụ thuộc**.
Chưa compile 28 gói mới cục bộ nên chưa có dung lượng thực đo; CI báo sau build.
USB vật lý/DTS chưa được xác nhận; driver không tự kích hoạt phần cứng.
WED đã thuộc kernel/mt76, không có `kmod-wed`; `mt7981-wo-firmware`
là firmware blob không phải kmod.

Kernel package nền:
`6.12.112~9c48f85431763d0db2624a4a60318bdb-r1`.
Extended dự kiến ABI `6d547a8b8c6af9cab628731ed59bd18c` với tag/feeds hiện tại.
**Không cài feed Extended lên firmware nền.** Phải build firmware và modules
cùng lượt, không chỉ đối chiếu `uname -r`. CI kiểm tra manifest, `.vermagic`,
dependency từng APK, ELF vermagic, closure và chữ ký; sai thì dừng.

## Pages và cách thêm kho

Pages chỉ xuất APK đã ký, `packages.adb` đã ký, public key và `index.html`
hướng dẫn; không đưa config/log/report/firmware lên Pages.
Mỗi lượt chỉ có một thư mục
`feeds/KERNEL_VERSION/ABI_HASH/RUN_ID-ATTEMPT/`, không trộn ABI.
Build core kiểm chữ ký bằng APK; bước chuẩn bị Pages kiểm checksum, key,
ABI và allowlist từ artifact của chính lượt đó. Hash không thay chữ ký.

**Mỗi deploy thay toàn bộ site**, không lưu lịch sử Pages. URL cũ không
còn sau deploy mới; lưu artifact nếu cần mirror bền vững. Không tái sử dụng
URL một ABI cho ABI khác, không lấy package từ thư mục khác.
URL thật nằm trong output deploy Pages; vào trang gốc để chọn feed.

Tải public key qua kênh tin cậy; đối chiếu SHA256 với repo đã review:

```sh
sha256sum keys/nr3053-kmods.pub
```

Fingerprint SHA256 của public key hiện tại:
`66cf290cb46bb3009f33bbd9f41df8284d20d03e2a443d813281365dc89833ad`.
Khi rotate khóa phải review và cập nhật cả fingerprint này.

Sau khi đối chiếu `apk list --installed 'kernel*'` với kernel package trên
trang feed, tự chép key vào `/etc/apk/keys/nr3053-kmods.pub` (Extended đã
nhúng sẵn). Trên router:

```sh
FEED_URL='https://YOUR-ACCOUNT.github.io/YOUR-REPO/feeds/KERNEL/ABI/RUN-ATTEMPT'
printf 'ndx @nr3053_kmods %s/packages.adb\n' "$FEED_URL" \
  > /etc/apk/repositories.d/nr3053-kmods.list
apk update
apk add kmod-sched-cake@nr3053_kmods
```

Giữ feed chính thức cho user-space. Không dùng `--allow-untrusted`,
force-depends hoặc nâng kernel qua apk để chữa lệch ABI.
Sao lưu cấu hình rồi flash đúng sysupgrade qua LuCI **System → Backup/Flash
Firmware**, Keep settings nếu phù hợp; không Force upgrade. Gói apk cài
riêng có thể cần cài lại. Hướng dẫn này không tự thay đổi router.

## Port, cache và nâng tag

`overlay/0001-nr3053-integration.patch` sửa filogic.mk, 02_network,
platform.sh; file mới ở `overlay/target` / `overlay/files`.
Danh sách lấy từ git diff tag, commit nền trong `overlay/upstream-commit.txt`.
Feeds do tag OpenWrt ghim commit. Đổi tag cần review pin/feeds, thử overlay
và defconfig; kernel ngoài 6.12 bị verifier từ chối, không tự ép vượt.

```sh
git clone --depth 1 --branch v25.12.6 https://github.com/openwrt/openwrt.git openwrt
bash scripts/apply-overlay.sh "$PWD/openwrt"
cd openwrt
./scripts/feeds update -a
./scripts/feeds install -a
cp ../nr3053.seed.config .config
make defconfig
python3 ../scripts/verify.py . --config-only
```

Runner ubuntu-22.04: job tối đa 360 phút, build 300 phút, Ninja/make tối đa
2 job. Cache dl/ccache, không cache toàn bộ build_dir; chạy lại không resume
chính xác LLVM. Hủy/timeout có thể không lưu cache. Cleanup SDK chỉ chạy
trên GitHub-hosted runner; không chạy trên máy cá nhân. Cần ít nhất 25GiB
trống. CI không thay thế `sysupgrade -T`/boot test trên thiết bị thật.
Standard GitHub-hosted Actions miễn phí cho repo public theo chính sách
hiện hành; vẫn có giới hạn runner, concurrency, storage/cache và chính sách
chống lạm dụng. Larger runners có thể tính phí; không coi public là vô hạn.
