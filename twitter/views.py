from django.http import HttpResponse


def webhook(request):
    print(request.body)
    return HttpResponse("")
