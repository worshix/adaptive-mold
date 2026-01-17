# Adaptive Mold

**Precision Path Mapping System**

A PySide6 desktop application for loading STEP geometry files, visualizing 3D wireframes, computing mapping paths, and sending waypoints to a controller over serial communication.

---

## Project Information

| | |
|---|---|
| **Project Title** | Adaptive Mold - Precision Path Mapping System |
| **Student** | Joseph B Mawodzeka |
| **Supervisor** | Worship L Mugomeza |
| **Institution** | Engineering Department |
| **Year** | 2026 |

---

## Features

- **Precise STEP File Loading**: Uses pythonocc-core (OpenCASCADE) for engineering-grade B-Rep geometry precision
- **3D Wireframe View**: Interactive 3D visualization with rotate/pan/zoom controls
- **Path Planning**: Greedy nearest-neighbor and edge-sampling algorithms for waypoint sequencing
- **Serial Communication**: Real serial (pyserial) and mock controller for demo/testing
- **Job Persistence**: SQLite database storage for jobs, geometry, and waypoints
- **Mock Mode**: Built-in mock controller for testing without hardware
- **Welcome Screen**: Professional project information display on startup

## Requirements

- Python 3.11 (required for pythonocc-core compatibility)
- Conda (Anaconda or Miniconda)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd adaptive-mold
```

2. Create the conda environment:
```bash
conda env create -f environment.yml
```

3. Activate the environment:
```bash
conda activate eng
```

4. Install the project in development mode (optional):
```bash
pip install -e .
```

## Running the Application

### Launch the GUI

```bash
# Make sure the environment is activated
conda activate eng

# Run the application
python -m adaptive_mold.app
```

### Run the Mock Controller (Standalone)

For testing the serial protocol independently:

```bash
python -m adaptive_mold.resources.mock_controller
```

Then send JSON commands via stdin:
```json
{"cmd":"MAP","job_id":"test-1","path":[[0,0,0],[10,10,10],[20,20,20]],"meta":{"units":"mm","feedrate":50}}
```

## Usage Guide

### Creating a Job

1. Click **"New Job"** in the dashboard
2. Enter a job name
3. Either:
   - Click **"Browse..."** to select a STEP file, or
   - Click **"Use Sample Geometry"** for the built-in test geometry
4. Configure planner settings (mode and sample spacing)
5. Click **OK** to create the job

### Planning a Path

1. Select a job from the job list
2. Click **"Plan Path"** to compute waypoints
3. The status bar will show waypoint count and total distance

### Running the Mapping (Mock Mode)

1. Ensure **"Mock Mode"** is checked in Settings (default)
2. Click **"Connect"** to connect to the mock controller
3. Select a job with a planned path
4. Click **"Start Mapping"**
5. Watch as vertices turn red to indicate visited positions
6. A completion dialog appears when mapping finishes

### Real Hardware Mode

1. Connect your Arduino/controller via USB
2. Uncheck **"Mock Mode"** in Settings
3. Select the serial port from the dropdown
4. Set the baud rate (default: 115200)
5. Click **"Connect"**
6. Proceed with mapping as above

## Serial Protocol

The application uses newline-delimited JSON for communication:

### PC → Controller

**MAP Command:**
```json
{"cmd":"MAP", "job_id":"job-123", "path":[[x,y,z],...], "meta":{"units":"mm","feedrate":50}}
```

**STOP Command:**
```json
{"cmd":"STOP"}
```

### Controller → PC

**Validation:**
```json
{"type":"VALIDATION", "status":"VALID"}
```

**Position Update:**
```json
{"type":"POS", "pos":[x,y,z], "t":1700000000}
```

**Progress:**
```json
{"type":"PROGRESS", "visited":123, "total":456}
```

**Complete:**
```json
{"type":"COMPLETE", "job_id":"job-123", "duration_s":300}
```

## Project Structure

```
adaptive_mold/
├── app/
│   ├── __main__.py        # Entry point with welcome screen
│   ├── welcome_screen.py  # Project welcome/info screen
│   ├── main_window.py     # Main GUI window
│   ├── view3d.py          # 3D wireframe widget
│   └── ui_helpers.py      # UI utility functions
├── core/
│   ├── step_loader.py     # STEP/mesh file loading (OCC + trimesh)
│   ├── path_planner.py    # Waypoint path planning
│   └── serial_manager.py  # Serial communication
├── models/
│   ├── db.py              # SQLAlchemy database models
│   └── schemas.py         # Pydantic message schemas
├── resources/
│   ├── mock_controller.py # Standalone mock controller
│   └── sample_geometry.json
└── data/
    └── adaptive_mold.db   # SQLite database (created at runtime)

