import requests

class GDMCClient:
    def __init__(self, base_url="http://localhost:9000"):
        self.base_url = base_url

    def request(self, method, endpoint, params=None, data=None):
        url = f"{self.base_url}{endpoint}"

        r = requests.request(
            method=method,
            url=url,
            params=params,
            json=data,
            timeout=5
        )

        r.raise_for_status()

        if r.text:
            return r.json()
        return None

    def get(self, endpoint, params=None):
        return self.request("GET", endpoint, params=params)

    def put(self, endpoint, data=None):
        return self.request("PUT", endpoint, data=data)

    def post(self, endpoint, data=None):
        return self.request("POST", endpoint, data=data)
    
    def check_connection(self):
        try:
            r = requests.options(f"{self.base_url}/")
            return r.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def check_build_area(self):
        try:
            data = self.get("/buildarea")
            return data is not None and all(k in data for k in ["xFrom", "yFrom", "zFrom", "xTo", "yTo", "zTo"])
        except requests.exceptions.RequestException:
            return False