from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import routers
from app.api.documents import router as documents_router

app = FastAPI(
    title="RAG System API",
    description="Retrieval-Augmented Generation System with Qdrant/PostgreSQL",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "RAG System API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": True,
        "vector_store": True,
        "models_loaded": ["parser_test"]
    }

# Health check router (global)
@app.get("/api/v1/health")
async def api_health_check():
    return {
        "status": "healthy",
        "database": True,
        "vector_store": True,
        "models_loaded": ["parser_test"]
    }

# Router registration
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099)