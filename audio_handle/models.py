from django.db import models

# Create your models here.

class Audio(models.Model):
    file_name = models.CharField(max_length=64)
    md5 = models.CharField(max_length=32)
    target = models.ForeignKey(
        'Demo',
        on_delete=models.CASCADE,
    )

class Demo(models.Model):
    name = models.CharField(max_length=64)
    file_name = models.CharField(max_length=64)
