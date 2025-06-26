#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BACKEND_URL="http://localhost:8000"

echo -e "${GREEN}🔍 Inspecting Harbor RAG System${NC}"
echo "=========================================="

# Check if backend is running
echo -e "${BLUE}📡 Checking backend status...${NC}"
if ! curl -s "$BACKEND_URL/health" > /dev/null; then
    echo -e "${RED}❌ Backend not running at $BACKEND_URL${NC}"
    echo "Please start the backend first with: ./start.sh"
    exit 1
fi

echo -e "${GREEN}✅ Backend is running${NC}"
echo

# Get index stats
echo -e "${BLUE}📊 Index Statistics:${NC}"
curl -s "$BACKEND_URL/api/stats" | python3 -m json.tool
echo

# Discover URLs
echo -e "${BLUE}🕸️  Discovered URLs:${NC}"
curl -s "$BACKEND_URL/api/discover" | python3 -m json.tool
echo

# Get stored documents
echo -e "${BLUE}📄 All Stored Documents:${NC}"
curl -s "$BACKEND_URL/api/documents?limit=100" | python3 -c "
import json
import sys

data = json.load(sys.stdin)
if data.get('success'):
    print(f\"Total documents: {data['total_count']}\")
    print(\"=\" * 80)
    for i, doc in enumerate(data['documents'], 1):
        print(f\"Document {i}:\")
        print(f\"  ID: {doc['id']}\")
        print(f\"  Source URL: {doc['source_url']}\")
        print(f\"  Content Length: {len(doc['full_text'])} characters\")
        print(f\"  Content:\")
        # Print the full content with proper indentation
        content_lines = doc['full_text'].split('\n')
        for line in content_lines[:20]:  # Show first 20 lines
            print(f\"    {line}\")
        if len(content_lines) > 20:
            print(f\"    ... ({len(content_lines) - 20} more lines)\")
        print(\"=\" * 80)
        print()
else:
    print(f\"Error: {data.get('message', 'Unknown error')}\")
"

echo -e "${YELLOW}💡 Tips:${NC}"
echo "- Documents are chunked into 512-character pieces"
echo "- Multiple documents from one URL = the page was split into chunks"
echo "- To see all documents: curl -s '$BACKEND_URL/api/documents?limit=100'"
echo "- To test a query: curl -X POST '$BACKEND_URL/api/chat' -H 'Content-Type: application/json' -d '{\"question\":\"your question\"}'" 