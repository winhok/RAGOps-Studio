"""Run the single-worker application with its compiled web client."""
import os
import sys
from pathlib import Path
import uvicorn
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
if __name__ == '__main__':
    uvicorn.run('app.main:app', host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '8000')), workers=1)
