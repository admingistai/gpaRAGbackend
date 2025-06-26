#!/bin/bash

# Website Indexing Script for Harbor RAG System
echo "🔍 Harbor Website Indexing Tool"
echo "==============================="

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend server is not running on port 8000"
    echo "💡 Please start the backend first with: ./start.sh"
    exit 1
fi

# Get current index stats
echo "📊 Current index status:"
curl -s http://localhost:8000/api/stats | python3 -m json.tool

echo ""
echo "🚀 Starting website indexing..."

# Index the website
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/index" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "http://localhost:3000"}')

echo "📝 Indexing response:"
echo "$RESPONSE" | python3 -m json.tool

# Get updated stats
echo ""
echo "📊 Updated index status:"
curl -s http://localhost:8000/api/stats | python3 -m json.tool

echo ""
echo "✅ Indexing complete! You can now ask questions about the website content." 