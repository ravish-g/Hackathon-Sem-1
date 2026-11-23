from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer


class IgnoreClientContentNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        for renderer in renderers:
            if isinstance(renderer, JSONRenderer):
                return renderer, renderer.media_type
        return renderers[0], renderers[0].media_type
