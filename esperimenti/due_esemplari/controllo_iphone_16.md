# Preliminary comparison of two iPhone 16 units

The owner confirmed that `IMG_3777.DNG` (A) and `IMG_6529.DNG` (B) came from two physically distinct iPhone 16 units. Both DNGs identify the rear camera and contain a BGGR Bayer mosaic. The experiment script decoded both visible mosaics at 4032 × 3024 using rawpy 0.28.0. LibRaw reports a black level of 528 and a white level of 4095 for both files.

For each Bayer position, we computed the Pearson correlation between the two captures' Gaussian residuals (sigma 1). We used sensor coordinates where both normalized values fell between 0.05 and 0.95, with the original orientation and alignment.

| BGGR plane | Valid pixels in both captures | Share of plane | Correlation |
| --- | ---: | ---: | ---: |
| B, top left | 238,983 | 7.8% | −0.0019 |
| G, top right | 916,370 | 30.1% | 0.0140 |
| G, bottom left | 915,564 | 30.0% | 0.0130 |
| R, bottom right | 597,540 | 19.6% | 0.0317 |

The correlations describe two captures from different units. Measuring PRNU attribution requires a same-unit control, fingerprints built from evenly illuminated captures from each unit, separate captures for choosing the threshold, and previously unseen scenes for blind testing. Many pixels in this pair fall below the intensity cutoff. Use brighter, even illumination for calibration while avoiding saturation.

## Second batch of 19 captures

We provisionally assigned the DNGs from `IMG_3778.DNG` through `IMG_3797.DNG` to phone A based on the attachment numbering. File 3780 was absent. All files decoded to distinct 4032 × 3024 BGGR mosaics. The median usable pixel share was 7.2% in blue, 52.2% in both green planes, and 41.9% in red.

The fingerprint built from all 19 captures has digest `f36cb845b32a1c4e503021b49ce70b1178e4f03a59fc7a2356fdc479b999c4e9`. For an internal check, we built a second fingerprint from the first 16 captures and scored the final three against it.

| DNG | B | Top G | Bottom G | R | Minimum |
| --- | ---: | ---: | ---: | ---: | ---: |
| IMG_3795.DNG | 0.186 | 0.150 | 0.150 | 0.242 | 0.150 |
| IMG_3796.DNG | 0.119 | 0.124 | 0.076 | 0.134 | 0.076 |
| IMG_3797.DNG | 0.101 | 0.045 | 0.051 | 0.142 | 0.045 |

The internal check used captures from the same batch, so shared scene details may contribute to the scores. The two initial DNGs were unavailable during this step. Comparing them with fingerprint A remains pending, as does collecting evenly illuminated captures from B and separate scenes to calibrate the threshold and measure error rates.
