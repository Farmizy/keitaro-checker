#!/bin/bash
set -e

echo "=== FB Budget Manager — Deploy ==="

# 1. Check Docker
if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker not installed"
  exit 1
fi

# 2. Check .env files
if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Copy from backend/.env.example and fill in."
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env not found (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY). Copy from .env.example and fill in."
  exit 1
fi

# 3. Build and start
echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "=== Done ==="
echo "Frontend: http://$(hostname -I | awk '{print $1}')"
echo "Backend API: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "Health: http://$(hostname -I | awk '{print $1}'):8000/health"
echo ""
echo "Logs: docker compose logs -f"
