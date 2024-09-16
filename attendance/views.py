import io
from math import radians, cos, sin, asin, sqrt

import pandas as pd
from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.utils import timezone
from openpyxl.utils import get_column_letter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Attendance, User
from .serializers import PasswordChangeSerializer, UserSerializer


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r


class CheckinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
                    'Employee': record.employee.first_name if record.employee.first_name else '' + " " + record.employee.last_name if record.employee.last_name else '' ,
                    'Check-in Time': record.checkin_time.astimezone(timezone.get_current_timezone()).strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    'Check-out Time': record.checkout_time.astimezone(timezone.get_current_timezone()).strftime(
                        '%Y-%m-%d %H:%M:%S') if record.checkout_time else None,
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

                # Adjust column width to fit 40 characters
                worksheet = writer.sheets[str(date)]
                for col_num, column in enumerate(df.columns, 1):
                    max_length = 40  # Set a fixed width to display 40 characters
                    worksheet.column_dimensions[get_column_letter(col_num)].width = max_length

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


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.update_password(request.user)
            return Response({"detail": "Password changed successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminCheckInOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Ensure the user is an admin
        if request.user.role != 'admin':
            return Response({"message": "Permission denied."}, status=403)

        # Retrieve the employee ID and action (check-in or check-out) from the request
        employee_id = request.data.get('employee_id')
        action = request.data.get('action')

        if not employee_id or action not in ['checkin', 'checkout']:
            return Response({"message": "Employee ID and valid action (checkin/checkout) are required."}, status=400)

        # Find the employee by ID
        try:
            employee = User.objects.get(id=employee_id)
        except User.DoesNotExist:
            return Response({"message": "Employee not found."}, status=404)

        # Check if there's already a record for today
        try:
            attendance = Attendance.objects.filter(
                employee=employee,
                checkin_time__date=timezone.now().date()
            ).latest('checkin_time')
        except Attendance.DoesNotExist:
            attendance = None

        if action == 'checkin':
            # If the admin is trying to check-in the user
            if attendance and attendance.checkin_time:
                return Response({"message": "The user is already checked in today!"}, status=400)
            else:
                # Create a new check-in record
                Attendance.objects.create(employee=employee, checkin_time=timezone.now())
                return Response({"message": "Check-in successful!"})

        elif action == 'checkout':
            # If the admin is trying to check-out the user
            if attendance and attendance.checkout_time:
                return Response({"message": "The user is already checked out today!"}, status=400)
            elif not attendance:
                return Response({"message": "No check-in record found for today!"}, status=400)
            else:
                # Update the existing record with the checkout time
                attendance.checkout_time = timezone.now()
                attendance.save()
                return Response({"message": "Check-out successful!"})


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fetch all users from the database
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)