from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, papers, chat, workspaces, ai
from database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ResearchHub AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],  # Vite default port is 5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(papers.router)
app.include_router(chat.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    return {"message": "ResearchHub AI API is running"}
