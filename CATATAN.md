# CATATAN — Build 8: Docker dengan Python

Mengikuti workshop Fewbytes, *rubber-docker: Rebuild Docker from
Scratch* — https://github.com/Fewbytes/rubber-docker (11 level).
Adaptasi lingkungan (rootless, ctypes, cgroup v2) dicatat di RENCANA.
Satu halaman per irisan: konsep inti + temuan.

## Irisan 1 — fork/exec + chroot image (15 Nov 2026, terverifikasi)

**Yang dibangun:** Level 00 dan 01 workshop — proses anak hasil `fork()` yang `exec` perintah di dalam rootfs hasil `chroot()`, plus pembangun rootfs BusyBox (satu biner statis + symlink applet, meniru image busybox workshop). Karena sandbox kami bukan root, anak lebih dulu masuk *user namespace* lewat ctypes (`unshare(CLONE_NEWUSER)`, lalu menulis `setgroups=deny`, `gid_map`, `uid_map`): uid 0 di dalam, uid kami sendiri di luar — kemampuan chroot didapat tanpa pernah menjadi root sungguhan. Syscall lewat ctypes ke libc menggantikan modul C `linux` milik workshop dengan semantik yang sama.

**Bukti jalan:** `uji_irisan1.py` — semua hijau, dan wasitnya adalah sistem berkas host itu sendiri. Dari dalam: `ls /` menunjukkan hanya isi rootfs (`bin etc proc tanda.txt tmp`), berkas tanda rootfs terbaca, berkas host (`/etc/hostname` asli) tidak terjangkau. Tulisan dari dalam mendarat di rootfs (terlihat dari host) dan tidak bocor ke `/tmp` host. Kode keluar diteruskan dengan benar, dan `id` di dalam melaporkan uid 0.

**Temuan — dua pelajaran syscall yang hanya datang dari praktik:**
1. Sesudah menulis `deny` ke `setgroups`, syscall `setgroups()` itu sendiri menjadi *terlarang* di namespace tersebut — memang itu gunanya deny. Kode awal kami memanggilnya dan ditolak EPERM; urutan yang benar berhenti di pemetaan gid/uid lalu `setgid`/`setuid`.
2. Bug yang lebih licik ada di *pelaporan*: `os.waitpid` mengembalikan 2-tuple, kode kami membongkar 3 — proses induk selalu runtuh dengan kode 1 *sesudah* anak selesai bekerja. Semua perintah container sebenarnya berhasil (berkas tertulis, keluaran benar) tapi semuanya "dilaporkan gagal". Di seri ini polanya berulang: pipa pelaporan adalah bagian dari kebenaran, bukan detail.

## Irisan 2 — Namespace & pivot_root (15 Nov 2026, terverifikasi)

**Yang dibangun:** Level 02, 03, 05, 06 workshop — anak masuk mount + UTS + PID namespace sekaligus (PID namespace hanya berlaku bagi *anak-anak* proses yang memanggil unshare, jadi struktur kami fork dua tahap dan cucunyalah yang menjadi PID 1). Di dalamnya: hostname sendiri lewat `sethostname`, seluruh pohon mount dijadikan privat (`MS_REC|MS_PRIVATE`) agar tidak ada yang merambat, rootfs di-bind ke dirinya sendiri lalu `pivot_root` menukar akar dan akar lama dilepas dengan `MNT_DETACH` — pengganti chroot yang tidak menyisakan jalan kembali ke rootfs host.

**Bukti jalan:** `uji_irisan2.py` — semua hijau, setiap klaim diperiksa dua arah. Hostname di dalam `wadahku`, hostname host tak berubah. Proses utama melaporkan `$$` = 1 dan anak pertamanya = 2. Mount tmpfs di dalam bekerja dan tidak muncul di tabel mount host. Kode keluar tetap utuh melewati dua fork.

**Temuan — tembok lingkungan yang jujur, dan wasit yang lebih keras sebagai gantinya:** mount `/proc` baru ditolak kernel (EPERM) dalam segala varian, termasuk `subset=pid` — karena sandbox kami sendiri tinggal di dalam container yang `/proc`-nya *terkunci* (path bertopeng), dan kernel menolak proc segar di userns turunannya. Ini tembok yang sama yang menahan rootless Docker di dalam container terbatas; di host biasa mount itu berhasil. Karena `ps` tak bisa jadi bukti, isolasi PID dibuktikan lewat saluran kernel di sisi host: berkas `/proc/<pid>/status` milik proses container menunjukkan **`NSpid: 5543 1`** — kernel sendiri melaporkan bahwa proses yang di host bernomor 5543 itu adalah PID 1 di namespace-nya. Bukti dari mulut kernel, bukan dari alat di dalam yang bisa saja tertipu.

