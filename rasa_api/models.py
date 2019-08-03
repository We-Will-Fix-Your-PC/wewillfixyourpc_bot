from django.db import models


class Utterance(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class UtteranceResponse(models.Model):
    utterance = models.ForeignKey(Utterance, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    image = models.ImageField(blank=True)

    def __str__(self):
        return f"#{self.id}"


class UtteranceButton(models.Model):
    utterance = models.ForeignKey(Utterance, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    payload = models.CharField(max_length=255)