build.py                   # Build script for creating executables
environment.yml            # Conda environment specification
```

## 3D View Controls

- **Left-click + drag**: Rotate view
- **Right-click + drag** or **Middle-click + drag**: Pan view
- **Mouse wheel**: Zoom in/out
- **R** or **Home**: Reset view to default

## Platform Notes

### Linux
- Serial ports are typically `/dev/ttyUSB0`, `/dev/ttyACM0`, etc.
- May need to add user to `dialout` group: `sudo usermod -a -G dialout $USER`

### Windows
- Serial ports are `COM1`, `COM2`, `COM3`, etc.
- Check Device Manager for the correct port number

## Development

### Run with debug logging:
```bash
python -m adaptive_mold.app
```

### Database location:
```
adaptive_mold/data/adaptive_mold.db
```

To reset the database, simply delete this file.

---

## Building Standalone Executables

The project includes a build script to create standalone executables for distribution.

### Prerequisites

Make sure PyInstaller and Pillow are installed:
```bash
conda install pyinstaller pillow -c conda-forge
```

### Build Commands

```bash
# Basic build (creates a directory with executable)
python build.py

# Build a single executable file
python build.py --onefile

# Build with a custom icon
python build.py --icon /path/to/icon.png

# Clean previous builds first
python build.py --clean

# Build with console for debugging
python build.py --console

# Combined: clean and build single file
python build.py --clean --onefile
```

### Build Output

After building, find your executable in:
- **Directory mode**: `dist/AdaptiveMold/AdaptiveMold`
- **Single file mode**: `dist/AdaptiveMold` (or `dist/AdaptiveMold.exe` on Windows)

### Platform-Specific Notes

| Platform | Icon Format | Executable |
|----------|-------------|------------|
| Linux    | `.png`      | `AdaptiveMold` |
| Windows  | `.ico`      | `AdaptiveMold.exe` |
| macOS    | `.icns`     | `AdaptiveMold.app` |

### Distributing

To distribute the application:

1. **Directory mode** (recommended for debugging):
   - Copy the entire `dist/AdaptiveMold/` folder
   - Users run the executable inside

2. **Single file mode** (simpler distribution):
   - Copy just the `dist/AdaptiveMold` executable
   - Slower startup (extracts files to temp directory)

---

## Troubleshooting

### STEP File Loading Issues

If STEP files fail to load:
1. Ensure pythonocc-core is installed: `conda list | grep pythonocc`
2. Check the console for error messages
3. Try exporting the model as STL/OBJ as a fallback

### Serial Connection Issues

**Linux:**
- Add user to dialout group: `sudo usermod -a -G dialout $USER`
- Log out and back in for changes to take effect

**Windows:**
- Check Device Manager for correct COM port
- Install appropriate USB drivers for your controller

### Application Won't Start

1. Ensure conda environment is activated: `conda activate eng`
2. Check Python version: `python --version` (should be 3.11.x)
3. Verify dependencies: `conda list`

---

## License

[Add your license here]

---

## Acknowledgments

- **pythonocc-core**: OpenCASCADE Python bindings for precise CAD geometry
- **PySide6**: Qt6 Python bindings for the GUI framework
- **trimesh**: Mesh processing library (fallback geometry loader)
- **SQLAlchemy**: Database ORM for job persistence
