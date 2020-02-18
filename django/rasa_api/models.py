from django.db import models
import operator_interface.models


class Utterance(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class UtteranceResponse(models.Model):
    utterance = models.ForeignKey(Utterance, on_delete=models.CASCADE)
    text = models.TextField(blank=True, null=True)
    custom_json = models.TextField(blank=True, null=True)
    image = models.ImageField(blank=True, null=True)

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
    conversation = models.ForeignKey(operator_interface.models.Conversation, on_delete=models.CASCADE)
    rasa_url = models.URLField()

    def __str__(self):
        return str(self.conversation)
