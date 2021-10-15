# -*- coding: utf-8 -*-
# Copyright (c) 2021, Upande LTD and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

#std lib imports 
import datetime

class ExternalPaymentEntry(Document):
	'''
	This is the external Payment Entry 
	Document class
	'''
	def validate(self):
		'''
		Method that runs validation before the document is
		saved
		'''
		# validate  fields
		self.validate_fields()

	def before_save(self):
		'''
		Method that runs before the document is 
		saved
		'''
		#check status hence action
		if self.status == "Draft":			
			pass
		elif self.status == "Submitted":
			#prepare erpnext payment details
			self.prepare_payment_entry_details()
			#now add the payment to a payment entry
			self.create_payment_entry()
				
	def validate_fields(self):
		'''
		Method that validates the given
		fields
		'''
		if self.status == "Draft":
			pass
		elif self.status == "Submitted":
			required_fields = [
				{'field_name':'Account','value':self.account},
				{'field_name':'Amount','value':self.amount},
				{'field_name':'Mode of Payment','value':self.mode_of_payment},
				{'field_name':'Type of Entry','value':self.type_of_entry}
			]
			#loop through required fields
			for field in required_fields:
				if not field.get('value'):
					frappe.throw('The {} field is required'.format(field['field_name']))
			#check payment references where required
			if self.mode_of_payment != "Cash" \
			and not self.payment_reference:
				frappe.throw("A payment reference is required")

	def get_account_account(self):
		'''
		Function that that uses the given account number
		to fetch the related ERPNext customer
		'''
		#get customer account doc
		cust_acc_docs = frappe.get_list("Customer Details",filters={
			'linked_customer_account':self.account,
			'status':'Active'
			},
			fields = ['name','linked_customer_account','customer']
		)
		# check if a customer details document was found
		if cust_acc_docs:
			#get linked customer account
			erpnext_customer = cust_acc_docs[0].get('customer')
			#now return the customer account
			return {'status':True,'erpnext_customer':erpnext_customer}
		else:
			return {'status':False,'message':'The customer account'}

	def get_mobile_payment_settings(self):
		'''
		Method that gets mobile payment settings 
		'''
		#check if mobile payment settings
		if not hasattr(self,'mobile_money_settings'):
			#get mobile payment settings
			self.mobile_payment_settings = frappe.get_single("Mobile Payment Settings")

	def prepare_payment_entry_details(self):
		'''
		Method that prepares the required details for new payment entry
		'''
		#get customer account
		customer_account_details = self.get_account_account()
		#get mobile payment settings
		mobile_payment_settings = frappe.get_single("Mobile Payment Settings")
		#define details based on account details status
		if customer_account_details['status']:
			customer = customer_account_details['erpnext_customer']
			company = mobile_payment_settings.company
			paid_from = mobile_payment_settings.account_paid_from_assigned
			paid_to = mobile_payment_settings.account_paid_to_assigned
			acc_currency = mobile_payment_settings.account_currency_assigned
		else:
			customer = mobile_payment_settings.unassigned_customer
			company = mobile_payment_settings.company
			paid_from = mobile_payment_settings.account_paid_from_unassigned
			paid_to = mobile_payment_settings.account_paid_to_unassigned
			acc_currency = mobile_payment_settings.account_currency_unassigned
		#compile the erpnext payment details 
		self.payment_details = {
			'customer':customer,
			'company':company,
			'paid_from':paid_from,
			'paid_to':paid_to,
			'acc_currency':acc_currency
		}

	def create_payment_entry(self):
		'''
		Method that creates a payment entry for an associated 
		customer
		'''
		#check if the document is already linked with payment entry
		if self.linked_payment_entry:
			return 

		#create new payment entry doc
		new_payment = frappe.new_doc("Payment Entry")
		new_payment.payment_type = self.type_of_entry
		new_payment.party_type = "Customer"
		new_payment.party = self.payment_details['customer']
		new_payment.company = self.payment_details['company']
		new_payment.mode_of_payment = self.mode_of_payment
		new_payment.paid_from = self.payment_details['paid_from']
		new_payment.paid_to = self.payment_details['paid_to']
		new_payment.paid_to_account_currency = self.payment_details['acc_currency']
		new_payment.received_amount = self.amount
		new_payment.paid_amount = self.amount
		#validate the payment entry
		try:
			new_payment.validate()
		except Exception as e:
			frappe.throw(e)
		#now save to database()
		new_payment.save(ignore_permissions = True)
		# frappe.db.commit()
		#now submite the payment entry
		new_payment.submit()
		frappe.db.commit()
		#Now add the linked payment entry to payment entry
		self.linked_payment_entry = new_payment.name




		
		



