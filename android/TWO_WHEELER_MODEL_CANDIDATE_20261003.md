# Android two-wheeler candidate

The Android app now has an additional ONNX asset:

- `app/src/main/assets/two_wheeler_candidate.onnx`
- source weights: `vehicle-mixed-traffic-yolo26n/best.pt`
- output shape: `[1, 8, 8400]` (4 box channels + 4 broad traffic classes)
- class 1 is treated as `两轮车` by the phone temporal risk engine
- asset SHA256: `1743c6ecb7112ae8d32247f9a938af015be1e2fb84e6083b76cdc7f3a0dcfa13`

`yolov8n.onnx` remains in the assets directory unchanged.  The app entry point
uses the new candidate asset and a 0.10 detector threshold for the first
two-wheeler warning prototype.  The phone risk path now requires four matched
observations, keeps a short history, checks the median area-growth trend and
downward image motion, and limits warnings to a central corridor.  Its default
parameters correspond to the recorded-video candidate rule (`min area 0.005`,
vertical/bottom approach `0.09/s`, corridor half-width `0.14`).  The Android
rider gate also runs the existing COCO person asset every second candidate
frame and retains a two-wheeler only when a person overlaps at least 25% of its
box.  This is a false-alert filter for parked rows, not a training label.  The
risk engine also predicts a short image-space route crossing and suppresses
targets already moving out of that corridor.  It reports the first two bands
as warning and the later close approach as danger.  This remains a lightweight
temporal approximation rather than a calibrated collision predictor and still
requires a real phone run for latency and false-alert measurement.

The ONNX adapter now reads the channel and candidate dimensions from the model
output, so the existing 84-channel COCO asset and the new 8-channel asset share
the same decoder.

## 2026-10-05 metadata verification

The shipped 320 input asset was read with ONNX Runtime. Its metadata reports
four broad classes in this order: `pedestrian`, `2-wheeler`, `3-wheeler`, and
`4-wheeler`. Therefore phone class 1 is a broad two-wheeler candidate, not a
bicycle-only class; bicycles, electric scooters, and motorcycles use the same
route-risk logic. The phone path still ignores classes 0, 2, and 3 for this
first safety scope.
