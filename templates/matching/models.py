from django.db import models

class UserProfile(models.Model):
    nickname = models.CharField(max_length=30)
    age_range = models.CharField(max_length=10)
    area = models.CharField(max_length=20)
    purpose = models.CharField(max_length=10)

    def __str__(self):
        return self.nickname
