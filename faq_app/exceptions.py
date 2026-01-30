from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize the error response format
        custom_data = {
            'status': 'error',
            'code': response.status_code,
            'message': 'An error occurred',
            'details': response.data
        }
        
        # Try to get a more specific message if available
        if isinstance(response.data, dict):
            if 'detail' in response.data:
                custom_data['message'] = response.data['detail']
                del custom_data['details']['detail']
            
            # If details is empty after removing detail, remove it
            if not custom_data['details']:
                del custom_data['details']
        elif isinstance(response.data, list):
             custom_data['details'] = response.data

        response.data = custom_data

    return response
