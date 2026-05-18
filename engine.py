import requests
import json
from google import genai
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from typing import Dict, Any, List

class AddressEngine:
    def __init__(self):
        # Standard Google GenAI Production Client
        self.ai_client = genai.Client(api_key="AIzaSyDLwVxYJIRaZC1AqdxjGrZtbFAvHuGBkAY")
        
        self.geolocator = Nominatim(user_agent="nigeria_digital_address_pro_v11_strict")
        self.overpass_url = "http://overpass-api.de/api/interpreter"

    async def search_intelligence(self, query: str, user_lat: float, user_lon: float) -> List[Dict[str, Any]]:
        query = query.lower().strip()
        raw_suggestions = []

        # --- STEP 1: RESOLVE LOCAL ANCHORS ---
        current_city = "Local Area"
        try:
            current_location = self.geolocator.reverse((user_lat, user_lon), language='en')
            if current_location and 'address' in current_location.raw:
                addr = current_location.raw['address']
                current_city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('suburb') or "Oyo"
        except:
            pass

        # --- STEP 2: SEMANTIC REASONING LAYER (With Quota Protection) ---
        prompt = f"""
        User is in: {current_city} (Coordinates: {user_lat}, {user_lon}).
        Query: "{query}"

        Task: 
        1. Resolve commercial name (e.g. 'uba' -> UBA Bank).
        2. Create an optimized query bound strictly to {current_city}.
        
        Return JSON: {{"resolved_name": "Clean Name", "optimized_query": "Name, City, Nigeria"}}
        """
        
        try:
            response = self.ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            intent = json.loads(clean_text)
            resolved_title = intent.get("resolved_name", query)
            ai_query = intent.get("optimized_query", f"{query} {current_city}")
        except Exception as e:
            # If 429 Quota Exceeded happens, fail gracefully without crashing
            print(f"AI Quota or Parse Error: {e}")
            resolved_title = query.capitalize()
            ai_query = f"{query} {current_city}"

        # --- STEP 3: STRICT SEARCH PIPELINE ---
        search_strategies = [
            ai_query,
            f"{query} {current_city} Nigeria",
            f"{resolved_title} {current_city} Nigeria",
            f"{query} Nigeria"
        ]

        local_viewbox = [
            (user_lat + 0.3, user_lon - 0.3), 
            (user_lat - 0.3, user_lon + 0.3)
        ]

        for strategy in search_strategies:
            if not strategy:
                continue
            try:
                locations = self.geolocator.geocode(
                    strategy,
                    exactly_one=False,
                    limit=20,
                    viewbox=local_viewbox
                )
                
                if locations:
                    for loc in locations:
                        if not any(abs(s['lat'] - loc.latitude) < 0.0002 for s in raw_suggestions):
                            display_name = loc.address.split(',')[0]
                            if len(display_name) > 25:
                                display_name = resolved_title
                                
                            raw_suggestions.append(self._format_suggestion(
                                display_name,
                                loc.address,
                                loc.latitude,
                                loc.longitude,
                                user_lat,
                                user_lon
                            ))
            except:
                continue

        # --- STEP 4: THE IRON CURTAIN FILTER ---
        # HARD RULE: If it is more than 25 Kilometers away, DROP IT entirely.
        # This guarantees you will NEVER see Ilorin while sitting in Oyo.
        filtered_suggestions = [s for s in raw_suggestions if s['dist_km'] <= 25.0]

        return sorted(filtered_suggestions, key=lambda x: x['dist_km'])

    def _format_suggestion(self, name, addr, lat, lon, u_lat, u_lon) -> Dict[str, Any]:
        dist = round(geodesic((u_lat, u_lon), (lat, lon)).km, 2)
        return {
            "name": name,
            "address": addr,
            "lat": lat,
            "lon": lon,
            "dist_km": dist,
            "travel_times": {
                "walking": f"{round(dist * 12)} min",
                "driving": f"{round(dist * 4)} min"
            }
        }

    async def get_clean_address(self, lat: float, lon: float) -> Dict[str, Any]:
        try:
            location = self.geolocator.reverse((lat, lon), language='en', zoom=18)
            if not location: 
                return {"status": "error", "error": "Target coordinates could not be resolved."}

            raw = location.raw.get('address', {})
            landmark = (raw.get('university') or raw.get('amenity') or raw.get('place_of_worship') or raw.get('building'))
            road = raw.get('road')
            suburb = raw.get('suburb') or raw.get('neighbourhood') or raw.get('county')
            city = raw.get('city') or raw.get('town') or raw.get('village') or "Local Area"
            state = raw.get('state', '').replace(" State", "").strip()

            address_parts = [p for p in [landmark, road, suburb, city, state] if p]
            formatted = ", ".join(address_parts)
            intelligence = self._fetch_intelligence(lat, lon)

            return {
                "status": "success",
                "data": {
                    "formatted_address": formatted,
                    "postcode": raw.get('postcode') or self._estimate_postcode(formatted),
                    "city": city,
                    "intelligence": intelligence
                }
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _fetch_intelligence(self, lat: float, lon: float) -> Dict[str, Any]:
        query = f"""[out:json][timeout:15];(node["amenity"~"hospital|police|pharmacy"](around:2000, {lat}, {lon}););out body;"""
        try:
            res = requests.post(self.overpass_url, data={'data': query}).json().get('elements', [])
            services = [{"name": e.get('tags', {}).get('name', 'Public Facility'), "type": e.get('tags', {}).get('amenity')} for e in res if e.get('tags', {}).get('name')]
            return {"nearby_emergency": services[:5], "network_quality": {"primary": "MTN 4G (Strong)", "secondary": "Airtel 4G (Good)"}}
        except: 
            return {"nearby_emergency": [], "network_quality": {"primary": "MTN 4G", "secondary": "Airtel 4G"}}

    def _estimate_postcode(self, formatted: str) -> str:
        if "Ibadan" in formatted: return "200211"
        if "Lagos" in formatted: return "100001"
        if "Oyo" in formatted: return "211105"
        return "Nigeria"