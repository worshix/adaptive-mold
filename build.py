#!/usr/bin/env python3
"""Build script for Adaptive Mold application.

Creates standalone executables for different operating systems using PyInstaller.

Usage:
    python build.py                    # Build for current OS
    python build.py --icon icon.png    # Build with custom icon
    python build.py --onefile          # Build single executable file
    python build.py --clean            # Clean build artifacts first
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# Project configuration
APP_NAME = "AdaptiveMold"
APP_VERSION = "0.1.0"
MAIN_SCRIPT = "adaptive_mold/app/__main__.py"
ICON_NAME = "adaptive_mold_icon"

# Directories
PROJECT_ROOT = Path(__file__).parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_DIR = PROJECT_ROOT


def get_platform_info() -> dict:
    """Get current platform information."""
    system = platform.system().lower()
    
    if system == "windows":
        icon_ext = ".ico"
        exe_ext = ".exe"
    elif system == "darwin":
        icon_ext = ".icns"
        exe_ext = ".app"
    else:  # Linux
        icon_ext = ".png"
        exe_ext = ""
    
    return {
        "system": system,
        "icon_ext": icon_ext,
        "exe_ext": exe_ext,
        "arch": platform.machine(),
    }


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
        return True
    except ImportError:
        print("✗ PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        return True


def clean_build():
    """Clean build artifacts."""
    print("\n🧹 Cleaning build artifacts...")
    
    for directory in [BUILD_DIR, DIST_DIR]:
        if directory.exists():
            shutil.rmtree(directory)
            print(f"  Removed: {directory}")
    
    # Remove spec files
    for spec_file in PROJECT_ROOT.glob("*.spec"):
        spec_file.unlink()
        print(f"  Removed: {spec_file}")
    
    print("✓ Clean complete")


def create_default_icon(icon_path: Path, platform_info: dict):
    """Create a simple default icon if none provided."""
    print(f"\n🎨 Creating default icon: {icon_path}")
    
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  Pillow not installed, skipping icon creation")
        return None
    
    # Create a 256x256 icon
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background - hexagon shape
    center = size // 2
    radius = size // 2 - 10
    
    # Draw gradient-like background circles
    for i in range(radius, 0, -5):
        alpha = int(255 * (i / radius))
        color = (0, int(100 + 55 * (i/radius)), int(200 + 55 * (i/radius)), alpha)
        draw.ellipse([center-i, center-i, center+i, center+i], fill=color)
    
    # Draw "AM" text
    try:
        # Try to use a system font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
    except:
        font = ImageFont.load_default()
    
    text = "AM"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2 - 10
    
    # Text shadow
    draw.text((text_x + 2, text_y + 2), text, fill=(0, 50, 100, 200), font=font)
    # Main text
    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
    
    # Save as PNG first
    png_path = icon_path.with_suffix('.png')
    img.save(png_path)
    print(f"  Created: {png_path}")
    
    # Convert to platform-specific format if needed
    if platform_info["system"] == "windows":
        ico_path = icon_path.with_suffix('.ico')
        # Create ICO with multiple sizes
        img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        print(f"  Created: {ico_path}")
        return ico_path
    elif platform_info["system"] == "darwin":
        # For macOS, just use PNG (PyInstaller will handle it)
        return png_path
    else:
        return png_path


def build_app(icon_path: Path = None, onefile: bool = False, console: bool = False):
    """Build the application using PyInstaller."""
    platform_info = get_platform_info()
    
    print(f"\n🔨 Building {APP_NAME} for {platform_info['system']} ({platform_info['arch']})")
    print(f"   Version: {APP_VERSION}")
    print(f"   Mode: {'Single file' if onefile else 'Directory'}")
    
    # Prepare PyInstaller arguments
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
    ]
    
    # One file or directory mode
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")
    
    # Console or windowed
    if not console:
        args.append("--windowed")
    
    # Icon
    if icon_path and icon_path.exists():
        args.extend(["--icon", str(icon_path)])
        print(f"   Icon: {icon_path}")
    
    # Add data files
    data_files = [
        ("adaptive_mold/resources/sample_geometry.json", "adaptive_mold/resources"),
    ]
    
    for src, dst in data_files:
        src_path = PROJECT_ROOT / src
        if src_path.exists():
            separator = ";" if platform_info["system"] == "windows" else ":"
            args.extend(["--add-data", f"{src_path}{separator}{dst}"])
    
    # Hidden imports that PyInstaller might miss
    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui", 
        "PySide6.QtWidgets",
        "numpy",
        "scipy",
        "scipy.spatial",
        "scipy.spatial.distance",
        "sqlalchemy",
        "pydantic",
        "loguru",
        "serial",
        "serial.tools.list_ports",
    ]
    
    # Try to add OCC if available
    try:
        import OCC
        hidden_imports.extend([
            "OCC",
            "OCC.Core",
            "OCC.Core.STEPControl",
            "OCC.Core.TopExp",
            "OCC.Core.TopoDS",
            "OCC.Core.BRep_Tool",
            "OCC.Core.gp",
        ])
        print("   Including: pythonocc-core")
    except ImportError:
        print("   Note: pythonocc-core not found, STEP support will be limited")
    
    # Try to add trimesh if available
    try:
        import trimesh
        hidden_imports.append("trimesh")
        print("   Including: trimesh")
    except ImportError:
        pass
    
    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])
    
    # Add the main script
    args.append(str(PROJECT_ROOT / MAIN_SCRIPT))
    
    print(f"\n📦 Running PyInstaller...")
    print(f"   Command: {' '.join(args[:10])}...")
    
    # Run PyInstaller
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    
    if result.returncode == 0:
        output_path = DIST_DIR / APP_NAME
        if onefile:
            output_path = DIST_DIR / f"{APP_NAME}{platform_info['exe_ext']}"
        
        print(f"\n✓ Build successful!")
        print(f"  Output: {output_path}")
        
        # Print size info
        if output_path.exists():
            if output_path.is_file():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"  Size: {size_mb:.1f} MB")
            else:
                total_size = sum(f.stat().st_size for f in output_path.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                print(f"  Total size: {size_mb:.1f} MB")
        
        return True
    else:
        print(f"\n✗ Build failed with return code {result.returncode}")
        return False


def main():
    """Main entry point for build script."""
    parser = argparse.ArgumentParser(
        description="Build Adaptive Mold application for distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build.py                     Build for current OS
  python build.py --icon myicon.png   Use custom icon
  python build.py --onefile           Create single executable
  python build.py --clean --onefile   Clean first, then build single file
        """
    )
    
    parser.add_argument(
        "--icon",
        type=Path,
        help="Path to icon file (.png, .ico, or .icns)"
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Create a single executable file instead of a directory"
    )
    parser.add_argument(
        "--console",
        action="store_true", 
        help="Show console window (useful for debugging)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts before building"
    )
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only clean, don't build"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"  ADAPTIVE MOLD BUILD SCRIPT")
    print(f"  Version: {APP_VERSION}")
    print("=" * 60)
    
    # Check PyInstaller
    if not args.clean_only:
        check_pyinstaller()
    
    # Clean if requested
    if args.clean or args.clean_only:
        clean_build()
    
    if args.clean_only:
        return 0
    
    # Prepare icon
    platform_info = get_platform_info()
    icon_path = args.icon
    
    if icon_path is None:
        # Create default icon
        default_icon_path = PROJECT_ROOT / "resources" / ICON_NAME
        default_icon_path.parent.mkdir(parents=True, exist_ok=True)
        icon_path = create_default_icon(default_icon_path, platform_info)
    elif not icon_path.exists():
        print(f"⚠ Warning: Icon file not found: {icon_path}")
        icon_path = None
    
    # Build
    success = build_app(
        icon_path=icon_path,
        onefile=args.onefile,
        console=args.console
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
