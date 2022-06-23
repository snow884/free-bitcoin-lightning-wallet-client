import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import base64


from datetime import datetime

url = "https://lndhub.herokuapp.com"


class BlueWalletClient:
    def __init__(self, bluewallet_login, bluewallet_password, limit=1000):
        self.creds = {
            "login": bluewallet_login,
            "password": bluewallet_password,
        }
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "POST", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http = requests.Session()
        self.http.mount("https://", adapter)
        self.http.mount("http://", adapter)

        self.get_token()
        invoice_list = self.getuserinvoices_paginate(limit)
        self.invoice_lookup = {
            inv_data["r_hash"]: inv_data for inv_data in invoice_list
        }

    def get_login(self):

        body = {"partnerid": "bluewallet", "accounttype": "common"}

        res = self.http.post(f"{url}/create", data=body)
        res.raise_for_status()

    def limit_reached(self, headers):

        if int(headers.get("X-Ratelimit-Remaining", 100)) < 10:
            raise Exception(
                f"Rate limit dropped below {int(headers['X-Ratelimit-Remaining'])}, headers: {headers}"
            )

    def get_token(self):
        res = self.http.post(f"{url}/auth", data=self.creds)
        self.limit_reached(res.headers)
        res.raise_for_status()
        res_dict = res.json()

        self.access_token = res_dict["access_token"]
        self.refresh_token = res_dict["refresh_token"]

    def create_invoice(self, amt, memo):

        body = {"amt": amt, "memo": memo}
        res = self.http.post(
            f"{url}/addinvoice",
            data=body,
            headers={"Authorization": f"{self.access_token}"},
        )
        self.limit_reached(res.headers)
        res.raise_for_status()
        res_dict = res.json()
        res_dict = self.correct_rhash(res_dict)
        return res_dict

    def payinvoice(self, invoice, amount=None):
        body = {"invoice": invoice}
        if amount:
            body["amount"] = amount

        res = self.http.post(
            f"{url}/payinvoice",
            data=body,
            headers={"Authorization": f"{self.access_token}"},
        )
        self.limit_reached(res.headers)
        res.raise_for_status()
        res_dict = res.json()

    def lnd_send_payment(self, payment_request, amount=None):

        body = {"invoice": payment_request}
        if amount:
            body["amount"] = amount

        res = self.http.post(
            f"{url}/payinvoice",
            data=body,
            headers={"Authorization": f"{self.access_token}"},
        )
        self.limit_reached(res.headers)
        res.raise_for_status()
        res_dict = res.json()

    def getuserinvoices(self, limit):
        params = {"limit": limit}

        res = self.http.get(
            f"{url}/getuserinvoices",
            params=params,
            headers={"Authorization": f"{self.access_token}"},
        )
        self.limit_reached(res.headers)
        res.raise_for_status()
        res_dict = res.json()
        return res_dict

    def getuserinvoices_paginate(self, limit=1000):

        res = []
        res_full = []

        res = self.getuserinvoices(limit)

        res_full.extend(res)

        timestamps = [
            datetime.utcfromtimestamp(a["timestamp"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            for a in res
        ]

        if len(timestamps) > 0:
            print(f"count {len(timestamps)}")
            print(f"first timestamp {timestamps[0]}")
            print(f"last timestamp {timestamps[-1]}")

        for invoice_data in res_full:
            invoice_data = self.correct_rhash(invoice_data)

        return res_full

    def lookup_invoice(self, r_hash):

        res = self.invoice_lookup.get(r_hash, None)

        return res

    def correct_rhash(self, invoice_data):
        invoice_data["r_hash"] = (
            base64.b64encode(bytes(invoice_data["r_hash"]["data"]))
        ).decode("utf-8")
        return invoice_data


