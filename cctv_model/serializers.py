from rest_framework import serializers

class ImageSerializer(serializers.Serializer):
    url = serializers.CharField()
    last_modified = serializers.DateTimeField()
    image_date = serializers.DateField()
