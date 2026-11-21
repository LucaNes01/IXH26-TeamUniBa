# CROSS upstream provenance

Repository: https://github.com/CROSS-signature/CROSS-implementation

Pinned commit: `7e9a4d93ab072b7c59f89589d0eb2d90751330fb` (CROSS v2.2).

`Reference_Implementation/`, `KAT_Generation/`, `LICENSE`, `README` and
`sha_512_sum_KATs` are copied byte for byte from upstream. The KAT directory
comes from upstream `Additional_Implementations/KAT_Generation/`.
`UPSTREAM.json` records provenance and SHA-256 for every copied file.

Team Bari's integration is outside these upstream sources:

- `scripts/build_cross.py`: reference library builds for category 1 RSDP,
  SIG_SIZE (small) or SPEED + NO_TREES (fast), standalone upstream SHAKE.
- `crypto_kit/native/cross_bridge.c`: ABI metadata and per-call randomness
  interface for upstream `randombytes`, backed by Python OS randomness.
- `crypto_kit/cross_official.py`: Python ctypes API and detached signatures.
- `scripts/verify_cross_kat.py`: unmodified upstream KAT generator and NIST RNG,
  linked separately with OpenSSL; verifies complete upstream SHA-512 checksums.

The application builds define upstream `SKIP_ASSERT` so invalid signatures
return rejection rather than aborting on a debug assertion. No upstream
cryptographic source has been edited. The application never uses the KAT RNG.
The reference build needs no AVX2 instructions and was tested on macOS arm64.
The old educational key/signature formats are incompatible with this backend.
