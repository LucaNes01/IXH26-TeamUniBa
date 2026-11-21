/* CROSS richiede randombytes. Il chiamante fornisce un buffer di entropia per operazione. */
#include <stddef.h>
#include <string.h>
#include "api.h"

static _Thread_local const unsigned char *entropy;
static _Thread_local size_t available, consumed;
static _Thread_local int entropy_error;

void randombytes(unsigned char *out, unsigned long long len) {
    if (entropy == NULL || len > available - consumed) {
        entropy_error = 1;
        memset(out, 0, (size_t)len);
        return;
    }
    memcpy(out, entropy + consumed, (size_t)len);
    consumed += (size_t)len;
}

static void begin(const unsigned char *input, size_t len) {
    entropy = input;
    available = len;
    consumed = 0;
    entropy_error = 0;
}

static int finish(int status) {
    int failed = entropy_error || consumed != available;
    entropy = NULL;
    available = consumed = 0;
    return failed ? -2 : status;
}

size_t tb_cross_pk_bytes(void) { return CRYPTO_PUBLICKEYBYTES; }
size_t tb_cross_sk_bytes(void) { return CRYPTO_SECRETKEYBYTES; }
size_t tb_cross_sig_bytes(void) { return CRYPTO_BYTES; }
size_t tb_cross_key_entropy_bytes(void) { return KEYPAIR_SEED_LENGTH_BYTES; }
size_t tb_cross_sign_entropy_bytes(void) { return SEED_LENGTH_BYTES + SALT_LENGTH_BYTES; }

int tb_cross_keypair(unsigned char *pk, unsigned char *sk,
                     const unsigned char *randomness) {
    begin(randomness, tb_cross_key_entropy_bytes());
    return finish(crypto_sign_keypair(pk, sk));
}

int tb_cross_sign(unsigned char *sm, unsigned long long *smlen,
                  const unsigned char *m, unsigned long long mlen,
                  const unsigned char *sk, const unsigned char *randomness) {
    begin(randomness, tb_cross_sign_entropy_bytes());
    return finish(crypto_sign(sm, smlen, m, mlen, sk));
}
