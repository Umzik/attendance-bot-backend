from django.contrib import admin

from attendance.models import User, Attendance, OfficeLocation

admin.site.register(User)
admin.site.register(Attendance)

admin.site.register(OfficeLocation)