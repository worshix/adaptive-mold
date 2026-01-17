# Prompt for VS Code AI — **Adaptive Mold** (clean, prototype-focused)

Use this file as `Prompt.md` in the repo. The goal is to bootstrap a **working demo/prototype** for **Adaptive Mold**: a PySide6 GUI that loads a STEP file (or fallback sample geometry), extracts vertices, displays a 3D wireframe, computes a mapping path (waypoints) using `scipy`/`numpy`, stores jobs in a local SQLite database, and sends the path to a controller over serial (Arduino). The system must include a **mock controller** so the demo runs without physical hardware.

> Note: You mentioned using a non-pip environment (you wrote “python uv”). Replace `pip` install steps below with whichever package manager/installer your environment uses — the package list is the important part.

---

## One-sentence goal

A minimal PySide6 desktop prototype demonstrating STEP→vertices→wireframe→path planner→serial send loop, persisted to an SQLite file, with a mock controller for demo runs.

---

## Minimal libraries (install with your environment)

* `PySide6` — GUI and Qt 3D or widgets
* `trimesh` — lightweight STEP/mesh loading for prototyping (fallback to sample geometry if STEP fails)
* `numpy`
* `scipy`
* `pyserial` — serial comms with Arduino
* `sqlalchemy` — SQLite ORM (or use stdlib `sqlite3` if you prefer)
* `pydantic` — optional, for message validation
* `loguru` (or `logging`) — debugging serial traffic / app flow

Example (if you *do* use pip just as an example):

```bash
pip install PySide6 trimesh numpy scipy pyserial sqlalchemy pydantic loguru
```

(If you do not use `pip`, adapt the list to your environment installer — the AI should not hardcode use of `pip`.)

---

## Simplifications made for this prototype

* Use `trimesh` instead of `pythonocc-core` to avoid heavy, slow installs — `trimesh` is good for demoing vertex extraction and wireframes. Add `pythonocc-core` later for engineering-grade STEP fidelity.
* No HTTP server (removed `fastapi`/`uvicorn`) — the GUI is the app surface for the demo.
* Keep tests minimal (optional) — focus on a working end-to-end mock loop.
* SQLite file database only (no remote DB). Keep schema tiny.

---

## Project skeleton (minimal)

```
adaptive_mold/
├─ app/
│  ├─ __main__.py        # entry point
│  ├─ main_window.py     # MainWindow, dashboard, settings, status bar
│  ├─ view3d.py          # 3D widget (Qt3D or fallback)
│  └─ ui_helpers.py
├─ core/
│  ├─ step_loader.py     # load_step(path) -> vertices, edges, metadata
│  ├─ path_planner.py    # waypoint sequencing (greedy + sampling)
│  └─ serial_manager.py  # RealSerialManager + MockSerialManager
├─ models/
│  ├─ db.py              # SQLAlchemy engine & models (Job, JobGeometry, Waypoint)
│  └─ schemas.py         # Pydantic message schemas (optional)
├─ resources/
│  ├─ sample_geometry.json
│  └─ mock_controller.py # CLI mock controller for demo
├─ data/
│  └─ adaptive_mold.db   # SQLite DB (created at runtime)
├─ requirements.txt OR pyproject.toml
└─ README.md
```

---

## Database (SQLite) basics

* DB file: `data/adaptive_mold.db`
* Minimal SQLAlchemy models:

  * `Job` — id (uuid/text), name, filename, created_at, status, planner_params (JSON)
  * `JobGeometry` — job_id FK, vertex_index, x, y, z
  * `Waypoints` — job_id FK, index, x, y, z, visited (bool)
* Use simple migrations or recreate schema on startup for the prototype.

---

## UI / UX (prototype requirements)

1. **Dashboard**: job list (loaded from SQLite), Create New Job button, status bar messages.
2. **Create Job**:

   * File selector for `.step`/`.stp` (if parsing fails, offer `resources/sample_geometry.json`).
   * Parse and store vertices in DB and show metadata (vertex count, bounding box).
   * Show **Start Mapping** button once job created.
3. **Settings**:

   * COM port dropdown (auto-populate via `serial.tools.list_ports`).
   * Baud rate input, Mock Mode toggle (must default to Mock for demos).
   * Note: App is developed on Linux; show Windows COM example (COM3) in the UI tooltip.
