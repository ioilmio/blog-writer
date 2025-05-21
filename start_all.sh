#!/bin/bash
# Start all required services and the blog post generation script, each in a new terminal window

# Start Ollama server in a new terminal if not already running
if ! pgrep -f "ollama serve" > /dev/null; then
  echo "[INFO] Starting Ollama server in new terminal..."
  gnome-terminal -- bash -c "ollama serve"
  sleep 2
else
  echo "[INFO] Ollama server already running."
fi

# Start FastAPI backend in a new terminal if not already running
if ! pgrep -f "uvicorn backend.main:app" > /dev/null; then
  echo "[INFO] Starting FastAPI backend in new terminal..."
  gnome-terminal -- bash -c "uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
  sleep 2
else
  echo "[INFO] FastAPI backend already running."
fi

# Start the blog post generation script in a new terminal
# (runs in foreground so you can see progress)
echo "[INFO] Running blog post generation script in new terminal..."
gnome-terminal -- bash -c "python3 generate_all_blog_posts.py; exec bash"
