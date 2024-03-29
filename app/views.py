import json
import random

import cv2
from django.http import HttpResponseRedirect
from django.shortcuts import render

from app.forms import RegisterForm, AuthForm, ProfileForm
from app.models import Profile
import requests

url = 'https://api.yii2-stage.test.wooppay.com'

"""Главная"""


def index(request):
    return render(request, 'main.html')


"""Регистрация. 1 этап"""

registation = '/v1/registration/create-account'


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            login = form.cleaned_data.get('login')
            email = form.cleaned_data.get('email')
            data = {'login': login, 'email': email}
            response = requests.post(url + registation, data=data)
            if response.status_code == 201:
                return render(request, 'activate.html', {'form': ProfileForm()})
            else:
                form = RegisterForm()
                return render(request, 'register.html', {'form': form, 'error': 'Возникла ошибка'})
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


"""Регистрация.2 этап"""

activate = '/v1/registration/set-password'


def activate_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            login = form.cleaned_data.get('login')
            fio = form.cleaned_data.get('fio')
            city = form.cleaned_data.get('city')
            job = form.cleaned_data.get('job')
            foto = form.cleaned_data.get('foto')
            activate_code = form.cleaned_data.get('activate_code')
            password = form.cleaned_data.get('password')
            data = {'login': login, 'password': password, 'activate_code': activate_code}
            response = requests.post(url + activate, data=data)
            response_json = response.json()
            if response.status_code == 201:
                response_auth = request.post(url + auth, data={'login': login, 'password': password})
                if response_auth.status_code == '200':
                    response_balance = requests.get(url + balance,
                                                    headers={'Authorization': response_json['token']})
                    balance_user = response_balance.json()['active']
                    response = requests.post(url + id_status, headers={'Authorization': response_json['token']})
                    status = response.json()['status']
                    profile_user = Profile.objects.create(login=login, fio=fio, city=city, job=job,
                                                          balance=balance_user, foto=foto)
                    return render(request, 'profile.html',
                                  {'data': response_json, 'profile': profile_user, 'status': status,
                                   'balance': response_balance.json()['active']})
                else:
                    return render(request, 'login.html')
            else:
                form = ProfileForm()
                return render(request, 'activate.html', {'form': form, 'error': response_json[0]['message']})
    else:
        form = ProfileForm()
    return render(request, 'activate.html', {'form': form})


"""Авторизация"""

auth = '/v1/auth'
balance = '/v1/balance'
id_status = '/v1/user/id-status'


def login_view(request):
    if request.method == 'POST':
        form = AuthForm(request.POST)
        if form.is_valid():
            login = form.cleaned_data.get('login')
            password = form.cleaned_data.get('password')
            data = {'login': login, 'password': password}
            response = requests.post(url + auth, data=data, headers={'Partner-name': 'tips'})
            response_json = response.json()
            if response.status_code == 200:
                response_balance = requests.get(url + balance, headers={'Authorization': response_json['token'],
                                                                        'Partner-name': 'tips'})
                response_status = requests.get(url + id_status, headers={'Authorization': response_json['token'],
                                                                         'Partner-name': 'tips'})
                status = response_status.json()['status']

                profile_user = Profile.objects.filter(login=login)
                return render(request, 'profile.html',
                              {'data': response_json, 'profile': profile_user, 'status': status,
                               'balance': response_balance.json()['active']})
            else:
                form = AuthForm()
                return render(request, 'login.html', {'form': form, 'error': response_json[0]['message']})
    else:
        form = AuthForm()
    return render(request, 'login.html', {'form': form})


"""Создание услуги(чаевые) и генерирование кьюара"""
import qrcode

img_name = 'blank.png'
donate = '/v1/service/donate'
num = random.randint(1,500)

def donate_view(request):
    if request.method == 'POST':
        token = request.POST.get('token')
        user = request.POST.get('user')
        data_user = request.POST.get('data')
        data = json.dumps({
            "fields": {
                "amount": "0"
            },
            "title": "Чаевые!",
            "name": "УРА! Чаевые!",
            "description": "Нужно больше золота..."
        })
        response = requests.post(url + donate, headers={'Content-Type': 'application/json', 'Authorization': token},
                                 data=data)
        service_name = response.json()['service_name']
        img = qrcode.make(service_name)
        img.save('app/static/img/blank%s.png' % num)
        return render(request, 'qr.html', {'qr': 'img/blank%s.png' % num, 'user': user,'data': data_user})


