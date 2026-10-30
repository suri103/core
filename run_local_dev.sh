#!/bin/bash

# CoreDent Local Development Runner
# Runs both backend and frontend in the same terminal

echo "🚀 Starting CoreDent Local Development..."
echo ""
echo "Backend: http://localhost:8080"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Start backend
echo "📦 Starting Backend..."
cd coredent-api
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Frontend..."
cd coredent-style-main
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Both services are running!"
echo ""
echo "Login credentials:"
echo "  Email: admin@coredent.com"
echo "  Password: Admin123!@#"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