4. **3D Wireframe View**:

   * Wireframe only (edges). Allow rotate/pan/zoom.
   * Realtime highlighting: edges/vertices visited turn red as controller reports positions.
   * Show small overlay with vertex index and coordinate on hover/click.
5. **Mapping workflow**:

   * When **Start Mapping** pressed: compute path, send MAP message to controller (mock or real).
   * Status bar shows messages from controller (`VALID`, `mapping`, `done`).
   * During mapping, update UI from serial POS messages (color visited parts red).

---

## Minimal serial protocol (newline-delimited JSON — easiest to debug)

**PC → Controller**

```json
{"cmd":"MAP", "job_id":"job-123", "path":[[x,y,z],[x,y,z], ...], "meta":{"units":"mm", "feedrate":50}}
```

**Controller → PC**

* Validation:

```json
{"type":"VALIDATION", "status":"VALID"}
```

* Position update:

```json
{"type":"POS", "pos":[x,y,z], "t":1700000000}
```

* Progress/Complete:

```json
{"type":"PROGRESS","visited":123,"total":456}
{"type":"COMPLETE","job_id":"job-123","duration_s":300}
```

`pydantic` schemas in `models/schemas.py` are recommended for validating messages.

---

## Path planning (prototype)

* Use `numpy` and `scipy.spatial.distance` for building distance matrices.
* Implement a **greedy nearest-neighbor** planner (fast to write and deterministic) as baseline:

  * Input: list of vertices (N x 3)
  * Output: ordered list of waypoints
* Provide a simple **edge-sampling** mode: sample points along edges at fixed spacing to get denser coverage.
* Keep planner modular so it can be swapped later.

---

## Mock controller (required for demo)

* `resources/mock_controller.py`:

  * Accepts MAP JSON (stdin / TCP / pseudo-serial).
  * Validates coordinates against a bounding box (return VALID or ERROR).
  * Simulates motion by sending `POS` updates at a configurable interval (simulate 10–50 Hz).
  * Sends `COMPLETE` when done.
* GUI must support `mock://` connection or a "Mock Mode" that starts an internal thread to simulate incoming messages.

---

## Acceptance criteria for the demo (must be minimal and achievable)

1. App launches and shows a dashboard with either parsed STEP geometry or a sample wireframe fallback.
2. Create Job flow persists job & vertices to the SQLite DB.
3. `PathPlanner` returns an ordered list of waypoints for a job.
4. `SerialManager` supports:

   * Mock mode (connect to `MockSerialManager`) and
   * Real mode (pyserial), but mock is default for the demo.
5. Pressing **Start Mapping** while mock mode is active:

   * App sends MAP JSON to mock controller
   * Mock replies VALID
   * Mock streams POS updates and APP updates the 3D wireframe (visited items colored red)
   * App receives COMPLETE and updates status bar
6. Simple instructions in README explaining how to run the mock controller and GUI on Linux (with Windows COM examples).

---

## First tasks for the AI developer (concrete checklist)

1. Create project skeleton above.
2. Add `requirements.txt` (or `pyproject.toml`) listing the minimal packages.
3. Implement `models/db.py` with SQLAlchemy SQLite setup and the minimal models (Job, JobGeometry, Waypoint).
4. Implement `core/step_loader.py` using `trimesh.load()` for STEP or fallback JSON.
5. Implement `core/path_planner.py` with greedy planner + edge sampling mode.
6. Implement `core/serial_manager.py` with `RealSerialManager` (pyserial) and `MockSerialManager` (internal threads/async).
7. Implement `app/__main__.py` + `main_window.py` + `view3d.py`:

   * Minimal Qt app with Dashboard, Settings, 3D view, status bar, Create Job dialog.
   * Wireframe rendering and realtime highlight updates.
8. Implement `resources/mock_controller.py`.
9. Provide README with run instructions (Linux) and a short line describing Windows COM port names.
10. Keep commits small, with descriptive commit messages.

---

## DEV notes & tips for the AI

* Use Qt `QThread` or `QRunnable` + signals to handle serial read loops; never block the main thread.
* Keep STEP parsing optional: if `trimesh` raises or format unsupported, load `resources/sample_geometry.json`.
* Store job geometry in SQLite so the demo can show persistence across restarts.
* Default to Mock Mode for first demo runs.
* Keep the 3D view simple; the demo should prioritize correct path visualization and real-time updates, not photorealism.
* Keep the serial protocol text-based (JSON) — easiest to debug with `cat`/`screen` or the mock controller logs.

---