# чтение куара
transfer_new = '/v1/payment/transfer-new'
pay_card = '/v1/payment/pay-from-card'


def qr_reader(request):
    cam = cv2.VideoCapture(0)  # включаем камеру
    detector = cv2.QRCodeDetector()  # включаем  QRCode detector
    while True:
        _, img = cam.read()
        service_name, bbox, _ = detector.detectAndDecode(img)
        if service_name[:8] == 'transfer':
            data = service_name
            break
    return render(request, 'pseudo_auth.html', {'service_name': data})


"""Псевдоавторизация"""
pseudo_auth = '/v1/auth/pseudo'


def pseudo_auth_view(request):
    if request.method == 'POST':
        login = request.POST.get('login')
        service_name = request.POST.get('service_name')
        response = requests.post(url + pseudo_auth, data={'login': login})
        token = response.json()['token']
        return render(request, 'form_pay.html', {'token': token, 'service_name': service_name})


# создание визитки
import os
from PIL import Image, ImageDraw, ImageColor, ImageFont

card_name = os.path.normpath('app/static/img/card.png')

def make_card(request):
    if request.method == 'POST':
        qr = request.POST.get('qr')
        im2 = Image.open(card_name)
        qr = Image.open('app/static/'+qr)
        im2.paste(qr,(100,100))
        im2.save('app/static/img/card%s.png' % num)
        return render(request, 'card.html',{'card':'img/card%s.png' % num})


"""История"""

history = '/v1/history'


def history_view(request):
    token = request.GET.get('token')
    print(token)
    response = requests.get(url + history, headers={'Content-Type': 'application/json', 'Authorization': token})
    response_json = response.json()
    return render(request, 'history.html', {'history': response_json, 'token': token})


"""Вывод чаевых на карту"""

transfer = '/v1/payment/transfer-to-card'


def token_view(request):
    token = request.POST.get('token')
    return render(request, 'transfer.html', {'token': token})


def transfer_view(request):
    token = request.POST.get('token')
    summa = request.POST.get('summa')
    response = requests.post(url + transfer, headers={'Content-Type': 'application/json', 'Authorization': token},
                             data=json.dumps({'amount': str(summa), 'mobile_scripts': True}))
    print(response.json())
    return HttpResponseRedirect(response.json()['frame_url'])


"""Оплата"""


def form_pay_view(request):
    token = request.POST.get('token')
    service_name = request.POST.get('service_name')
    summa = request.POST.get('summa')
    data = json.dumps({
        'service_name': service_name,
        "fields": {
            "amount": summa
        }
    })
    response = requests.post(url + transfer_new, headers={'Content-Type': 'application/json', 'Authorization': token},
                             data=data)
    operation_id = response.json()['operation']['id']

    response_url = requests.post(url + pay_card, headers={'Authorization': token},
                                 data={'operation_id': operation_id})
    return HttpResponseRedirect(response_url.json()['frame_url'])


"""ЧЕК"""

receipt = '/v1/history/receipt/'
status = '/v1/history/transaction/get-operations-data'

def receipt_view(request, pk):
    if request.method == 'POST':
        token = request.POST.get('token')
        id = request.POST.get('id')
        data = json.dumps({
          "operation_ids": [
            id
          ]
        })
        response_status = requests.post(url + status, headers={'Content-Type': 'application/json', 'Authorization': token},data=data )
        if response_status.json()[0]["status"] == 14:
            response = requests.get(url + receipt + str(pk),headers={'Content-Type': 'application/json', 'Authorization': token})
            print(response)
            if response.status_code == 200:
                return render(request, 'receipt.html', {'receipt': response.json()})
        else:
            return render(request,'receipt.html',{'error':'Статус операции - %s'%response_status.json()[0]["status"]})

def receipt_pdf_view(request, pk):
    if request.method == 'POST':
        token = request.POST.get('token')
        response = request.get(url + receipt + 'pdf/' + str(pk), headers={'Authorization': token})
        if response.status_code == 200:
            return render(request, 'receipt.html', {'receipt': response.json()})
