from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import routers (will be created later)
# from app.api.documents import router as documents_router
# from app.api.query import router as query_router

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
    return {"status": "healthy"}

# Router registration (uncomment after creating routers)
# app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
# app.include_router(query_router, prefix="/api/v1/query", tags=["query"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)