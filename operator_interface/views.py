from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, "operator_interface/index.html")


def privacy_policy(request):
    return render(request, "operator_interface/Privacy Policy.html")
