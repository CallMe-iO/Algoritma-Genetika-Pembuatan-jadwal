# Genetic Algorithm Course Timetabling

A FastAPI microservice that runs a penalty-based genetic algorithm (GA) to build conflict-free course timetables. Upload a CSV/XLSX dataset, tune GA parameters, and download the optimized schedule as JSON, CSV, or PDF. A simple HTML front-end (served at `/`) provides upload and run buttons.

## Requirements
- Python 3.11+
- pip
- (Optional) Docker / Docker Compose v2

## Local Development
- **Windows:**
  ```bat
  run_local.bat
  ```
- **Linux / macOS:**
  ```bash
  chmod +x run_local.sh
  ./run_local.sh
  ```
Both scripts install dependencies from `requirements.txt`, start `uvicorn`, and open `http://127.0.0.1:8000/` in your browser.

## Docker
```bash
docker build -t ga-scheduler .
docker run --rm -p 8000:8000 ga-scheduler
```
Or use Compose (hot reload not included):
```bash
docker compose up --build
```

## API Reference & cURL Samples
### `/health`
```bash
curl http://127.0.0.1:8000/health
```

### `/optimize/json`
```bash
curl -X POST http://127.0.0.1:8000/optimize/json \
  -F "file=@sample_penjadwalan.csv" \
  -F "pop_size=60" -F "gens=200" \
  -F "cx_rate=0.8" -F "mut_rate=0.2" -F "seed=42"
```

### `/optimize/csv`
```bash
curl -X POST http://127.0.0.1:8000/optimize/csv \
  -F "file=@sample_penjadwalan.csv" \
  -o jadwal_hasil.csv
```

### `/optimize/pdf`
```bash
curl -X POST http://127.0.0.1:8000/optimize/pdf \
  -F "file=@sample_penjadwalan.csv" \
  -o hasil_run_penjadwalan.pdf
```

## Dataset Schema (CSV / XLSX)
Columns must appear exactly as listed:
| Column      | Description                                      |
|-------------|--------------------------------------------------|
| Hari        | Initial day label (Senin..Sabtu)                 |
| MataKuliah  | Course name                                      |
| SKS         | Credit load (1, 2, or 3)                         |
| SMT         | Semester / cohort number (1–7)                   |
| Kelas       | Section label (e.g., A or B)                     |
| Dosen       | Lecturer name                                    |

The engine schedules every row as a distinct gene while respecting hard constraints (room/lecturer/cohort overlap prevention, DLB lecturer restrictions, operating hours) and soft objectives (compact cohort days + fewer teaching days).

Use `sample_penjadwalan.csv` for a ready-to-run dataset covering SMT {1,3,5,7} with both A/B sections and DLB lecturers.
