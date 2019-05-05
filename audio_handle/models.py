from django.db import models

# Create your models here.

class Audio(models.Model):
    file_name = models.CharField(max_length=64)
    md5 = models.CharField(max_length=32)
    target = models.ForeignKey(
        'Demo',
        on_delete=models.CASCADE,
    )
    task_id = models.CharField(max_length=64)

class Demo(models.Model):
    file_name = models.CharField(max_length=64)
    name = models.CharField(max_length=20)
    artist = models.CharField(max_length=20)
    lyric = models.TextField()
    accompaniment_url = models.TextField()
    offset = models.FloatField()

# class Lyric(models.Model)

