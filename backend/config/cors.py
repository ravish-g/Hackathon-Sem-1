from django.http import HttpResponse


LOCAL_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}


class LocalCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS" and origin in LOCAL_ORIGINS:
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if origin in LOCAL_ORIGINS:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = "Accept, Content-Type, X-CSRFToken"
            response["Access-Control-Allow-Methods"] = "DELETE, GET, OPTIONS, PATCH, POST, PUT"
            response["Vary"] = "Origin"
        return response
