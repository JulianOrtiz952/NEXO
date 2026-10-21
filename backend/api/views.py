from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({
        'status': 'ok',
        'message': '¡Hola desde Django! NEXO ya tiene conexión.',
        'service': 'NEXO API',
        'timestamp': timezone.now().isoformat(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def menu(request):
    import json
    from pathlib import Path
    products = json.loads(Path(__file__).with_name('menu.json').read_text(encoding='utf-8'))
    return Response({'products': products})
