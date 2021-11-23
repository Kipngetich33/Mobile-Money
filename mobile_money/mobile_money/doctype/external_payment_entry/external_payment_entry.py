# -*- coding: utf-8 -*-
# Copyright (c) 2021, Upande LTD and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from types import new_class
import frappe
from frappe.model.document import Document

#std lib imports 
import datetime,json

#application level/local imports
from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_reference_documents

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
			#now get any oustanding invoices
			self.get_any_linked_outstanding_invoices()
			#append any outstanding invoices to payment entry
			self.prepare_outstanding_invoices()
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

	def get_any_linked_outstanding_invoices(self):
		'''
		Function that uses an ERPNext inbuilt method to get any oustanding
		invoices
		'''
		#check if payment in of type recieve 
		if not self.type_of_entry == "Receive":
			# return a empty list since we do not yet have functionality 
			# to deal with other cases
			#set outstanding_docs as empty 
			self.outstanding_docs =  []
			#stop execution of this function
			return 
		
		#if type is recieve go ahead an pull the payments
		arguments =  {
			"posting_date": None,
			"company": self.payment_details['company'],
			"party_type": "Customer",
			"payment_type": self.type_of_entry,
			"party": self.payment_details['customer'],
			"party_account": "Debtors - UL",
			"cost_center": None
		}
		args = json.dumps(arguments)#convert dict to str
		#get outstanding documents
		outstanding_docs = get_outstanding_reference_documents(args)
		#set outstandinf docs 
		self.outstanding_docs = outstanding_docs

	def prepare_outstanding_invoices(self):
		'''
		Methods that prepares any outstanding invoices to a payment
		entry provided the payment amount is not exeeded
		'''
		#get remaining balance
		remaining_balance = self.amount
		invoices_to_append = []
		if self.outstanding_docs:
			#loop through outstanding docs
			for doc in self.outstanding_docs:
				if remaining_balance > 0:
					if remaining_balance >= doc.outstanding_amount:
						allocated = doc.outstanding_amount
					else:
						new_outstanding = doc.outstanding_amount - remaining_balance
						allocated = remaining_balance
					doc_inv = {
						'reference_doctype':doc.voucher_type,
						'reference_name':doc.voucher_no,
						'due_date':doc.due_date,
						'total_amount':doc.invoice_amount,
						'outstanding_amount':doc.outstanding_amount,
						'allocated_amount':allocated,
					}
					#append new invoice to list
					invoices_to_append.append(doc_inv)
					#reduce balance by outstanding amount
					remaining_balance -= doc.outstanding_amount
				else:
					break
		#now set invoices to append
		self.invoices_to_append  = invoices_to_append
					
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
		#add advances invoices
		if self.invoices_to_append:
			# loop through each invoice
			for invoice_to_append in self.invoices_to_append:
				row = new_payment.append("references", {})
				row.reference_doctype = invoice_to_append['reference_doctype']
				row.reference_name = invoice_to_append['reference_name']
				row.due_date = invoice_to_append['due_date']
				row.total_amount = invoice_to_append['total_amount']
				row.outstanding_amount = invoice_to_append['outstanding_amount']
				row.allocated_amount = invoice_to_append['allocated_amount'] 
		#validate the payment entry
		try:
			new_payment.validate()
		except Exception as e:
			frappe.throw(e)
		#now save to database()
		new_payment.save(ignore_permissions = True)
		frappe.db.commit()
		#now submite the payment entry
		new_payment.submit()
		frappe.db.commit()
		#Now add the linked payment entry to payment entry
		self.linked_payment_entry = new_payment.name




		
		