## Irisan 3 — Net namespace, batas sumber daya, overlay (15 Nov 2026, terverifikasi)

**Yang dibangun:** Level 07, 08, 09, dan 04 workshop. Network namespace baru hanya berisi loopback yang awalnya mati — dinyalakan lewat ioctl `SIOCSIFFLAGS` (kita memegang CAP_NET_ADMIN atas namespace milik userns kita). Overlayfs di-mount di dalam userns dengan rootfs sebagai lowerdir baca-saja dan folder per-container sebagai upperdir. Batas sumber daya memakai rlimit (`RLIMIT_AS`, `RLIMIT_CPU`) yang dipasang tepat sebelum exec.

**Bukti jalan:** `uji_irisan3.py` — semua hijau dengan beban sungguhan, bukan pembacaan konfigurasi. Jaringan: di dalam hanya ada `lo`, ping ke 127.0.0.1 dijawab; dan bukti dua-dunia — container melayani port 18099 di dunianya sementara host *tetap bisa* memakai 18099 dan yang menjawab di host adalah server host. Memori: alat uji `hog` (C statis kecil, mengalokasikan dan menyentuh halaman sungguhan) menyelesaikan 96 MB tanpa batas, tetapi di bawah batas 64 MB berhenti dengan gagal alokasi di 56 MB. CPU: pemutar abadi dibunuh di 1,1 detik oleh batas 1 detik (kode 137). Overlay: tulisan container mendarat di lapisan atas, rootfs dasar tetap bersih, container kedua melihat lapisan yang sama.

**Temuan — cgroup tertutup, dan itu dicatat sebagai selisih, bukan kegagalan diam:** jalur workshop (cgroup) dicoba lebih dulu lewat probe: bahkan *mount* cgroup2 di dalam userns ditolak EPERM di sandbox ini — tidak ada delegasi cgroup untuk kami. Maka mekanismenya rlimit: ditegakkan kernel dan diwarisi anak, tetapi semantiknya per-proses, bukan per-container seperti cgroup (sebuah container yang mem-fork banyak anak kecil bisa mengakali batas memori per-proses dengan cara yang tidak bisa dilakukan pada cgroup). Perbedaan itu nyata, kami tulis apa adanya — di host dengan delegasi cgroup, level 08/09 workshop berjalan sebagaimana mestinya. Satu batas sengaja tidak dipasang: `RLIMIT_NPROC`, karena penghitungnya adalah uid nyata di namespace induk — di sandbox bersama, batas kecil akan memblokir semua fork termasuk milik host sendiri.

## Irisan 4 — Final: semua isolasi, satu perintah (15 Nov 2026, terverifikasi)

**Yang dibangun:** bukan fitur baru, melainkan pembuktian rangkaiannya: satu invocation `wadah.py` dengan hostname + overlay + batas memori + jaringan sendiri sekaligus, menjalankan skrip laporan di dalam, dan host memverifikasi setiap barisnya. Dalam merangkainya, satu kekurangan rootfs ketahuan dan diperbaiki: rootfs kami belum punya simpul `/dev` — pengalihan ke `/dev/null` (idiom shell paling dasar) gagal di dalam. Karena `mknod` dari userns ditolak pada sistem berkas milik namespace induk, keempat perangkat aman (null, zero, urandom, console) di-bind-mount dari host sebelum pivot — pola yang sama yang dipakai runtime rootless sungguhan.

**Bukti jalan:** `uji_irisan4.py` — semua hijau: container selesai kode 0 dengan hostname `finalku`, PID 1, isi image terbaca lewat overlay, jaringan loopback saja dan hidup, batas memori aktif *bersamaan* dengan semua isolasi lain (hog berhenti gagal-alokasi), jejak tertulis di lapisan atas, image dasar bersih, hostname host tak berubah. Regresi Irisan 1–3 tetap hijau.

**Pelajaran penutup build:** container bukan satu teknologi melainkan *tumpukan persetujuan kecil dari kernel* — namespace untuk pandangan, pivot untuk akar, overlay untuk tulisan, batas untuk perilaku — dan masing-masing hanya terbukti saat diperiksa dari sisi lain pagarnya. Build ini juga yang paling banyak menabrak tembok lingkungannya (proc terkunci, cgroup tak terdelegasi), dan justru di situlah letak pelajarannya: runtime sungguhan seperti Docker rootless menghabiskan sebagian besar kodenya untuk persis tembok-tembok semacam itu.
