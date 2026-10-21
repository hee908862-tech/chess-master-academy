FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends stockfish && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Optional local/corporate CA bundle; never persist it in an image layer.
RUN --mount=type=secret,id=pip_ca_bundle \
    if [ -f /run/secrets/pip_ca_bundle ]; then export PIP_CERT=/run/secrets/pip_ca_bundle; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY skill_index.py diagnostic_replay.py board_facts.py education_content.py education_server.py repertoire_content.py repertoire_server.py puzzle_challenge.py foundation_content.py foundation_server.py server.py exercises.py assessment_v3.py lesson_scenarios.py curriculum_v6.py v7_server.py v8_server.py assessment_v8.py mate3_v8.py v9_server.py learning_server.py assistance.py mate_explanation.py competencies.py journey_server.py onboarding_server.py build_journey_index.py journey_evidence.py growth_model.py game_analysis.py app_rating.py engine_budget.py study_server.py opening_courses.py .
COPY puzzles_lichess.jsonl ./puzzles_lichess.jsonl
RUN python build_journey_index.py
COPY public ./public
COPY data/openings ./data/openings
ENV STOCKFISH_PATH=/usr/games/stockfish
ENV PYTHONUNBUFFERED=1
CMD ["sh","-c","exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
