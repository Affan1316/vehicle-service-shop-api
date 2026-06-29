from fastapi import FastAPI

app = FastAPI(title="Vehicle Service Shop API")

@app.get("/")
async def root():
    return {"message": "Welcome to the Vehicle Service Shop API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
