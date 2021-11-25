import frappe
from decouple import config
import requests,json
from requests.auth  import HTTPBasicAuth
from frappe import enqueue

#app level imports
from water.custom_methods.reusable_methods import get_settings

@frappe.whitelist()
def token():
	'''
	Function that uses the consumer key and consumer secret
	to generate and authorization token for a given MPesa app
	'''
	return ac_token()

#get authorization token
def ac_token():
	'''
	# Function that fetched authorization token for daraja api
	'''
	#determine whether mpesa is production or test
	mobile_money_settings = get_settings("Mobile Payment Settings")
	if mobile_money_settings.production:
		#mpesa  api prod details 
		consumer_key = config('organization_mpesa_api_key_prod')
		consumer_secret = config('organization_mpesa_api_secret_prod')
		mpesa_auth_url = config('mpesa_auth_url_prod')
	else:
		#mpesa api test details 
		consumer_key = config('organization_mpesa_api_key_test')
		consumer_secret = config('organization_mpesa_api_secret_test')
		mpesa_auth_url = config('mpesa_auth_url_test')
	#send http request
	data = (requests.get(mpesa_auth_url,auth = HTTPBasicAuth(consumer_key,consumer_secret))).json()
	return data['access_token']

#register urls
@frappe.whitelist()
def register():
	'''
	Function that registers the validation and confirmation urls for an APP
	in MPesa
	'''
	#determine whether mpesa is production or test
	mobile_money_settings = get_settings("Mobile Payment Settings")
	if mobile_money_settings.production:
		mpesa_endpoint = config('mpesa_reg_url_prod')
		organization_shortcode = config('organization_shortcode_prod')
	else:
		mpesa_endpoint = config('mpesa_reg_url_test')
		organization_shortcode = config('organization_shortcode_test')
	
	headers = {
		"Authorization": "Bearer %s" % ac_token(),
		"Content-Type": "application/json"
	}
	transaction_state = config('organization_transation_state')
	base_url = config('organization_api_base_url')

	req_body = {
		"ShortCode":organization_shortcode,
		"ResponseType":transaction_state,
		"ConfirmationURL": base_url +"/mobile_money.safcom.c2b_api.confirm",
		"ValidationURL": base_url +"/mobile_money.safcom.c2b_api.validate"
	}

	response_data = requests.post(
		mpesa_endpoint,
		json = req_body,
		headers = headers
	)
	#return the response data
	return response_data.json()

@frappe.whitelist(allow_guest = True)
def confirm():
	'''
	This is an endpoint that receives confirmation from 
	Mpesa when a transation is completed successfully
	'''
	transaction = get_request_form_data()
	#enque the payment data for processing and submission
	enqueue_transaction_payment_processing(transaction)
	#return process status
	return {'status':'Success'}

@frappe.whitelist(allow_guest = True)
def validate():
	'''
	Function that recives a validation request from mpesa before a
	transaction is completed. A request is only sent to this URL is 
	external validation is activated
	'''
	#we currently have not active external validation hence just pass
	return {'status':'Success'}

def process_payment(transaction):
	'''
	Function that uses the data from the transaction response i.e confirm
	url to create process payment that can be stored locally
	input: 
	 	transaction - dict
	 output:
	 	None
	'''
	#set the user to Administrator to avoid permission issue
	frappe.session.user = "Administrator"
	#get various details
	customer_acc = transaction.get('BillRefNumber')
	customer_phone_num = transaction.get('MSISDN')
	customer_first_name = transaction.get('FirstName')
	customer_middle_name = transaction.get('MiddleName')
	customer_last_name = transaction.get('LastName')
	transaction_amount = transaction.get('TransAmount')
	transaction_id = transaction.get('TransID')
	transaction_type = transaction.get('TransactionType')
	transaction_time = transaction.get('TransTime')
	business_short_code = transaction.get('BusinessShortCode')
	third_party_id = transaction.get('ThirdPartyTransID')
	invoice_number = transaction.get('InvoiceNumber')
	organization_balance = transaction.get('OrgAccountBalance')
	#now create the payment in the system here etc.
	#create external payment entry
	doc = frappe.new_doc('External Payment Entry')
	doc.account  = customer_acc
	doc.amount = transaction_amount
	doc.mode_of_payment = "MPesa"
	doc.type_of_entry = "Receive"
	doc.payment_reference = transaction_id
	doc.customer_phone_number = customer_phone_num
	doc.customer_first_name = customer_first_name
	doc.customer_middle_name = customer_middle_name
	doc.customer_last_name = customer_last_name
	doc.transaction_time = transaction_time
	doc.business_short_code = business_short_code 
	doc.third_party_id = third_party_id
	doc.invoice_number = invoice_number
	doc.note = transaction_type
	#now save the doc
	doc.save(ignore_permissions = True)
	frappe.db.commit()
	#now  enque the saved transaction for submission
	enqueue_transaction_submission(doc.name)

def submit_payment(transaction_doc_name):
	'''
	Function that changes the status of a saved 
	transaction and to submitted allowing it 
	to make changes in the system
	input:
		transaction_doc_name - str
	output:
		None
	'''
	frappe.session.user = "Administrator"
	payment_doc = frappe.get_doc("External Payment Entry",transaction_doc_name)
	# payment_doc.save()
	payment_doc.status = "Submitted"
	payment_doc.save()
	frappe.db.commit()

@frappe.whitelist(allow_guest = True)
def test_api():
	return {'status':True}

def get_request_form_data():
	if frappe.local.form_dict.data is None:
		data = frappe.safe_decode(frappe.local.request.get_data())
	else:
		data = frappe.local.form_dict.data
	return frappe.parse_json(data)

def enqueue_transaction_payment_processing(transaction):
    enqueue('mobile_money.safcom.c2b_api.process_payment', transaction=transaction)

def enqueue_transaction_submission(transaction_doc_name):
    enqueue('mobile_money.safcom.c2b_api.submit_payment', transaction_doc_name=transaction_doc_name)