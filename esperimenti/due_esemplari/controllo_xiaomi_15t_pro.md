# Inspection of two Xiaomi 15T Pro DNGs

| File | Time in metadata | ISO | Exposure time |
| --- | ---: | ---: | ---: |
| IMG_20261121_093305.dng | 09:33:05 | 725 | Approx. 1/50 s |
| IMG_20261121_093307.dng | 09:33:07 | 725 | Approx. 1/50 s |

Both files identify the camera as Xiaomi 15T Pro and contain an uncompressed **BGGR** mosaic with one 16-bit stored sample per photosite. The declared white level is 16,383. The raster measures 4096 × 3072. The default crop measures 4080 × 3056 and starts at column 8, row 8. The two files have different SHA-256 digests. The inspected metadata contains no serial number that would distinguish two handsets.

We read the samples directly from the DNG TIFF block without demosaicing or rotation. Within the default crop, we subtracted the black level for each Bayer position and normalized the values against the white level. We computed residuals using the project's Gaussian filter with sigma 1, then calculated Pearson correlation at positions where both captures had normalized values between 0.05 and 0.95.

| BGGR position | Valid pixels in both captures | Residual correlation |
| --- | ---: | ---: |
| B, top left | 40.8% | 0.0471 |
| G, top right | 65.4% | 0.0428 |
| G, bottom left | 65.3% | 0.0445 |
| R, bottom right | 55.9% | 0.0492 |

The files contain Bayer samples suitable for comparison. The correlations describe this pair and can include shared scene details. Measuring discrimination between two handsets requires reference captures under uniform illumination for each unit, a separate set to calibrate the threshold, and a blind test set. The experiment script's rawpy reader was not tested on these two files in this inspection.
