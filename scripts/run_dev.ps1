$env:PYTHONPATH = (Resolve-Path ".").Path
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
