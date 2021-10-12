from __future__ import unicode_literals
from frappe import _
import frappe


def get_data():
    config = [
		  {
        "label": _("Mobile Money"),
        "items": [
            {
              "type": "doctype",
              "name": "External Payment Entry",
              "description": _("External Payment Entry"),
              "onboard": 1,
            },
            {
              "type": "doctype",
              "name": "Mobile Payment Settings",
              "description": _("Mobile Payment Settings"),
              "onboard": 1,
            },
          ]
      }
    ]
    return config