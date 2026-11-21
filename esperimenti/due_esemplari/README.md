# Testing two units of the same camera model

This experiment measures how well the project's Bayer PRNU comparison distinguishes two camera units, A and B. Each capture is scored against both fingerprints. A reference passes when all four of its scores meet the threshold. Both references can pass, and both can fail.

## Capture protocol

Record the manufacturer, model, two distinct physical device identifiers, ISO, RAW mode, geometry, and visible-area origin. Use the same capture mode on both units and disable automatic development. The script relies on the person collecting the data to verify these conditions and identify the units.

1. **Reference fingerprints.** For a pilot experiment, collect 20 uniformly illuminated RAWs per unit at fixed ISO and several exposures. Avoid deep shadows and saturation. Fill the frame with an evenly illuminated diffuser.
2. **Threshold calibration.** Capture the same scenes with A and B and reserve about 10 captures per unit for threshold selection. Use comparable lighting conditions across the two units.
3. **Blind test.** Use both units to photograph new scenes, including low light and detailed surfaces. Start with 20 captures per unit for a pilot run. Keep each scene and capture burst within one split. Use anonymous filenames and have the person who captures the images keep the device mapping.

## Input and execution

Create the following layout in the data directory. Put only image files in the five capture directories.

```text
dati/
  uniformi/A/   uniformi/B/
  soglia/A/     soglia/B/
  cieco/
  verita.json
```

The ground truth file maps each blind filename to a camera, for example `{"001.dng": "B", "002.dng": "A"}`. The script reads it after setting the threshold and calculating scores for the blind set.

Run these commands from the repository root.

```sh
python3 -m pip install -r requirements-prnu.txt
python3 -m pip install rawpy
python3 -m esperimenti.due_esemplari.confronto dati --schema RGGB > rapporto.json
```

Select the pattern at the origin of the visible mosaic. The reader uses LibRaw through rawpy to subtract each channel's black level and normalize to its white level. Use linear Bayer RAW files supported by LibRaw. You can also supply two-dimensional NumPy `.npy` mosaics already normalized to [0, 1] with a common origin and pattern. The NumPy input uses the PRNU dependencies alone.

## Reading the results

Among evaluable calibration captures, the script minimizes the sum of false acceptances and false rejections. Ties favor fewer false acceptances. A reference's score is the minimum of its four correlations, in top-left, top-right, bottom-left, bottom-right order within the Bayer block.

For each capture, the JSON report lists the four scores against each reference and the units that passed. Divide each error count by the number of evaluable blind captures. Each capture provides one comparison against the correct unit and one against the other unit. Report captures with insufficient signal and cases where both references pass separately. Keep the originals, threshold, and report so the result can be reproduced.
