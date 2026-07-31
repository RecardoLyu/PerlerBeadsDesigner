"""
Export module for saving patterns to PNG and PDF
"""
import cv2
import numpy as np
from typing import Dict, Optional
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, letter, landscape
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw, ImageFont

# Register Chinese fonts
def _register_chinese_fonts():
    """Register system Chinese fonts for PDF support"""
    try:
        # Try common Windows Chinese font paths
        font_paths = [
            "C:\\Windows\\Fonts\\SimHei.ttf",      # 黑体
            "C:\\Windows\\Fonts\\simsun.ttc",      # 宋体
            "C:\\Windows\\Fonts\\simfang.ttf",     # 仿宋
            "/System/Library/Fonts/SimHei.ttf",    # macOS
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
        ]
        
        registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # Register as SimHei (we use this name in styles)
                    if not registered:
                        pdfmetrics.registerFont(TTFont('SimHei', font_path))
                        print(f"成功注册中文字体: {font_path}")
                        registered = True
                        break
                except Exception as e:
                    print(f"注册字体 {font_path} 失败: {e}")
        
        if not registered:
            print("警告: 未找到系统中文字体，PDF中文可能显示为方框")
    except Exception as e:
        print(f"字体注册过程出错: {e}")

# Call on import
_register_chinese_fonts()


