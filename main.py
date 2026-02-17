import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from database import init_db
from routes import router # Import the router we just made

load_dotenv()

app = FastAPI()

# Connect the routes
app.include_router(router)

@app.on_event("startup")
def on_startup():
    init_db()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)