from django.conf import settings
from rest_framework.permissions import BasePermission


def get_client_ip(request):
    """To'g'ridan-to'g'ri ulanish IP'si (REMOTE_ADDR — TCP darajasida soxtalashtirib bo'lmaydi).
    Proksi (ngrok/Cloudflare) orqasida bu proksi IP'si bo'ladi — o'shani allowlist qiling."""
    return request.META.get('REMOTE_ADDR', '')


class IsTrustedServer(BasePermission):
    """Faqat sozlangan ishonchli IP'lardan (o'yin serveri) ruxsat beradi.
    settings.TRUSTED_SERVER_IPS bo'sh bo'lsa — cheklov yo'q (token baribir talab qilinadi)."""
    message = "Bu endpoint faqat ishonchli server IP'sidan ruxsat etilgan."

    def has_permission(self, request, view):
        allowed = settings.TRUSTED_SERVER_IPS
        if not allowed:
            return True
        return get_client_ip(request) in allowed
