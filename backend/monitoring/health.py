from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok", "service": "crowd-monitoring-backend"})

