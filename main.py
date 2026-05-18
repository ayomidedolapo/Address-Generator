from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from engine import AddressEngine

# Initialize the app
app = FastAPI(
    title="Address Pro | Intelligent Search & Geocoding",
    description="Backend engine for real-time location intelligence and routing.",
    version="2.0.0"
)

# Initialize our custom logic from engine.py
engine = AddressEngine()

# Enable CORS so your HTML file can communicate with this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Address Pro API is active.",
        "endpoints": {
            "generate": "/api/v1/generate",
            "search": "/api/v1/search"
        }
    }

@app.get("/api/v1/generate")
async def generate(
    lat: float = Query(..., description="Latitude of the target location"),
    lon: float = Query(..., description="Longitude of the target location")
):
    """
    Reverse geocodes coordinates into a professional address 
    and fetches local intelligence (Safety, Landmarks, Network).
    """
    result = await engine.get_clean_address(lat, lon)
    
    if "error" in result:
        return {"status": "error", "message": result["error"]}
    
    return result

@app.get("/api/v1/search")
async def search(
    query: str = Query(..., description="The place or category to search for"),
    lat: float = Query(..., description="User's current latitude for proximity sorting"),
    lon: float = Query(..., description="User's current longitude for proximity sorting")
):
    """
    FIXED: Handles the new Search Intelligence feature.
    Finds specific names (UBA Bank) or categories (Restaurants) near the user.
    """
    results = await engine.search_intelligence(query, lat, lon)
    
    # Return the list of suggestions directly to the frontend
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)