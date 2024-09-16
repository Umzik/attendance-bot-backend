from django.urls import path
from .views import CheckinView, CheckoutView, AdminReportView, LoginView, IsAdminView, PasswordChangeView, UserListView, \
    AdminCheckInOutView

urlpatterns = [
    path('checkin/', CheckinView.as_view(), name='checkin'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('admin/report/', AdminReportView.as_view(), name='admin-report'),
    path('login/', LoginView.as_view(), name='login'),
    path('is_admin/', IsAdminView.as_view(), name='is_admin'),

    path('user/change_password/', PasswordChangeView.as_view(), name='change-password'),

    path('users/', UserListView.as_view(), name='user-list'),

    path('admin/check/', AdminCheckInOutView.as_view(), name='admin-checkinout'),  # Admin check-in/out

]
