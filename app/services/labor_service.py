from typing import Dict, Any, List
import random
import hashlib

class LaborService:
    @staticmethod
    async def decode_vin(vin: str) -> Dict[str, Any]:
        """Mock VIN decoding (simulating NHTSA / MOTOR info)"""
        # A simple deterministic mock based on the VIN string length/hash
        vin_upper = vin.upper()
        if len(vin_upper) != 17:
            return {"error": "Invalid VIN length (must be 17 chars)."}

        hasher = hashlib.md5(vin_upper.encode())
        hash_val = int(hasher.hexdigest(), 16)
        
        years = [2010, 2015, 2018, 2020, 2022, 2024]
        makes = ["Honda", "Toyota", "Ford", "Chevrolet", "BMW", "Audi"]
        models = {
            "Honda": ["Civic", "Accord", "CR-V"],
            "Toyota": ["Camry", "Corolla", "RAV4"],
            "Ford": ["F-150", "Mustang", "Explorer"],
            "Chevrolet": ["Silverado", "Malibu", "Equinox"],
            "BMW": ["328i", "X5", "M3"],
            "Audi": ["A4", "Q5", "S4"]
        }
        engines = ["2.0L 4-Cyl", "3.5L V6", "5.0L V8", "Electric"]

        make = makes[hash_val % len(makes)]
        model = models[make][(hash_val // 2) % len(models[make])]
        year = years[(hash_val // 3) % len(years)]
        engine = engines[(hash_val // 4) % len(engines)]

        return {
            "vin": vin_upper,
            "year": year,
            "make": make,
            "model": model,
            "engine": engine
        }

    @staticmethod
    async def lookup_labor(query: str, vin: str) -> List[Dict[str, Any]]:
        """Mock MOTOR/ProDemand standard labor time lookup"""
        q = query.lower()
        results = []
        
        # We will generate deterministic mock hours
        base_hours = max(0.5, float(len(q)) / 10.0)

        results.append({
            "operation": f"Replace {query.title()}",
            "description": f"Standard replacement of {query.lower()} (OEM procedure)",
            "hours": round(base_hours * 1.5, 1)
        })
        results.append({
            "operation": f"Inspect and Replace {query.title()}",
            "description": f"Includes diagnostic time and replacement of {query.lower()}",
            "hours": round((base_hours * 1.5) + 1.0, 1)
        })

        return results
