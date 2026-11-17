# Build Your Own Docker — Python

Container runtime dari nol dengan Python, mengikuti workshop
Fewbytes **rubber-docker** (*Rebuild Docker from Scratch*) dari daftar
[build-your-own-x](https://github.com/codecrafters-io/build-your-own-x).

Satu berkas utama: `wadah.py` — user + mount + UTS + PID + network
namespace, `pivot_root`, overlayfs, dan batas sumber daya, dengan
syscall lewat ctypes (pengganti modul C `linux` milik workshop).

## Pakai

```
./siapkan.sh          # unduh BusyBox + kompilasi alat uji ke aset/
python3 - <<'EOF'
import wadah
wadah.buat_rootfs('rootfs-ku', 'aset/busybox')
EOF
python3 wadah.py --hostname kotakku --memori 64 run rootfs-ku /bin/sh
```

Opsi: `--hostname NAMA`, `--lapisan DIR` (overlay: tulisan masuk ke
DIR/atas, image dasar tetap bersih), `--memori MB`, `--cpu DETIK`.

## Bukti

```
python3 uji_irisan1.py   # fork/exec + chroot: kurungan sistem berkas
python3 uji_irisan2.py   # namespace + pivot_root: hostname, PID, mount
python3 uji_irisan3.py   # net namespace, batas menahan beban, overlay
python3 uji_irisan4.py   # SEMUA isolasi dalam satu perintah
```

Isolasi dibuktikan dua arah — dari dalam container dan dari host.
Sorotan: kernel host sendiri melaporkan proses container sebagai
`NSpid: <pid-host> 1`; pemakan memori sungguhan berhenti di 56 MB di
bawah batas 64 MB; port yang sama bisa dipakai bersamaan oleh
container dan host karena dunia jaringannya berbeda.

## Adaptasi & batas jujur (detail di CATATAN.md)

Workshop aslinya mengasumsikan VM root + cgroup v1. Runtime ini
**rootless**: pintu masuknya user namespace (uid 0 di dalam, uid
pengguna di luar). Tiga tembok lingkungan dicatat terbuka:

- Mount `/proc` baru ditolak di sandbox tempat build ini diuji
  (proc host terkunci) — di host biasa ia berhasil; isolasi PID di
  sini dibuktikan lewat NSpid host.
- cgroup tidak terdelegasi di sandbox itu (mount cgroup2 pun EPERM),
  jadi batas memakai **rlimit** — ditegakkan kernel, tetapi
  semantiknya per-proses, bukan per-container seperti cgroup.
- Simpul `/dev` dasar di-bind-mount dari host (pola runtime rootless).

Di luar cakupan: registry/pull image, jaringan antar-container &
penerbitan port ke host, daemon, seccomp. Workshop-nya pun berhenti
di dasar-dasar ini.
