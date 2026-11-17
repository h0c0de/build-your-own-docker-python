# RENCANA — Build 8: Docker dengan Python

Sumber: daftar build-your-own-x (fork h0c0de), seksi "Build your own
`Docker`", entri Python:

- Fewbytes, *rubber-docker — A workshop on Linux containers:
  Rebuild Docker from Scratch* — https://github.com/Fewbytes/rubber-docker
  (11 level: 00 fork/exec, 01 chroot image, 02 mount ns, 03 pivot_root,
  04 overlay, 05 UTS ns, 06 PID ns, 07 net ns, 08 cpu cgroup,
  09 memory cgroup, 10 setuid)

Dipilih Vero 15 Nov 2026 — kandidat yang tertunda sejak pemilihan
build ketiga (saat itu dinilai melawan sandbox VM ini). Penilaian itu
kini gugur oleh bukti: `unshare` namespace pengguna bekerja di sini.

## Adaptasi lingkungan (dicatat terbuka, bukan disembunyikan)

Workshop aslinya mengasumsikan VM root + cgroup v1 + modul C khusus
bernama `linux` untuk syscall yang tak ada di pustaka standar Python.
Lingkungan kami berbeda, jadi:

- **Rootless**: pintu masuk kami adalah user namespace (kita menjadi
  "root" di dalam namespace sendiri) — di workshop ini materi level
  akhir, di sini tiket masuk untuk semua level lain.
- **ctypes, bukan modul C**: syscall yang sama (unshare, mount,
  pivot_root, sethostname) dipanggil lewat libc dengan ctypes.
- **cgroup v2 baca-saja** dari sandbox kami: level cgroup dicoba di
  dalam user namespace; bila kernel menolak, cadangan jujurnya adalah
  rlimit — dicatat sebagai selisih, bukan ditutup-tutupi.
- Rootfs: BusyBox statis (workshop sendiri memakai image busybox).

## Irisan

- [x] Irisan 1 — selesai & terverifikasi 15 Nov 2026 (lihat CATATAN.md). Level 00+01: fork/exec + image chroot. Rootfs
      busybox dibangun skrip; proses berjalan terkurung di dalamnya.
      Bukti: isi rootfs yang terlihat, berkas host tak terjangkau,
      tulisan hanya mendarat di rootfs.
- [x] Irisan 2 — selesai & terverifikasi 15 Nov 2026 (lihat CATATAN.md). Level 02+03+05+06: mount namespace + pivot_root,
      UTS (hostname sendiri), PID namespace (proses = PID 1, /proc
      sendiri). Bukti: baterai isolasi vs host.
- [x] Irisan 3 — selesai & terverifikasi 15 Nov 2026 (lihat CATATAN.md). Level 07+08+09 (+04 bila kernel mengizinkan):
      net namespace, batas CPU & memori (cgroup v2 atau rlimit),
      overlay rootfs bila bisa. Bukti: batas benar-benar menahan.
- [x] Irisan 4 — selesai & terverifikasi 15 Nov 2026 (lihat CATATAN.md). Final: CLI `wadah.py run` merangkai semuanya;
      baterai isolasi lengkap melawan host; tutup + terbit.

## Di luar cakupan (dicatat)

Registry image & pull jarak jauh, networking antar-container &
port publishing ke host (butuh kerja sama namespace luar), daemon
manajemen, seccomp & capability dropping halus. Workshop-nya pun
berhenti di dasar-dasar ini.

## Pagar selesai

- [x] Satu perintah menjalankan proses terisolasi: rootfs, hostname,
      PID, dan batas sumber daya terbukti dari dalam & luar.
- [x] `CATATAN.md` satu halaman per irisan: konsep inti + temuan.
- [x] Repo GitHub publik `build-your-own-docker-python` terbit & terverifikasi.
