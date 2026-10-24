"""Desktop pattern export: PNG images and optional BOM CSV files."""
import csv
import os
from typing import Dict

import cv2
import numpy as np


class PatternExporter:
    """Export rendered patterns and their bill of materials."""

    def __init__(self, output_dir: str = './output'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    @staticmethod
    def _write_png(image: np.ndarray, filepath: str) -> None:
        """Write RGB images with Unicode-safe paths."""
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        success, buffer = cv2.imencode('.png', image_bgr)
        if not success:
            raise ValueError('PNG 编码失败')
        with open(filepath, 'wb') as f:
            f.write(buffer.tobytes())

    def export_png(self, pattern: np.ndarray, filename: str,
                   scale: int = 1) -> str:
        """Export a bead pattern image as PNG."""
        if pattern is None:
            raise ValueError('图案不能为空')
        if scale > 1:
            h, w = pattern.shape[:2]
            pattern = cv2.resize(pattern, (w * scale, h * scale),
                                 interpolation=cv2.INTER_NEAREST)
        filepath = os.path.join(self.output_dir, f'{filename}.png')
        self._write_png(pattern, filepath)
        return filepath

    def export_png_with_codes(self, pattern: np.ndarray, color_map: np.ndarray,
                              filename: str, bead_size: int = 30,
                              scale: int = 1) -> str:
        """Export a pattern with a color code in every bead cell."""
        h, w = pattern.shape[:2]
        output = np.full((h * bead_size, w * bead_size, 3), 255,
                         dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                color_code = str(color_map[y, x])
                color_rgb = pattern[y, x]
                y1, y2 = y * bead_size, (y + 1) * bead_size
                x1, x2 = x * bead_size, (x + 1) * bead_size
                output[y1:y2, x1:x2] = color_rgb
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = min(0.4, bead_size / 15)
                r, g, b = color_rgb[:3]
                brightness = 0.299 * r + 0.587 * g + 0.114 * b
                text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
                text_size = cv2.getTextSize(color_code, font, font_scale, 1)[0]
                text_x = x1 + (bead_size - text_size[0]) // 2
                text_y = y1 + (bead_size + text_size[1]) // 2
                cv2.putText(output, color_code, (text_x, text_y), font,
                            font_scale, text_color, 1)
        if scale > 1:
            h_out, w_out = output.shape[:2]
            output = cv2.resize(output, (w_out * scale, h_out * scale),
                                interpolation=cv2.INTER_LINEAR)
        filepath = os.path.join(self.output_dir, f'{filename}_codes.png')
        self._write_png(output, filepath)
        return filepath

    def export_png_standard(self, chart_image: np.ndarray, filename: str,
                            scale: float = 1.0) -> str:
        """Export a pre-rendered standard chart as PNG."""
        if chart_image is None:
            raise ValueError('图纸图像不能为空')
        if scale <= 0:
            raise ValueError('PNG 缩放必须大于 0')
        out = chart_image
        if scale != 1:
            h, w = out.shape[:2]
            interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST
            dsize = (max(1, int(round(w * scale))),
                     max(1, int(round(h * scale))))
            out = cv2.resize(out, dsize, interpolation=interp)
        filepath = os.path.join(self.output_dir, f'{filename}.png')
        self._write_png(out, filepath)
        return filepath

    def export_bom_csv(self, bom: Dict, filename: str,
                       brand: str = '') -> str:
        """Export BOM as Excel-friendly UTF-8 CSV, sorted by bead count."""
        colors = (bom or {}).get('colors', {})
        rows = sorted(colors.items(),
                      key=lambda item: (-int(item[1].get('count', 0)), item[0]))
        filepath = os.path.join(self.output_dir, f'{filename}_bom.csv')
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['brand', 'code', 'name', 'count', 'percentage'])
            for code, info in rows:
                writer.writerow([
                    brand,
                    code,
                    info.get('name', ''),
                    int(info.get('count', 0)),
                    f"{float(info.get('percentage', 0)):.2f}",
                ])
        return filepath


if __name__ == '__main__':
    print('PatternExporter ready')
