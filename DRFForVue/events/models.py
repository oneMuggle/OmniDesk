from django.db import models
from users.models import CustomUser

class Experiment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    responsible_persons = models.ManyToManyField(CustomUser)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Personnel(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50)
    email = models.EmailField()
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='personnels')

    def __str__(self):
        return f"{self.name} ({self.role})"

class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class DocumentTemplate(models.Model):
    EXPERIMENT_TYPES = [
        ('chemical', '化学实验'),
        ('biological', '生物实验'),
        ('physical', '物理实验'),
    ]
    
    name = models.CharField(max_length=100)
    experiment_type = models.CharField(max_length=20, choices=EXPERIMENT_TYPES)
    template_file = models.FileField(upload_to='templates/')
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.name} ({self.get_experiment_type_display()})"
