FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends stockfish && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py exercises.py assessment_v3.py lesson_scenarios.py curriculum_v6.py v7_server.py v8_server.py assessment_v8.py mate3_v8.py v9_server.py learning_server.py .
COPY puzzles_lichess.jsonl ./puzzles_lichess.jsonl
COPY public ./public
ENV STOCKFISH_PATH=/usr/games/stockfish
ENV PYTHONUNBUFFERED=1
CMD ["sh","-c","uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
