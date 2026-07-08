"""
Color loader for Perler bead colors from local JSON file
Loads colors from colors_221.json asset file
"""
import json
from typing import List, Dict
from pathlib import Path


class PixelBeadsColorScraper:
    """Loader for Perler Beads color chart from local JSON file"""
    
    def __init__(self):
        self.colors: List[Dict] = []
        self.colors_file = self._get_colors_file_path()
    
    @staticmethod
    def _get_colors_file_path() -> Path:
        """Get the path to colors_221.json asset file"""
        # Get the path relative to this file
        current_dir = Path(__file__).parent.parent  # Go to src/
        colors_file = current_dir / "assets" / "colors_221.json"
        return colors_file
    
    def fetch_colors(self) -> List[Dict]:
        """
        Load color data from colors_221.json
        
        Returns:
            List of color dictionaries with code, name, and hex value
        """
        try:
            colors = self._load_colors_from_json()
            self.colors = colors if colors else self._get_default_colors()
            return self.colors
        except Exception as e:
            print(f"加载颜色文件失败: {e}")
            return self._get_default_colors()
    
    def _load_colors_from_json(self) -> List[Dict]:
        """Load colors from local JSON file"""
        if not self.colors_file.exists():
            raise FileNotFoundError(f"颜色文件不存在: {self.colors_file}")
        
        with open(self.colors_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def _get_default_colors() -> List[Dict]:
        """
        Return default MARD bead colors as fallback
        Based on actual MARD 221-color chart
        """
        return [
            {'code': 'H1', 'name': '纯白', 'hex': '#ffffff'},
            {'code': 'H7', 'name': '纯黑', 'hex': '#010101'},
            {'code': 'F5', 'name': '深红', 'hex': '#e10328'},
            {'code': 'B4', 'name': '翠绿', 'hex': '#5fdf34'},
            {'code': 'C8', 'name': '深蓝', 'hex': '#0f52bd'},
            {'code': 'A3', 'name': '柠檬黄', 'hex': '#fcff92'},
            {'code': 'H3', 'name': '浅灰', 'hex': '#b4b4b4'},
            {'code': 'H5', 'name': '深灰', 'hex': '#464648'},
            {'code': 'A7', 'name': '橙橘', 'hex': '#fa8c4f'},
            {'code': 'D7', 'name': '深紫', 'hex': '#8758a9'},
            {'code': 'E6', 'name': '玫红', 'hex': '#eb4172'},
            {'code': 'G7', 'name': '深棕', 'hex': '#985c3a'},
            {'code': 'C13', 'name': '淡蓝', 'hex': '#cde7fe'},
            {'code': 'B6', 'name': '薄荷绿', 'hex': '#64e0a4'},
            {'code': 'F2', 'name': '正红', 'hex': '#f63d4b'},
            {'code': 'E4', 'name': '桃红', 'hex': '#e8649e'},
            {'code': 'G3', 'name': '肤色', 'hex': '#f1c4a5'},
            {'code': 'M4', 'name': '浅卡其', 'hex': '#e0d4bc'},
        ]


if __name__ == '__main__':
    scraper = PixelBeadsColorScraper()
    colors = scraper.fetch_colors()
    print(f"加载了 {len(colors)} 种颜色")
    print(f"颜色文件路径: {scraper.colors_file}")
    print("\n前5种颜色:")
    for color in colors[:5]:
        print(f"  {color['code']}: {color['name']} ({color['hex']})")
