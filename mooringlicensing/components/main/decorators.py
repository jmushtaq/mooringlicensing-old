import time
import traceback
from django.db import connection, reset_queries
import functools
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpRequest
from rest_framework import serializers
# from rest_framework.request import Request
# from rest_framework.request import Request
from rest_framework.request import Request
import logging

#logger = logging.getLogger(__name__)
logger = logging.getLogger()


def basic_exception_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except serializers.ValidationError:
            print(traceback.print_exc())
            raise
        except ValidationError as e:
            from mooringlicensing.components.main.utils import handle_validation_error
            handle_validation_error(e)
        except Exception as e:
            print(traceback.print_exc())
            raise serializers.ValidationError(str(e))
    return wrapper


#def update_settings_handler(func):
#    """
#    This function updates the settings values according to the subdomain
#    @param func:
#    @return:
#    """
#    def wrapper(*args, **kwargs):
#        for param in args:
#            if isinstance(param, HttpRequest) or isinstance(param, Request) or isinstance(param, WSGIRequest):
#                web_url = param.META.get('HTTP_HOST', None)
#                if web_url in settings.APIARY_URL:
#                    settings.SYSTEM_NAME = settings.APIARY_SYSTEM_NAME
#                    settings.SYSTEM_NAME_SHORT = 'Apiary'
#                    settings.BASE_EMAIL_TEXT = 'disturbance/emails/apiary_base_email.txt'
#                    settings.BASE_EMAIL_HTML = 'disturbance/emails/apiary_base_email.html'
#        return func(*args, **kwargs)
#    return wrapper


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % (method.__name__, (te - ts) * 1000))
            #logger.error('%r  %2.2f ms' % (method.__name__, (te - ts) * 1000))
        return result
    return timed

def query_debugger(func):
    @functools.wraps(func)
    def inner_func(*args, **kwargs):
        #import ipdb; ipdb.set_trace()
        reset_queries()
        start_queries = len(connection.queries)
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        end_queries = len(connection.queries)
        print(f"Function : {func.__name__}")
        print(f"Number of Queries : {end_queries - start_queries}")
        print(f"Finished in : {(end - start):.2f}s")
        function_name = 'Function : {}'.format(func.__name__)
        number_of_queries = 'Number of Queries : {}'.format(end_queries - start_queries)
        time_taken = 'Finished in : {0:.2f}s'.format((end - start))
        logger.error(function_name)
        logger.error(number_of_queries)
        logger.error(time_taken)
        #logger.error('Function : {}'.format(func.__name__))
        #logger.error('Number of Queries : {}'.format(end_queries - start_queries))
        #logger.error('Finished in : {0:.2f}s'.format((end - start)))
        return result
    return inner_func

