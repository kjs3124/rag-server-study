# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Python/FastAPI)
```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run development server
python main.py
# Server starts on http://127.0.0.1:8099
# API docs available at http://127.0.0.1:8099/docs

# Install development dependencies
pip install -r requirements-dev.txt
```

### Frontend (React/TypeScript)
```bash
# Install dependencies
cd frontend
npm install

# Development server
npm run dev

# Build for production
npm run build

# Lint TypeScript files
npm run lint

# Preview build
npm run preview
```

### Docker Deployment
```bash
# Start all services
docker-compose up

# Background start
docker-compose up -d

# Stop services
docker-compose down
```

## Architecture Overview

### System Design
This is a **Retrieval-Augmented Generation (RAG) system** with the following key components:

- **Multi-language document processing** with format-specific parsers
- **Adaptive embedding models** based on language detection
- **Dual vector database support** (Qdrant + PostgreSQL/pgvector)
- **2-stage retrieval** with vector search + reranking
- **FastAPI backend** with comprehensive document management
- **React frontend** with drag-drop upload interface

### Document Processing Pipeline
```
Document Upload/URL → Parser Selection → Language Detection → Embedding Model Selection
    ↓
Chunk Embedding → Vector DB Storage → Query Processing → Vector Search (Top-20)
    ↓
Reranking (Top-5) → LLM Context → Answer Generation
```

### Parser Factory Pattern
The system uses a factory pattern for document processing:
- **PDF**: PyMuPDF + pdfplumber fallback
- **DOCX/DOC**: python-docx
- **Excel**: openpyxl with sheet-based processing
- **PowerPoint**: python-pptx with slide-based chunking
- **Web**: requests-html + Playwright for dynamic content
- **Text formats**: TXT, HTML, Markdown, CSV with encoding detection

### Embedding Strategy
Dynamic model selection based on language composition:
- **BGE-M3**: For Korean > 60% or CJK languages > 40%
- **Multilingual-E5-Large**: For English > 60% or mixed documents

### Key Directories
- `backend/app/services/parsers/`: Document parser implementations
- `backend/app/api/documents.py`: Main API endpoints for document operations
- `backend/app/services/document_processor.py`: Core processing orchestration
- `frontend/src/components/`: React UI components
- `frontend/src/services/api.ts`: API client with TypeScript types
- `docs/`: Architecture and implementation documentation

### Database Architecture
- **Primary Vector DB**: Qdrant (preferred for performance)
- **Alternative**: PostgreSQL + pgvector extension
- **Metadata**: Document info, chunks, processing status stored in-memory (development) or PostgreSQL (production)
- **Caching**: Redis for embedding and processing optimization

### API Design
REST API with comprehensive OpenAPI documentation:
- `POST /api/v1/documents/upload`: File upload and processing
- `POST /api/v1/documents/url`: Web crawling
- `GET /api/v1/documents`: List all documents
- `GET /api/v1/documents/{id}`: Get document details and chunks
- `DELETE /api/v1/documents/{id}`: Remove document and vectors
- `POST /api/v1/documents/query`: RAG-based question answering
- `GET /health`: System health check

### Configuration
Environment variables:
- `DATABASE_URL`: PostgreSQL connection
- `QDRANT_URL`: Qdrant server endpoint
- `REDIS_URL`: Redis cache server
- Various API keys for embedding models and LLMs

The system is designed for multilingual document processing with Korean/English optimization, supporting enterprise-scale deployment through containerization and horizontal scaling capabilities.