class PatternExporter:
    """Exports patterns to various formats"""
    
    def __init__(self, output_dir: str = './output'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def export_png(self, pattern: np.ndarray, filename: str, 
                  scale: int = 1) -> str:
        """
        Export pattern as PNG with support for Chinese filenames
        
        Args:
            pattern: Pattern image array
            filename: Output filename (without extension, supports Chinese)
            scale: Scale factor
        
        Returns:
            Path to saved file
        """
        if pattern is None:
            raise ValueError("图案不能为空")
        
        # Scale if needed
        if scale > 1:
            h, w = pattern.shape[:2]
            pattern = cv2.resize(pattern, (w * scale, h * scale), 
                                interpolation=cv2.INTER_NEAREST)
        
        # Convert RGB to BGR for cv2
        pattern_bgr = cv2.cvtColor(pattern, cv2.COLOR_RGB2BGR)
        
        filepath = os.path.join(self.output_dir, f"{filename}.png")
        
        # Use imdecode/imencode to support Chinese filenames
        try:
            is_success, buffer = cv2.imencode('.png', pattern_bgr)
            with open(filepath, 'wb') as f:
                f.write(buffer)
        except Exception as e:
            # Fallback to cv2.imwrite for ASCII filenames
            cv2.imwrite(filepath, pattern_bgr)
        
        return filepath
    
    def export_png_with_grid(self, pattern: np.ndarray, filename: str,
                            bead_size: int = 20, scale: int = 1) -> str:
        """
        Export pattern with grid
        
        Args:
            pattern: Pattern image array
            filename: Output filename
            bead_size: Size of each bead/cell in pixels
            scale: Scale factor
        
        Returns:
            Path to saved file
        """
        h, w = pattern.shape[:2]
        
        # Create image with grid
        output = np.zeros((h * bead_size, w * bead_size, 3), dtype=np.uint8)
        
        for y in range(h):
            for x in range(w):
                y1 = y * bead_size
                y2 = y1 + bead_size
                x1 = x * bead_size
                x2 = x1 + bead_size
                output[y1:y2, x1:x2] = pattern[y, x]
        
        # Draw grid
        grid_color = (200, 200, 200)
        for x in range(w + 1):
            x_pixel = x * bead_size
            cv2.line(output, (x_pixel, 0), (x_pixel, output.shape[0]), grid_color, 1)
        
        for y in range(h + 1):
            y_pixel = y * bead_size
            cv2.line(output, (0, y_pixel), (output.shape[1], y_pixel), grid_color, 1)
        
        # Scale if needed
        if scale > 1:
            h_out, w_out = output.shape[:2]
            output = cv2.resize(output, (w_out * scale, h_out * scale),
                              interpolation=cv2.INTER_NEAREST)
        
        # Save
        output_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
        filepath = os.path.join(self.output_dir, f"{filename}_grid.png")
        cv2.imwrite(filepath, output_bgr)
        
        return filepath
    
    def export_png_with_codes(self, pattern: np.ndarray, color_map: np.ndarray,
                             filename: str, bead_size: int = 30, scale: int = 1) -> str:
        """
        Export pattern with color codes labeled
        
        Args:
            pattern: Pattern image array
            color_map: Map of color codes for each bead
            filename: Output filename
            bead_size: Size of each bead/cell in pixels
            scale: Scale factor
        
        Returns:
            Path to saved file
        """
        h, w = pattern.shape[:2]
        output = np.ones((h * bead_size, w * bead_size, 3), dtype=np.uint8) * 255
        
        for y in range(h):
            for x in range(w):
                color_code = color_map[y, x]
                color_rgb = pattern[y, x]
                
                y1 = y * bead_size
                y2 = y1 + bead_size
                x1 = x * bead_size
                x2 = x1 + bead_size
                
                # Draw color
                output[y1:y2, x1:x2] = color_rgb
                
                # Draw code
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = min(0.4, bead_size / 15)
                
                # Determine text color based on background brightness
                r, g, b = color_rgb[:3]
                brightness = 0.299 * r + 0.587 * g + 0.114 * b
                text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
                text_color = tuple(int(c) for c in text_color)
                
                text_size = cv2.getTextSize(color_code, font, font_scale, 1)[0]
                text_x = x1 + (bead_size - text_size[0]) // 2
                text_y = y1 + (bead_size + text_size[1]) // 2
                
                cv2.putText(output, color_code, (text_x, text_y), font, font_scale, text_color, 1)
        
        # Scale if needed
        if scale > 1:
            h_out, w_out = output.shape[:2]
            output = cv2.resize(output, (w_out * scale, h_out * scale),
                              interpolation=cv2.INTER_LINEAR)
        
        # Save
        output_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
        filepath = os.path.join(self.output_dir, f"{filename}_codes.png")
        cv2.imwrite(filepath, output_bgr)
        
        return filepath
    
    def export_png_standard(self, chart_image: np.ndarray, filename: str,
                            scale: int = 1) -> str:
        """
        Export a pre-rendered standard chart image as PNG.

        Args:
            chart_image: Image produced by PatternGenerator.render_standard_chart (RGB)
            filename: Output filename (without extension)
            scale: Scale factor

        Returns:
            Path to saved file
        """
        if chart_image is None:
            raise ValueError("图纸图像不能为空")

        out = chart_image
        if scale > 1:
            h, w = out.shape[:2]
            out = cv2.resize(out, (w * scale, h * scale),
                             interpolation=cv2.INTER_NEAREST)

        out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        filepath = os.path.join(self.output_dir, f"{filename}.png")
        try:
            is_success, buffer = cv2.imencode('.png', out_bgr)
            with open(filepath, 'wb') as f:
                f.write(buffer)
        except Exception:
            cv2.imwrite(filepath, out_bgr)
        return filepath

    def export_pdf(self, pattern_image: np.ndarray, bom: Dict,
                   filename: str, page_size_name: str = 'A4', title: str = None) -> str:
        """
        Export pattern as PDF with BOM

        Args:
            pattern_image: Rendered pattern image
            bom: Bill of materials dictionary
            filename: Output filename (without extension)
            page_size_name: 'A4' or 'Letter'
            title: PDF title (defaults to "拼豆图纸" if None)

        Returns:
            Path to saved file
        """
        if title is None:
            title = "拼豆图纸"
        filepath = os.path.join(self.output_dir, f"{filename}.pdf")

        # Save pattern as temporary image
        temp_pattern_path = os.path.join(self.output_dir, '_temp_pattern.png')
        pattern_bgr = cv2.cvtColor(pattern_image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(temp_pattern_path, pattern_bgr)

        try:
            page_size_map = {
                'A4': A4,
                'Letter': letter,
            }

            pdf_page_size = page_size_map.get(page_size_name, A4)
            page_w, page_h = pdf_page_size

            doc = SimpleDocTemplate(filepath, pagesize=pdf_page_size,
                                   rightMargin=10*mm, leftMargin=10*mm,
                                   topMargin=10*mm, bottomMargin=10*mm)

            styles = getSampleStyleSheet()
            elements = []

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                fontName='SimHei',
                textColor=colors.HexColor('#333333'),
                spaceAfter=6,
                alignment=TA_CENTER
            )

            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 2*mm))

            # Standard chart image - fit within available page area (proportional)
            avail_w = page_w - 30*mm
            avail_h = page_h - 40*mm   # leave room for title / footer only
            try:
                img_h, img_w_px = pattern_image.shape[:2]
                # scale to fit both width and height, keep aspect
                scale = min(avail_w / img_w_px, avail_h / img_h)
                disp_w = img_w_px * scale
                disp_h = img_h * scale
                img = RLImage(temp_pattern_path, width=disp_w, height=disp_h)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 5*mm))
            except Exception as e:
                print(f"Warning: Could not add image to PDF: {e}")

            # BOM appears only as the chip bar inside the chart image; the
            # separate reportlab BOM table was removed.

            # Footer
            footer_text = f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                fontName='SimHei',
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(footer_text, footer_style))

            doc.build(elements)
        finally:
            try:
                os.remove(temp_pattern_path)
            except:
                pass

        return filepath

    @staticmethod
    def _render_pattern_with_codes(pattern: np.ndarray, color_map: np.ndarray,
                                   bead_size: int = 20) -> np.ndarray:
        """Helper to render pattern with codes"""
        h, w = pattern.shape[:2]
        output = np.ones((h * bead_size, w * bead_size, 3), dtype=np.uint8) * 255
        
        for y in range(h):
            for x in range(w):
                color_code = color_map[y, x]
                color_rgb = pattern[y, x]
                
                y1 = y * bead_size
                y2 = y1 + bead_size
                x1 = x * bead_size
                x2 = x1 + bead_size
                
                output[y1:y2, x1:x2] = color_rgb
                
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.3
                
                r, g, b = color_rgb[:3]
                brightness = 0.299 * r + 0.587 * g + 0.114 * b
                text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
                
                text_size = cv2.getTextSize(color_code, font, font_scale, 1)[0]
                text_x = x1 + (bead_size - text_size[0]) // 2
                text_y = y1 + (bead_size + text_size[1]) // 2
                
                cv2.putText(output, color_code, (text_x, text_y), font, font_scale, text_color, 1)
        
        return output


if __name__ == '__main__':
    exporter = PatternExporter()
    print("PatternExporter ready")
