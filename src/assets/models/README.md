# U²-Netp model

- Purpose: lightweight general salient-object segmentation for the desktop app.
- Upstream architecture and pretrained weights: https://github.com/xuebinqin/U-2-Net
- ONNX distribution used by this repository: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx
- File: `u2netp.onnx`
- Size: 4,574,861 bytes
- SHA-256: `309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`
- Input: float32 NCHW, `1×3×320×320`, RGB, `[0,1]` then ImageNet mean/std normalization.
- Output: the first of seven `1×1×320×320` probability maps is the fused main prediction.
- License: Apache-2.0; see `LICENSE-U2NET.txt` and retain upstream attribution.

The application does not require PyTorch at runtime. CPU is always the fallback.
DirectML and CUDA require their corresponding ONNX Runtime builds and supported
hardware/drivers. Model quality and device performance must be validated on the
project's own image set; the file size is not a performance guarantee.
