#!/bin/bash

# Harbor RAG Backend Startup Script
echo "🚀 Starting Harbor RAG Backend"
echo "==============================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env template..."
    cat > .env << 'EOF'
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Frontend URL (where your Next.js app runs)
FRONTEND_URL=http://localhost:3000

# Backend Configuration
BACKEND_PORT=8000

# Vector Database
CHROMA_PERSIST_DIRECTORY=./chroma_db
EOF
    echo -e "${RED}❌ Please edit .env file and add your OPENAI_API_KEY${NC}"
    echo "Then run this script again."
    exit 1
fi

# Load environment variables
source .env

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY not set in .env file${NC}"
    echo "Please edit .env and add your OpenAI API key"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}🐍 Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install -r requirements.txt

# Check if port is available
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}❌ Port $BACKEND_PORT is already in use${NC}"
    echo "Please stop the service or change BACKEND_PORT in .env"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Start backend
echo -e "${GREEN}🚀 Starting Harbor RAG API server...${NC}"
echo -e "${BLUE}📊 Vector database: $CHROMA_PERSIST_DIRECTORY${NC}"
echo -e "${BLUE}🌐 Frontend URL: $FRONTEND_URL${NC}"
echo -e "${BLUE}🔧 Backend API: http://localhost:$BACKEND_PORT${NC}"
echo -e "${BLUE}📚 API Documentation: http://localhost:$BACKEND_PORT/docs${NC}"
echo ""
echo -e "${YELLOW}💡 Make sure your frontend is running on $FRONTEND_URL${NC}"
echo -e "${YELLOW}🛑 Press Ctrl+C to stop the server${NC}"
echo ""

# Start the server
python run.py 