from django.db import models
import operator_interface.models


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


class EnvironmentModel(models.Model):
    name = models.CharField(max_length=255)
    rasa_model = models.FileField()

    def __str__(self):
        return self.name


class TestingUser(models.Model):
    sender_id = models.CharField(max_length=255)
    environment = models.ForeignKey(EnvironmentModel, on_delete=models.CASCADE)

    def __str__(self):
        return self.sender_id
