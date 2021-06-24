from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from ledger.accounts.models import EmailUser

import logging

from mooringlicensing.components.approvals.email import send_vessel_nomination_reminder_main
from mooringlicensing.components.approvals.models import AnnualAdmissionPermit, Approval
from mooringlicensing.components.main.models import NumberOfDaysType, NumberOfDaysSetting
from mooringlicensing.settings import CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_AAP

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send email to annual admission permit holder configurable number of days before end of six month period in which a new vessel is to be nominated'

    def handle(self, *args, **options):
        try:
            user = EmailUser.objects.get(email=settings.CRON_EMAIL)
        except:
            user = EmailUser.objects.create(email=settings.CRON_EMAIL, password='')

        errors = []
        updates = []
        today = timezone.localtime(timezone.now()).date()

        # Retrieve the number of days before expiry date of the approvals to email
        days_type = NumberOfDaysType.objects.get(code=CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_AAP)
        days_setting = NumberOfDaysSetting.get_setting_by_date(days_type, today)
        if not days_setting:
            # No number of days found
            raise ImproperlyConfigured("NumberOfDays: {} is not defined for the date: {}".format(days_type.name, today))
        # NOTE: When sending the reminder:
        #       sold_date + 6months - number_of_days < today
        #       sold_date < today - 6months + number_of_days
        boundary_date = today - relativedelta(months=+6) + days_setting.number_of_days

        logger.info('Running command {}'.format(__name__))

        # Construct queries
        queries = Q()
        queries &= Q(processing_status__in=(Approval.APPROVAL_STATUS_APPROVED, Approval.APPROVAL_STATUS_SUSPENDED))
        queries &= Q(current_proposal__vessel_ownership__end_date__lt=boundary_date)
        queries &= Q(vessel_nomination_reminder_sent=False)

        for a in AnnualAdmissionPermit.objects.filter(queries):
            try:
                send_vessel_nomination_reminder_main(a)
                a.vessel_nomination_reminder_sent = True
                a.save()
                logger.info('Reminder to permission holder sent for Approval {}'.format(a.lodgement_number))
                updates.append(a.lodgement_number)
            except Exception as e:
                err_msg = 'Error sending reminder to permission holder for Approval {}'.format(a.lodgement_number)
                logger.error('{}\n{}'.format(err_msg, str(e)))
                errors.append(err_msg)

        cmd_name = __name__.split('.')[-1].replace('_', ' ').upper()
        err_str = '<strong style="color: red;">Errors: {}</strong>'.format(len(errors)) if len(
            errors) > 0 else '<strong style="color: green;">Errors: 0</strong>'
        msg = '<p>{} completed. {}. IDs updated: {}.</p>'.format(cmd_name, err_str, updates)
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
