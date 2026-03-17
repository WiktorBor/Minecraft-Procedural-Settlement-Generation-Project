import requests
from typing import Optional, Dict, Any

class GDMCClient:
    """
    Simple HTTP client for GDMC server API.
    
    Parameters
    ----------
    base_url : str
        Base URL of the GDMC server (default: "http://localhost:9000").
    """
    def __init__(self, base_url="http://localhost:9000"):
        self.base_url = base_url

    def request(
            self, 
            method, 
            endpoint, 
            params=None, 
            data=None
            ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"

        r = requests.request(
            method=method,
            url=url,
            params=params,
            json=data,
        )

        r.raise_for_status()

        if r.text:
            return r.json()
        return None

    def get(self, endpoint, params=None) -> Optional[Dict[str, Any]]:
        return self.request("GET", endpoint, params=params)

    def put(self, endpoint, data=None) -> Optional[Dict[str, Any]]:
        return self.request("PUT", endpoint, data=data)

    def post(self, endpoint, data=None) -> Optional[Dict[str, Any]]:
        return self.request("POST", endpoint, data=data)
    
    def check_connection(self) -> bool:
        try:
            r = requests.options(f"{self.base_url}/")
            return r.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def check_build_area(self) -> bool:
        try:
            data = self.get("/buildarea")
            return data is not None and all(k in data for k in ["xFrom", "yFrom", "zFrom", "xTo", "yTo", "zTo"])
        except requests.exceptions.RequestException:
            return False