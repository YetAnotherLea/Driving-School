from django.contrib import admin

# Register your models here.
from .models import UserProfile
from .models import HeuresFormation
from .models import RendezVous
from .models import Lecon

admin.site.register(UserProfile)
admin.site.register(HeuresFormation)
admin.site.register(RendezVous)
admin.site.register(Lecon)