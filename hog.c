/* hog — alat uji batas sumber daya untuk wadah (Irisan 3).
   Sengaja kecil & statis: mengalokasikan memori sungguhan (disentuh
   per halaman) atau membakar CPU, sambil melaporkan kemajuannya,
   supaya batas yang menahannya terlihat dari luar.
   Pakai: hog memori <MB>  |  hog cpu */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "cpu") == 0) {
        volatile unsigned long x = 0;
        for (;;) x++;
    }
    if (argc >= 3 && strcmp(argv[1], "memori") == 0) {
        long target = atol(argv[2]);
        long sudah = 0;
        while (sudah < target) {
            size_t mb = 8;
            char *p = malloc(mb * 1024 * 1024);
            if (!p) {
                printf("GAGAL-ALOKASI di %ld MB\n", sudah);
                fflush(stdout);
                return 3;
            }
            memset(p, 1, mb * 1024 * 1024);
            sudah += mb;
            printf("teralokasi %ld MB\n", sudah);
            fflush(stdout);
        }
        printf("SELESAI %ld MB\n", sudah);
        return 0;
    }
    fprintf(stderr, "pakai: hog memori <MB> | hog cpu\n");
    return 2;
}
