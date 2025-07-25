import requests
import base64
import json
from datetime import datetime
import uuid
from django.conf import settings
from requests.exceptions import RequestException

class MTNMobileMoney:
    def __init__(self):
        self.subscription_key = settings.MTN_MOMO_SUBSCRIPTION_KEY
        self.api_user = settings.MTN_MOMO_API_USER
        self.api_key = settings.MTN_MOMO_API_KEY
        self.callback_url = settings.MTN_MOMO_CALLBACK_URL
        self.environment = settings.MTN_MOMO_ENVIRONMENT  # 'sandbox' or 'production'
        
        if self.environment == 'sandbox':
            self.base_url = 'https://sandbox.momodeveloper.mtn.com'
        else:
            self.base_url = 'https://momodeveloper.mtn.com'

    def _get_auth_token(self):
        """Get authentication token from MTN API"""
        auth_url = f"{self.base_url}/collection/token/"
        auth_string = f"{self.api_user}:{self.api_key}"
        auth_bytes = auth_string.encode('ascii')
        base64_auth = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {base64_auth}',
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        
        try:
            response = requests.post(auth_url, headers=headers)
            response.raise_for_status()
            return response.json().get('access_token')
        except RequestException as e:
            raise Exception(f"Authentication failed: {str(e)}")

    def request_payment(self, amount, phone_number, external_id, payee_note="", payer_message=""):
        """Initiate payment request"""
        token = self._get_auth_token()
        payment_url = f"{self.base_url}/collection/v1_0/requesttopay"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Reference-Id': str(uuid.uuid4()),
            'X-Target-Environment': self.environment,
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        
        payload = {
            "amount": str(amount),
            "currency": "RWF",
            "externalId": external_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone_number
            },
            "payerMessage": payer_message,
            "payeeNote": payee_note,
            "callbackUrl": self.callback_url
        }
        
        try:
            response = requests.post(payment_url, headers=headers, json=payload)
            response.raise_for_status()
            return {
                'status': 'success',
                'reference_id': headers['X-Reference-Id'],
                'response': response.json()
            }
        except RequestException as e:
            return {
                'status': 'error',
                'message': str(e),
                'response': getattr(e.response, 'json', lambda: {})()
            }

    def check_payment_status(self, reference_id):
        """Check status of a payment"""
        token = self._get_auth_token()
        status_url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Target-Environment': self.environment,
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }
        
        try:
            response = requests.get(status_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            raise Exception(f"Payment status check failed: {str(e)}")