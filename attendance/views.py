import io
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Attendance
from django.utils import timezone
from rest_framework.views import APIView
from django.http import HttpResponse
from .models import Attendance
import pandas as pd
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from math import radians, cos, sin, asin, sqrt

def haversine(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of Earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r


class CheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Retrieve location data from the request
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        if latitude is None or longitude is None:
            return Response({"message": "Location is required."}, status=400)

        # Office location
        office_latitude = settings.OFFICE_LATITUDE
        office_longitude = settings.OFFICE_LONGITUDE
        office_radius = 0.5  # in kilometers (e.g., 500 meters)

        # Calculate the distance between the user's location and the office
        distance = haversine(float(latitude), float(longitude), office_latitude, office_longitude)
        
        if distance > office_radius:
            return Response({"message": "You are too far from the office to check in."}, status=400)

        # Check if the user has already checked in today
        attendance, created = Attendance.objects.get_or_create(
            employee=request.user,
            checkin_time__date=timezone.now().date()
        )
        if created:
            attendance.checkin_time = timezone.now()
            attendance.save()
            return Response({"message": "Check-in successful!"})
        else:
            return Response({"message": "Already checked in today!"}, status=400)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Retrieve location data from the request
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if latitude is None or longitude is None:
            return Response({"message": "Location is required."}, status=400)

        # Office location
        office_latitude = settings.OFFICE_LATITUDE
        office_longitude = settings.OFFICE_LONGITUDE
        office_radius = 0.5  # in kilometers

        # Calculate the distance between the user's location and the office
        distance = haversine(float(latitude), float(longitude), office_latitude, office_longitude)
        
        if distance > office_radius:
            return Response({"message": "You are too far from the office to check out."}, status=400)

        # Handle the checkout logic
        try:
            attendance = Attendance.objects.filter(
                employee=request.user,
                checkin_time__date=timezone.now().date()
            ).latest('checkin_time')
            if attendance.checkout_time:
                return Response({"message": "Already checked out!"}, status=400)
            attendance.checkout_time = timezone.now()
            attendance.save()
            return Response({"message": "Check-out successful!"})
        except Attendance.DoesNotExist:
            return Response({"message": "No check-in found!"}, status=400)

class AdminReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"User role: {request.user.role}")
        print(request)
        if request.user.role != 'admin':
            return Response({"message": "Permission denied."}, status=403)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str and end_date_str:
            start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = timezone.datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            return Response({"message": "Please provide both start_date and end_date."}, status=400)

        response = self.generate_excel_report(start_date, end_date)
        return response

    def generate_excel_report(self, start_date, end_date):
        records_by_date = {}

        # Collecting records for each day within the range
        for single_date in pd.date_range(start=start_date, end=end_date):
            records = Attendance.objects.filter(checkin_time__date=single_date)
            data = [
                {
                    'Employee': record.employee.first_name + " " + record.employee.last_name,
                    'Check-in Time': record.checkin_time.astimezone(timezone.get_current_timezone()).replace(tzinfo=None),
                    'Check-out Time': record.checkout_time.astimezone(timezone.get_current_timezone()).replace(tzinfo=None) if record.checkout_time else None,
                }
                for record in records
            ]
            records_by_date[single_date.date()] = data

        # Create a new Excel file with multiple sheets
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for date, data in records_by_date.items():
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name=str(date), index=False)

        output.seek(0)
        response = HttpResponse(output, content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="Attendance_Report_{start_date}_to_{end_date}.xlsx"'
        
        return response

class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        login = request.data.get('login')
        password = request.data.get('password')
        user = authenticate(username=login, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'role': user.role if user.role else "",
                'first_name': user.first_name if user.first_name else "",
                'last_name': user.last_name if user.last_name else "",
            }, status=status.HTTP_200_OK)
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
class IsAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        return Response({'is_admin': user.is_superuser})