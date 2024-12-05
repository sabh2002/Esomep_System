from rest_framework import serializers
from rest_framework.views import APIView  # Importa APIView
from rest_framework.response import Response  # Importa Response
from .models import Bienes, Stock

class BienesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bienes
        fields = ['id', 'nombre']  # Incluye otros campos relevantes

class StockSerializer(serializers.ModelSerializer):
    bien = BienesSerializer(source='bien_id', read_only=True)

    class Meta:
        model = Stock
        fields = ['id_stock', 'bien', 'cantidad_total', 'cantidad_disponible', 'cantidad_asignada',
                  'cantidad_prestada', 'cantidad_en_mantenimiento', 'cantidad_desincorporada',
                  'cantidad_resguardada']
        
class MessageSerializer(serializers.Serializer):
    destinatario_id = serializers.IntegerField()
    contenido = serializers.CharField()

class SendMessageView(APIView):
    def post(self, request):
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            # lógica para enviar el mensaje
            return Response({"message": "Mensaje enviado"})
        return Response(serializer.errors, status=400)
