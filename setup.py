"""
Setup configuration for Perler Beads Designer
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="PerlerBeadsDesigner",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool to design pixel art patterns for perler beads",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/PerlerBeadsDesigner",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt6>=6.6.0",
        "numpy>=1.24.0",
        "opencv-python>=4.8.0",
        "Pillow>=10.0.0",
        "scikit-image>=0.22.0",
        "scipy>=1.11.0",
        "reportlab>=4.0.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
    ],
    entry_points={
        "console_scripts": [
            "perler-beads-designer=src.main:main",
        ],
    },
)
