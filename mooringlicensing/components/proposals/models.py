from __future__ import unicode_literals

import json
import datetime
from django.db import models,transaction
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.utils.encoding import python_2_unicode_compatible
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.postgres.fields.jsonb import JSONField
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from django.conf import settings
from ledger.accounts.models import EmailUser, RevisionedMixin
#from ledger.accounts.models import EmailUser
from ledger.payments.invoice.models import Invoice

from mooringlicensing import exceptions
from mooringlicensing.components.organisations.models import Organisation
from mooringlicensing.components.main.models import (
    CommunicationsLogEntry,
    UserAction,
    Document, ApplicationType,
    # Region, District, Tenure,
    # ApplicationType,
    # Park, Activity, ActivityCategory, AccessType, Trail, Section, Zone, RequiredDocument#, RevisionedMixin
)

from mooringlicensing.components.proposals.email import (
    send_proposal_decline_email_notification,
    send_proposal_approval_email_notification,
    send_proposal_awaiting_payment_approval_email_notification,
    send_amendment_email_notification,
    send_submit_email_notification, 
    send_external_submit_email_notification, 
    send_approver_decline_email_notification, 
    send_approver_approve_email_notification, 
    send_proposal_approver_sendback_email_notification, 
)
from mooringlicensing.ordered_model import OrderedModel
import copy
import subprocess
from django.db.models import Q, Max
from reversion.models import Version
from dirtyfields import DirtyFieldsMixin
from rest_framework import serializers

import logging

from mooringlicensing.settings import PROPOSAL_TYPE_AMENDMENT, PROPOSAL_TYPE_RENEWAL

logger = logging.getLogger(__name__)


def update_proposal_doc_filename(instance, filename):
    return '{}/proposals/{}/documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_onhold_doc_filename(instance, filename):
    return '{}/proposals/{}/on_hold/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_proposal_required_doc_filename(instance, filename):
    return '{}/proposals/{}/required_documents/{}'.format(settings.MEDIA_APP_DIR, instance.proposal.id,filename)

def update_requirement_doc_filename(instance, filename):
    return '{}/proposals/{}/requirement_documents/{}'.format(settings.MEDIA_APP_DIR, instance.requirement.proposal.id,filename)

def update_proposal_comms_log_filename(instance, filename):
    return '{}/proposals/{}/communications/{}'.format(settings.MEDIA_APP_DIR, instance.log_entry.proposal.id,filename)

#def application_type_choicelist():
#    try:
#        return [( (choice.name), (choice.name) ) for choice in ApplicationType.objects.filter(visible=True)]
#    except:
#        # required because on first DB tables creation, there are no ApplicationType objects -- setting a default value
#        return ( ('T Class', 'T Class'), )
#
#class ProposalType(models.Model):
#    #name = models.CharField(verbose_name='Application name (eg. mooringlicensing, Apiary)', max_length=24)
#    #application_type = models.ForeignKey(ApplicationType, related_name='aplication_types')
#    description = models.CharField(max_length=256, blank=True, null=True)
#    #name = models.CharField(verbose_name='Application name (eg. mooringlicensing, Apiary)', max_length=24, choices=application_type_choicelist(), default=application_type_choicelist()[0][0])
#    name = models.CharField(verbose_name='Application name (eg. T Class, Filming, Event, E Class)', max_length=64, choices=application_type_choicelist(), default='T Class')
#    schema = JSONField(default=[{}])
#    #activities = TaggableManager(verbose_name="Activities",help_text="A comma-separated list of activities.")
#    #site = models.OneToOneField(Site, default='1')
#    replaced_by = models.ForeignKey('self', on_delete=models.PROTECT, blank=True, null=True)
#    #replaced_by = models.ForeignKey('self', blank=True, null=True)
#    version = models.SmallIntegerField(default=1, blank=False, null=False)
#
#    def __str__(self):
#        return '{} - v{}'.format(self.name, self.version)
#
#    class Meta:
#        app_label = 'mooringlicensing'
#        unique_together = ('name', 'version')
#
#class TaggedProposalAssessorGroupRegions(TaggedItemBase):
#    content_object = models.ForeignKey("ProposalAssessorGroup")
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
#class TaggedProposalAssessorGroupActivities(TaggedItemBase):
#    content_object = models.ForeignKey("ProposalAssessorGroup")
#
#    class Meta:
#        app_label = 'mooringlicensing'


class ProposalAssessorGroup(models.Model):
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(EmailUser)
    #region = models.ForeignKey(Region, null=True, blank=True)
    #default = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Assessor Group"
        verbose_name_plural = "Application Assessor Group"

    def __str__(self):
        num_of_members = self.members.count()
        num_of_members_str = '{} member'.format(num_of_members) if num_of_members == 1 else '{} members'.format(num_of_members)
        return '{} ({})'.format(self.name, num_of_members_str)

    #def clean(self):
    #    try:
    #        default = ProposalAssessorGroup.objects.get(default=True)
    #    except ProposalAssessorGroup.DoesNotExist:
    #        default = None

    #    if self.pk:
    #        if not self.default and not self.region:
    #            raise ValidationError('Only default can have no region set for proposal assessor group. Please specifiy region')
    #    else:
    #        if default and self.default:
    #            raise ValidationError('There can only be one default proposal assessor group')

    # TODO: check this logic
    def member_is_assigned(self,member):
        for p in self.current_proposals:
            if p.assigned_officer == member:
                return True
        return False

    #@property
    #def current_proposals(self):
    #    assessable_states = ['with_assessor','with_referral','with_assessor_requirements']
    #    return Proposal.objects.filter(processing_status__in=assessable_states)

    @property
    def members_email(self):
        return [i.email for i in self.members.all()]

#class TaggedProposalApproverGroupRegions(TaggedItemBase):
#    content_object = models.ForeignKey("ProposalApproverGroup")
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
#class TaggedProposalApproverGroupActivities(TaggedItemBase):
#    content_object = models.ForeignKey("ProposalApproverGroup")
#
#    class Meta:
#        app_label = 'mooringlicensing'


class ProposalApproverGroup(models.Model):
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(EmailUser)
    #region = models.ForeignKey(Region, null=True, blank=True)
    #default = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Approver Group"
        verbose_name_plural = "Application Approver Group"

    def __str__(self):
        num_of_members = self.members.count()
        num_of_members_str = '{} member'.format(num_of_members) if num_of_members == 1 else '{} members'.format(num_of_members)
        return '{} ({})'.format(self.name, num_of_members_str)

    #def clean(self):
    #    try:
    #        default = ProposalApproverGroup.objects.get(default=True)
    #    except ProposalApproverGroup.DoesNotExist:
    #        default = None

    #    if self.pk:
    #        if not self.default and not self.region:
    #            raise ValidationError('Only default can have no region set for proposal assessor group. Please specifiy region')
    #    else:
    #        if default and self.default:
    #            raise ValidationError('There can only be one default proposal approver group')
    
    # TODO: check this logic
    def member_is_assigned(self,member):
        for p in self.current_proposals:
            if p.assigned_approver == member:
                return True
        return False

    #@property
    #def current_proposals(self):
    #    assessable_states = ['with_approver']
    #    return Proposal.objects.filter(processing_status__in=assessable_states)

    @property
    def members_email(self):
        return [i.email for i in self.members.all()]


#class DefaultDocument(Document):
#    input_name = models.CharField(max_length=255,null=True,blank=True)
#    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
#    visible = models.BooleanField(default=True) # to prevent deletion on file system, hidden and still be available in history
#
#    class Meta:
#        app_label = 'mooringlicensing'
#        abstract =True
#
#    def delete(self):
#        if self.can_delete:
#            return super(DefaultDocument, self).delete()
#        logger.info('Cannot delete existing document object after Application has been submitted (including document submitted before Application pushback to status Draft): {}'.format(self.name))
#
#
#
class ProposalDocument(Document):
    proposal = models.ForeignKey('Proposal',related_name='documents')
    _file = models.FileField(upload_to=update_proposal_doc_filename, max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Document"

#class OnHoldDocument(Document):
#    proposal = models.ForeignKey('Proposal',related_name='onhold_documents')
#    _file = models.FileField(upload_to=update_onhold_doc_filename, max_length=512)
#    input_name = models.CharField(max_length=255,null=True,blank=True)
#    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
#    visible = models.BooleanField(default=True) # to prevent deletion on file system, hidden and still be available in history
#
#    def delete(self):
#        if self.can_delete:
#            return super(ProposalDocument, self).delete()
#
##Documents on Activities(land)and Activities(Marine) tab for T-Class related to required document questions
#class ProposalRequiredDocument(Document):
#    proposal = models.ForeignKey('Proposal',related_name='required_documents')
#    _file = models.FileField(upload_to=update_proposal_required_doc_filename, max_length=512)
#    input_name = models.CharField(max_length=255,null=True,blank=True)
#    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
#    required_doc = models.ForeignKey('RequiredDocument',related_name='proposals')
#    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
#    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted
#
#    def delete(self):
#        if self.can_delete:
#            return super(ProposalRequiredDocument, self).delete()
#        logger.info('Cannot delete existing document object after Application has been submitted (including document submitted before Application pushback to status Draft): {}'.format(self.name))
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
#
#class ReferralDocument(Document):
#    referral = models.ForeignKey('Referral',related_name='referral_documents')
#    _file = models.FileField(upload_to=update_referral_doc_filename, max_length=512)
#    input_name = models.CharField(max_length=255,null=True,blank=True)
#    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
#
#    def delete(self):
#        if self.can_delete:
#            return super(ProposalDocument, self).delete()
#        logger.info('Cannot delete existing document object after Application has been submitted (including document submitted before Application pushback to status Draft): {}'.format(self.name))
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
class RequirementDocument(Document):
    requirement = models.ForeignKey('ProposalRequirement',related_name='requirement_documents')
    _file = models.FileField(upload_to=update_requirement_doc_filename, max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    visible = models.BooleanField(default=True) # to prevent deletion on file system, hidden and still be available in history

    def delete(self):
        if self.can_delete:
            return super(RequirementDocument, self).delete()


#class ProposalApplicantDetails(models.Model):
#    first_name = models.CharField(max_length=24, blank=True, default='')
#
#    class Meta:
#        app_label = 'mooringlicensing'

VESSEL_TYPES = (
        ('yacht', 'Yacht'),
        ('cabin_cruiser', 'Cabin Cruiser'),
        ('tender', 'Tender'),
        ('other', 'Other'),
        )
INSURANCE_CHOICES = (
    ("five_million", "$5 million Third Party Liability insurance cover - required for vessels of length less than 6.4 metres"),
    ("ten_million", "$10 million Third Party Liability insurance cover - required for vessels of length 6.4 metres or greater"),
    ("over_ten", "over $10 million"),
)
MOORING_AUTH_PREFERENCES = (
        ('site_licensee', 'By a mooring site licensee for their mooring'),
        ('ria', 'By Rottnest Island Authority for a mooring allocated by the Authority'),
        )


class ProposalType(models.Model):
    code = models.CharField(max_length=30, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        # return 'id: {} code: {}'.format(self.id, self.code)
        return self.description

    class Meta:
        app_label = 'mooringlicensing'


class Proposal(DirtyFieldsMixin, RevisionedMixin):
#class Proposal(DirtyFieldsMixin, models.Model):
    APPLICANT_TYPE_ORGANISATION = 'ORG'
    APPLICANT_TYPE_PROXY = 'PRX'
    APPLICANT_TYPE_SUBMITTER = 'SUB'

    # CUSTOMER_STATUS_TEMP = 'temp'
    CUSTOMER_STATUS_DRAFT = 'draft'
    CUSTOMER_STATUS_WITH_ASSESSOR = 'with_assessor'
    # CUSTOMER_STATUS_AMENDMENT_REQUIRED = 'amendment_required'
    CUSTOMER_STATUS_APPROVED = 'approved'
    CUSTOMER_STATUS_DECLINED = 'declined'
    CUSTOMER_STATUS_DISCARDED = 'discarded'
    # CUSTOMER_STATUS_PARTIALLY_APPROVED = 'partially_approved'
    # CUSTOMER_STATUS_PARTIALLY_DECLINED = 'partially_declined'
    CUSTOMER_STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    CUSTOMER_STATUS_CHOICES = (
        # (CUSTOMER_STATUS_TEMP, 'Temporary'),
        (CUSTOMER_STATUS_DRAFT, 'Draft'),
        (CUSTOMER_STATUS_WITH_ASSESSOR, 'Under Review'),
        # (CUSTOMER_STATUS_AMENDMENT_REQUIRED, 'Amendment Required'),
        (CUSTOMER_STATUS_APPROVED, 'Approved'),
        (CUSTOMER_STATUS_DECLINED, 'Declined'),
        (CUSTOMER_STATUS_DISCARDED, 'Discarded'),
        # (CUSTOMER_STATUS_PARTIALLY_APPROVED, 'Partially Approved'),
        # (CUSTOMER_STATUS_PARTIALLY_DECLINED, 'Partially Declined'),
        (CUSTOMER_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        )

    # List of statuses from above that allow a customer to edit an application.
    CUSTOMER_EDITABLE_STATE = [
        #'temp',
        CUSTOMER_STATUS_DRAFT,
        # CUSTOMER_STATUS_AMENDMENT_REQUIRED,
    ]

    # List of statuses from above that allow a customer to view an application (read-only)
    CUSTOMER_VIEWABLE_STATE = [
        CUSTOMER_STATUS_WITH_ASSESSOR,
        CUSTOMER_STATUS_WITH_ASSESSOR,
        # 'id_required',
        # 'returns_required',
        CUSTOMER_STATUS_AWAITING_PAYMENT,
        CUSTOMER_STATUS_APPROVED,
        CUSTOMER_STATUS_DECLINED,
        # 'partially_approved',
        # 'partially_declined'
    ]

    PROCESSING_STATUS_TEMP = 'temp'
    PROCESSING_STATUS_DRAFT = 'draft'
    PROCESSING_STATUS_WITH_ASSESSOR = 'with_assessor'
    PROCESSING_STATUS_WITH_DISTRICT_ASSESSOR = 'with_district_assessor'
    PROCESSING_STATUS_ONHOLD = 'on_hold'
    PROCESSING_STATUS_WITH_QA_OFFICER = 'with_qa_officer'
    PROCESSING_STATUS_WITH_REFERRAL = 'with_referral'
    PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS = 'with_assessor_requirements'
    PROCESSING_STATUS_WITH_APPROVER = 'with_approver'
    PROCESSING_STATUS_RENEWAL = 'renewal'
    PROCESSING_STATUS_LICENCE_AMENDMENT = 'licence_amendment'
    PROCESSING_STATUS_AWAITING_APPLICANT_RESPONSE = 'awaiting_applicant_respone'
    PROCESSING_STATUS_AWAITING_ASSESSOR_RESPONSE = 'awaiting_assessor_response'
    PROCESSING_STATUS_AWAITING_RESPONSES = 'awaiting_responses'
    PROCESSING_STATUS_READY_FOR_CONDITIONS = 'ready_for_conditions'
    PROCESSING_STATUS_READY_TO_ISSUE = 'ready_to_issue'
    PROCESSING_STATUS_APPROVED = 'approved'
    PROCESSING_STATUS_DECLINED = 'declined'
    PROCESSING_STATUS_DISCARDED = 'discarded'
    PROCESSING_STATUS_PARTIALLY_APPROVED = 'partially_approved'
    PROCESSING_STATUS_PARTIALLY_DECLINED = 'partially_declined'
    PROCESSING_STATUS_AWAITING_PAYMENT = 'awaiting_payment'
    PROCESSING_STATUS_CHOICES = ((PROCESSING_STATUS_TEMP, 'Temporary'),
                                 (PROCESSING_STATUS_DRAFT, 'Draft'),
                                 (PROCESSING_STATUS_WITH_ASSESSOR, 'With Assessor'),
                                 (PROCESSING_STATUS_WITH_DISTRICT_ASSESSOR, 'With District Assessor'),
                                 (PROCESSING_STATUS_ONHOLD, 'On Hold'),
                                 (PROCESSING_STATUS_WITH_QA_OFFICER, 'With QA Officer'),
                                 (PROCESSING_STATUS_WITH_REFERRAL, 'With Referral'),
                                 (PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, 'With Assessor (Requirements)'),
                                 (PROCESSING_STATUS_WITH_APPROVER, 'With Approver'),
                                 (PROCESSING_STATUS_RENEWAL, 'Renewal'),
                                 (PROCESSING_STATUS_LICENCE_AMENDMENT, 'Licence Amendment'),
                                 (PROCESSING_STATUS_AWAITING_APPLICANT_RESPONSE, 'Awaiting Applicant Response'),
                                 (PROCESSING_STATUS_AWAITING_ASSESSOR_RESPONSE, 'Awaiting Assessor Response'),
                                 (PROCESSING_STATUS_AWAITING_RESPONSES, 'Awaiting Responses'),
                                 (PROCESSING_STATUS_READY_FOR_CONDITIONS, 'Ready for Conditions'),
                                 (PROCESSING_STATUS_READY_TO_ISSUE, 'Ready to Issue'),
                                 (PROCESSING_STATUS_APPROVED, 'Approved'),
                                 (PROCESSING_STATUS_DECLINED, 'Declined'),
                                 (PROCESSING_STATUS_DISCARDED, 'Discarded'),
                                 (PROCESSING_STATUS_PARTIALLY_APPROVED, 'Partially Approved'),
                                 (PROCESSING_STATUS_PARTIALLY_DECLINED, 'Partially Declined'),
                                 (PROCESSING_STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
                                )

    # PROPOSAL_TYPE_CHOICES = (
    #     ('new_proposal', 'New Application'),
    #     ('amendment', 'Amendment'),
    #     ('renewal', 'Renewal'),
    #     ('external', 'External'),
    # )

    # proposal_type = models.CharField('Proposal Status Type', max_length=40, choices=PROPOSAL_TYPE_CHOICES,
    #                                     default=PROPOSAL_TYPE_CHOICES[0][0])
    proposal_type = models.ForeignKey(ProposalType, blank=True, null=True)

#data = JSONField(blank=True, null=True)
    assessor_data = JSONField(blank=True, null=True)
    comment_data = JSONField(blank=True, null=True)
    #schema = JSONField(blank=False, null=False)
    proposed_issuance_approval = JSONField(blank=True, null=True)

    customer_status = models.CharField('Customer Status', max_length=40, choices=CUSTOMER_STATUS_CHOICES,
                                       default=CUSTOMER_STATUS_CHOICES[0][0])
    org_applicant = models.ForeignKey(
        Organisation,
        blank=True,
        null=True,
        related_name='org_applications') # not currently used in ML
    lodgement_number = models.CharField(max_length=9, blank=True, default='')
    lodgement_sequence = models.IntegerField(blank=True, default=0)
    lodgement_date = models.DateTimeField(blank=True, null=True)

    proxy_applicant = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proxy') # not currently used by ML
    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals')

    assigned_officer = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals_assigned', on_delete=models.SET_NULL)
    assigned_approver = models.ForeignKey(EmailUser, blank=True, null=True, related_name='mooringlicensing_proposals_approvals', on_delete=models.SET_NULL)
    processing_status = models.CharField('Processing Status', max_length=30, choices=PROCESSING_STATUS_CHOICES,
                                         default=PROCESSING_STATUS_CHOICES[1][0])
    prev_processing_status = models.CharField(max_length=30, blank=True, null=True)

    approval = models.ForeignKey('mooringlicensing.Approval',null=True,blank=True)

    proposed_decline_status = models.BooleanField(default=False)
    title = models.CharField(max_length=255,null=True,blank=True)
    approval_level = models.CharField('Activity matrix approval level', max_length=255,null=True,blank=True)
    approval_level_document = models.ForeignKey(ProposalDocument, blank=True, null=True, related_name='approval_level_document')
    approval_comment = models.TextField(blank=True)
    #If the proposal is created as part of migration of approvals
    migrated=models.BooleanField(default=False)
    #application_type = models.ForeignKey(ApplicationType)

    #fee_invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    #vessel_details_many = models.ManyToManyField('VesselDetails', related_name="proposal_vessel_details_many")
    vessel_details = models.ForeignKey('VesselDetails', blank=True, null=True)
    vessel_ownership = models.ForeignKey('VesselOwnership', blank=True, null=True)
    # draft proposal status VesselDetails records - goes to VesselDetails master record after submit
    rego_no = models.CharField(max_length=200, blank=True, null=True)
    vessel_id = models.IntegerField(null=True,blank=True)
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES, blank=True)
    vessel_name = models.CharField(max_length=400, blank=True)
    vessel_overall_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # exists in MB as 'size'
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    #org_name = models.CharField(max_length=200, blank=True, null=True)
    percentage = models.IntegerField(null=True, blank=True)
    individual_owner = models.NullBooleanField()
    company_ownership_percentage = models.IntegerField(null=True, blank=True)
    company_ownership_name = models.CharField(max_length=200, blank=True, null=True)
    # only for draft status proposals, otherwise retrieve from within vessel_ownership
    #company_ownership = models.ForeignKey('CompanyOwnership', blank=True, null=True)
    ## Insurance component field
    insurance_choice = models.CharField(max_length=20, choices=INSURANCE_CHOICES, blank=True)
    ## Mooring component field
    preferred_bay = models.ForeignKey('MooringBay', null=True, blank=True, on_delete=models.SET_NULL)
    ## Electoral Roll component field
    silent_elector = models.NullBooleanField() # if False, user is on electoral roll
    ## Mooring Authorisation fields
    mooring_authorisation_preference = models.CharField(max_length=20, choices=MOORING_AUTH_PREFERENCES, blank=True)
    bay_preferences_numbered = ArrayField(
            models.IntegerField(null=True, blank=True),
            blank=True,null=True,
            )
    site_licensee_email = models.CharField(max_length=200, blank=True, null=True)
    mooring_site_id = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application"
        verbose_name_plural = "Applications"

    def __str__(self):
        return str(self.lodgement_number)

    def save(self, *args, **kwargs):
        super(Proposal, self).save(*args,**kwargs)

    @property
    def invoice(self):
        if self.application_fees.count() < 1:
            return None
        elif self.application_fees.count() == 1:
            application_fee = self.application_fees.first()
            invoice = Invoice.objects.get(reference=application_fee.invoice_reference)
            return invoice
        else:
            logger.error('Proposal: {} has {} ApplicationFees.  There should be 0 or 1.'.format(self, self.application_fees.count()))
            return 'Multiple invoices found'

    @property
    def editable_vessel_details(self):
        editable = True
        #if self.vessel_details:
        #    if self.vessel_details.status == 'draft' and (
        #            self.vessel_details.blocking_proposal != self or 
        #            not self.vessel_details.blocking_proposal):
        #        editable = False
        return editable

    @property
    def fee_paid(self):
        if (self.invoice and self.invoice.payment_status in ['paid', 'over_paid']) or self.proposal_type==PROPOSAL_TYPE_AMENDMENT:
            return True
        return False

    @property
    def fee_amount(self):
        return self.invoice.amount if self.fee_paid else None

    #@property
    #def can_create_final_approval(self):
    #    return self.fee_paid and self.processing_status==Proposal.PROCESSING_STATUS_AWAITING_PAYMENT

    #@property
    #def reference(self):
    #    return '{}-{}'.format(self.lodgement_number, self.lodgement_sequence)

    @property
    def reversion_ids(self):
        current_revision_id = Version.objects.get_for_object(self).first().revision_id
        versions = Version.objects.get_for_object(self).select_related("revision__user").filter(Q(revision__comment__icontains='status') | Q(revision_id=current_revision_id))
        version_ids = [[i.id,i.revision.date_created] for i in versions]
        return [dict(cur_version_id=version_ids[0][0], prev_version_id=version_ids[i+1][0], created=version_ids[i][1]) for i in range(len(version_ids)-1)]

    @property
    def applicant(self):
        if self.org_applicant:
            return self.org_applicant.organisation.name
        elif self.proxy_applicant:
            return "{} {}".format(
                self.proxy_applicant.first_name,
                self.proxy_applicant.last_name)
        else:
            return "{} {}".format(
                self.submitter.first_name,
                self.submitter.last_name)

    @property
    def applicant_email(self):
        if self.org_applicant and hasattr(self.org_applicant.organisation, 'email') and self.org_applicant.organisation.email:
            return self.org_applicant.organisation.email
        elif self.proxy_applicant:
            return self.proxy_applicant.email
        else:
            return self.submitter.email

    @property
    def applicant_details(self):
        if self.org_applicant:
            return '{} \n{}'.format(
                self.org_applicant.organisation.name,
                self.org_applicant.address)
        elif self.proxy_applicant:
            return "{} {}\n{}".format(
                self.proxy_applicant.first_name,
                self.proxy_applicant.last_name,
                self.proxy_applicant.addresses.all().first())
        else:
            return "{} {}\n{}".format(
                self.submitter.first_name,
                self.submitter.last_name,
                self.submitter.addresses.all().first())

    @property
    def applicant_address(self):
        if self.org_applicant:
            return self.org_applicant.address
        elif self.proxy_applicant:
            #return self.proxy_applicant.addresses.all().first()
            return self.proxy_applicant.residential_address
        else:
            #return self.submitter.addresses.all().first()
            return self.submitter.residential_address

    @property
    def applicant_id(self):
        if self.org_applicant:
            return self.org_applicant.id
        elif self.proxy_applicant:
            return self.proxy_applicant.id
        else:
            return self.submitter.id

    @property
    def applicant_type(self):
        if self.org_applicant:
            return self.APPLICANT_TYPE_ORGANISATION
        elif self.proxy_applicant:
            return self.APPLICANT_TYPE_PROXY
        else:
            return self.APPLICANT_TYPE_SUBMITTER

    @property
    def applicant_field(self):
        if self.org_applicant:
            return 'org_applicant'
        elif self.proxy_applicant:
            return 'proxy_applicant'
        else:
            return 'submitter'

    @property
    def get_history(self):
        """ Return the prev proposal versions """
        l = []
        p = copy.deepcopy(self)
        while (p.previous_application):
            l.append( dict(id=p.previous_application.id, modified=p.previous_application.modified_date) )
            p = p.previous_application
        return l

    @property
    def is_assigned(self):
        return self.assigned_officer is not None

    #@property
    #def is_temporary(self):
    #    return self.customer_status == 'temp' and self.processing_status == 'temp'

    @property
    def can_user_edit(self):
        """
        :return: True if the application is in one of the editable status.
        """
        return self.customer_status in self.CUSTOMER_EDITABLE_STATE

    @property
    def can_user_view(self):
        """
        :return: True if the application is in one of the approved status.
        """
        return self.customer_status in self.CUSTOMER_VIEWABLE_STATE



    #@property
    #def is_discardable(self):
    #    """
    #    An application can be discarded by a customer if:
    #    1 - It is a draft
    #    2- or if the application has been pushed back to the user
    #    """
    #    return self.customer_status == 'draft' or self.processing_status == 'awaiting_applicant_response'

    #@property
    #def is_deletable(self):
    #    """
    #    An application can be deleted only if it is a draft and it hasn't been lodged yet
    #    :return:
    #    """
    #    return self.customer_status == 'draft' and not self.lodgement_number

    @property
    def assessor_assessment(self):
        qs=self.assessment.filter(referral_assessment=False, referral_group=None)
        if qs:
            return qs[0]
        else:
            return None

    @property
    def permit(self):
        return self.approval.licence_document._file.url if self.approval else None

    @property
    def allowed_assessors(self):
        if self.processing_status == 'with_approver':
            group = self.__approver_group()
        elif self.processing_status =='with_qa_officer':
            group = QAOfficerGroup.objects.get(default=True)
        else:
            group = self.__assessor_group()
        return group.members.all() if group else []

    #@property
    #def compliance_assessors(self):
    #    group = self.__assessor_group()
    #    return group.members.all() if group else []

    @property
    def can_officer_process(self):
        """ :return: True if the application is in one of the processable status for Assessor role."""
        officer_view_state = ['draft','approved','declined','temp','discarded', 'with_referral', 'with_qa_officer', 'waiting_payment', 'partially_approved', 'partially_declined', 'with_district_assessor']
        return False if self.processing_status in officer_view_state else True

    @property
    def amendment_requests(self):
        qs =AmendmentRequest.objects.filter(proposal = self)
        return qs

    #Check if there is an pending amendment request exist for the proposal
    @property
    def pending_amendment_request(self):
        qs =AmendmentRequest.objects.filter(proposal = self, status = "requested")
        if qs:
            return True
        return False

    @property
    def is_amendment_proposal(self):
        if self.proposal_type==PROPOSAL_TYPE_AMENDMENT:
            return True
        return False

    def __assessor_group(self):
        # TODO get list of assessor groups based on region and activity
        #if self.region and self.activity:
        #    try:
        #        check_group = ProposalAssessorGroup.objects.filter(
        #            #activities__name__in=[self.activity],
        #            region__name__in=self.regions_list
        #        ).distinct()
        #        if check_group:
        #            return check_group[0]
        #    except ProposalAssessorGroup.DoesNotExist:
        #        pass
        #default_group = ProposalAssessorGroup.objects.get(default=True)
        return ProposalAssessorGroup.objects.first()

        #return default_group


    def __approver_group(self):
        # TODO get list of approver groups based on region and activity
        #if self.region and self.activity:
        #    try:
        #        check_group = ProposalApproverGroup.objects.filter(
        #            #activities__name__in=[self.activity],
        #            region__name__in=self.regions_list
        #        ).distinct()
        #        if check_group:
        #            return check_group[0]
        #    except ProposalApproverGroup.DoesNotExist:
        #        pass
        #default_group = ProposalApproverGroup.objects.get(default=True)
        return ProposalApproverGroup.objects.first()

        #return default_group

    def __check_proposal_filled_out(self):
        if not self.data:
            raise exceptions.ProposalNotComplete()
        missing_fields = []
        required_fields = {
        #    'region':'Region/District',
        #    'title': 'Title',
        #    'activity': 'Activity'
        }
        for k,v in required_fields.items():
            val = getattr(self,k)
            if not val:
                missing_fields.append(v)
        return missing_fields

    @property
    def assessor_recipients(self):
        recipients = ProposalAssessorGroup.objects.first().members_email  # We expect there is only one assessor group
        return recipients

    @property
    def approver_recipients(self):
        recipients = ProposalApproverGroup.objects.first().members_email  # We expect there is only one assessor group
        return recipients
    #    recipients = []
    #    try:
    #        recipients = ProposalApproverGroup.objects.get(region=self.region).members_email
    #    except:
    #        recipients = ProposalApproverGroup.objects.get(default=True).members_email
    #    return recipients

    #Check if the user is member of assessor group for the Proposal
    def is_assessor(self,user):
        return self.__assessor_group() in user.proposalassessorgroup_set.all()

    #Check if the user is member of assessor group for the Proposal
    def is_approver(self,user):
        return self.__approver_group() in user.proposalapprovergroup_set.all()


    def can_assess(self,user):
        #if self.processing_status == 'on_hold' or self.processing_status == 'with_assessor' or self.processing_status == 'with_referral' or self.processing_status == 'with_assessor_requirements':
        if self.processing_status in ['on_hold', 'with_qa_officer', 'with_assessor', 'with_referral', 'with_assessor_requirements']:
            return self.__assessor_group() in user.proposalassessorgroup_set.all()
        elif self.processing_status == 'with_approver':
            return self.__approver_group() in user.proposalapprovergroup_set.all()
        else:
            return False

    def assessor_comments_view(self,user):

        if self.processing_status == 'with_assessor' or self.processing_status == 'with_referral' or self.processing_status == 'with_assessor_requirements' or self.processing_status == 'with_approver':
            try:
                referral = Referral.objects.get(proposal=self,referral=user)
            except:
                referral = None
            if referral:
                return True
            elif self.__assessor_group() in user.proposalassessorgroup_set.all():
                return True
            elif self.__approver_group() in user.proposalapprovergroup_set.all():
                return True
            else:
                return False
        else:
            return False

    def has_assessor_mode(self,user):
        status_without_assessor = ['with_approver','approved','waiting_payment','declined','draft']
        if self.processing_status in status_without_assessor:
            return False
        else:
            if self.assigned_officer:
                if self.assigned_officer == user:
                    return self.__assessor_group() in user.proposalassessorgroup_set.all()
                else:
                    return False
            else:
                return self.__assessor_group() in user.proposalassessorgroup_set.all()

    def log_user_action(self, action, request):
        return ProposalUserAction.log_action(self, action, request.user)

    @property
    def is_submitted(self):
        return True if self.lodgement_date else False

    def update(self,request,viewset):
        from mooringlicensing.components.proposals.utils import save_proponent_data
        with transaction.atomic():
            if self.can_user_edit:
                # Save the data first
                save_proponent_data(self,request,viewset)
                self.save()
            else:
                raise ValidationError('You can\'t edit this proposal at this moment')

    def assign_officer(self,request,officer):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if not self.can_assess(officer):
                    raise ValidationError('The selected person is not authorised to be assigned to this proposal')
                if self.processing_status == 'with_approver':
                    if officer != self.assigned_approver:
                        self.assigned_approver = officer
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_APPROVER.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_APPROVER.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                else:
                    if officer != self.assigned_officer:
                        self.assigned_officer = officer
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_ASSESSOR.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_ASSIGN_TO_ASSESSOR.format(self.id,'{}({})'.format(officer.get_full_name(),officer.email)),request)
            except:
                raise

    def assing_approval_level_document(self, request):
        with transaction.atomic():
            try:
                approval_level_document = request.data['approval_level_document']
                if approval_level_document != 'null':
                    try:
                        document = self.documents.get(input_name=str(approval_level_document))
                    except ProposalDocument.DoesNotExist:
                        document = self.documents.get_or_create(input_name=str(approval_level_document), name=str(approval_level_document))[0]
                    document.name = str(approval_level_document)
                    # commenting out below tow lines - we want to retain all past attachments - reversion can use them
                    #if document._file and os.path.isfile(document._file.path):
                    #    os.remove(document._file.path)
                    document._file = approval_level_document
                    document.save()
                    d=ProposalDocument.objects.get(id=document.id)
                    self.approval_level_document = d
                    comment = 'Approval Level Document Added: {}'.format(document.name)
                else:
                    self.approval_level_document = None
                    comment = 'Approval Level Document Deleted: {}'.format(request.data['approval_level_document_name'])
                #self.save()
                self.save(version_comment=comment) # to allow revision to be added to reversion history
                self.log_user_action(ProposalUserAction.ACTION_APPROVAL_LEVEL_DOCUMENT.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_APPROVAL_LEVEL_DOCUMENT.format(self.id),request)
                return self
            except:
                raise

    def unassign(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status == 'with_approver':
                    if self.assigned_approver:
                        self.assigned_approver = None
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_UNASSIGN_APPROVER.format(self.id),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_UNASSIGN_APPROVER.format(self.id),request)
                else:
                    if self.assigned_officer:
                        self.assigned_officer = None
                        self.save()
                        # Create a log entry for the proposal
                        self.log_user_action(ProposalUserAction.ACTION_UNASSIGN_ASSESSOR.format(self.id),request)
                        # Create a log entry for the organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_UNASSIGN_ASSESSOR.format(self.id),request)
            except:
                raise

    #def add_default_requirements(self):
    #    #Add default standard requirements to Proposal
    #    due_date=None
    #    if self.application_type.name==ApplicationType.TCLASS:
    #        due_date=self.other_details.nominated_start_date
    #    if self.application_type.name==ApplicationType.FILMING:
    #        due_date=self.filming_activity.commencement_date
    #    if self.application_type.name==ApplicationType.EVENT:
    #        due_date=self.event_activity.commencement_date
    #    default_requirements=ProposalStandardRequirement.objects.filter(application_type=self.application_type, default=True, obsolete=False)
    #    if default_requirements:
    #        for req in default_requirements:
    #            r, created=ProposalRequirement.objects.get_or_create(proposal=self, standard_requirement=req, due_date= due_date)

    def move_to_status(self, request, status, approver_comment):
        if not self.can_assess(request.user):
            raise exceptions.ProposalNotAuthorized()
        if status in [Proposal.PROCESSING_STATUS_WITH_ASSESSOR, Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS, Proposal.PROCESSING_STATUS_WITH_APPROVER]:
            if self.processing_status == Proposal.PROCESSING_STATUS_WITH_REFERRAL or self.can_user_edit:
                raise ValidationError('You cannot change the current status at this time')
            if self.processing_status != status:
                if self.processing_status == Proposal.PROCESSING_STATUS_WITH_APPROVER:
                    self.approver_comment = ''
                    if approver_comment:
                        self.approver_comment = approver_comment
                        self.save()
                        send_proposal_approver_sendback_email_notification(request, self)
                self.processing_status = status
                self.save()
                if status == 'with_assessor_requirements':
                    self.add_default_requirements()

                # Create a log entry for the proposal
                if self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR:
                    self.log_user_action(ProposalUserAction.ACTION_BACK_TO_PROCESSING.format(self.id),request)
                elif self.processing_status == self.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
                    self.log_user_action(ProposalUserAction.ACTION_ENTER_REQUIREMENTS.format(self.id),request)
        else:
            raise ValidationError('The provided status cannot be found.')


    def reissue_approval(self,request,status):
        if self.application_type.name==ApplicationType.FILMING and self.filming_approval_type=='lawful_authority':
            allowed_status=['approved', 'partially_approved']
            if not self.processing_status in allowed_status and not self.is_lawful_authority_finalised:
                raise ValidationError('You cannot change the current status at this time')
            elif self.approval and self.approval.can_reissue:
                if self.__assessor_group() in request.user.proposalassessorgroup_set.all():
                    self.processing_status = status
                    self.save(version_comment='Reissue Approval: {}'.format(self.approval.lodgement_number))
                    #self.save()
                    # Create a log entry for the proposal
                    self.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.id),request)
                else:
                    raise ValidationError('Cannot reissue Approval. User not permitted.')
            else:
                raise ValidationError('Cannot reissue Approval')

        else:
            if not self.processing_status=='approved' :
                raise ValidationError('You cannot change the current status at this time')
            elif self.approval and self.approval.can_reissue:
                if self.__approver_group() in request.user.proposalapprovergroup_set.all():
                    self.processing_status = status
                    #self.save()
                    self.save(version_comment='Reissue Approval: {}'.format(self.approval.lodgement_number))
                    # Create a log entry for the proposal
                    self.log_user_action(ProposalUserAction.ACTION_REISSUE_APPROVAL.format(self.id),request)
                else:
                    raise ValidationError('Cannot reissue Approval. User not permitted.')
            else:
                raise ValidationError('Cannot reissue Approval')

    def proposed_decline(self,request,details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != 'with_assessor':
                    raise ValidationError('You cannot propose to decline if it is not with assessor')

                reason = details.get('reason')
                ProposalDeclinedDetails.objects.update_or_create(
                    proposal = self,
                    defaults={'officer': request.user, 'reason': reason, 'cc_email': details.get('cc_email',None)}
                )
                self.proposed_decline_status = True
                approver_comment = ''
                self.move_to_status(request,'with_approver', approver_comment)
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_DECLINE.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PROPOSED_DECLINE.format(self.id),request)

                send_approver_decline_email_notification(reason, request, self)
            except:
                raise

    def final_decline(self,request,details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != 'with_approver':
                    raise ValidationError('You cannot decline if it is not with approver')

                proposal_decline, success = ProposalDeclinedDetails.objects.update_or_create(
                    proposal = self,
                    defaults={'officer':request.user,'reason':details.get('reason'),'cc_email':details.get('cc_email',None)}
                )
                self.proposed_decline_status = True
                self.processing_status = 'declined'
                self.customer_status = 'declined'
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_DECLINE.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_DECLINE.format(self.id),request)
                send_proposal_decline_email_notification(self,request, proposal_decline)
            except:
                raise

    def on_hold(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if not (self.processing_status == 'with_assessor' or self.processing_status == 'with_referral'):
                    raise ValidationError('You cannot put on hold if it is not with assessor or with referral')

                self.prev_processing_status = self.processing_status
                self.processing_status = self.PROCESSING_STATUS_ONHOLD
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PUT_ONHOLD.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PUT_ONHOLD.format(self.id),request)

                #send_approver_decline_email_notification(reason, request, self)
            except:
                raise

    def on_hold_remove(self,request):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != 'on_hold':
                    raise ValidationError('You cannot remove on hold if it is not currently on hold')

                self.processing_status = self.prev_processing_status
                self.prev_processing_status = self.PROCESSING_STATUS_ONHOLD
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_REMOVE_ONHOLD.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_REMOVE_ONHOLD.format(self.id),request)

                #send_approver_decline_email_notification(reason, request, self)
            except:
                raise

    def proposed_approval(self,request,details):
        with transaction.atomic():
            try:
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.processing_status != 'with_assessor_requirements':
                    raise ValidationError('You cannot propose for approval if it is not with assessor for requirements')
                self.proposed_issuance_approval = {
                    'start_date' : details.get('start_date').strftime('%d/%m/%Y'),
                    'expiry_date' : details.get('expiry_date').strftime('%d/%m/%Y'),
                    'details': details.get('details'),
                    'cc_email':details.get('cc_email')
                }
                self.proposed_decline_status = False
                approver_comment = ''
                self.move_to_status(request,'with_approver', approver_comment)
                self.assigned_officer = None
                self.save()
                # Log proposal action
                self.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id),request)
                # Log entry for organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_PROPOSED_APPROVAL.format(self.id),request)

                send_approver_approve_email_notification(request, self)
            except:
                raise


    def preview_approval(self,request,details):
        from mooringlicensing.components.approvals.models import PreviewTempApproval
        with transaction.atomic():
            try:
                if self.processing_status != 'with_approver':
                    raise ValidationError('Licence preview only available when processing status is with_approver. Current status {}'.format(self.processing_status))
                if not self.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                #if not self.applicant.organisation.postal_address:
                if not self.applicant_address:
                    raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                lodgement_number = self.previous_application.approval.lodgement_number if self.proposal_type in [PROPOSAL_TYPE_RENEWAL, PROPOSAL_TYPE_AMENDMENT] else None # renewals/amendments keep same licence number
                preview_approval = PreviewTempApproval.objects.create(
                    current_proposal = self,
                    issue_date = timezone.now(),
                    expiry_date = datetime.datetime.strptime(details.get('due_date'), '%d/%m/%Y').date(),
                    start_date = datetime.datetime.strptime(details.get('start_date'), '%d/%m/%Y').date(),
                    submitter = self.submitter,
                    #org_applicant = self.applicant if isinstance(self.applicant, Organisation) else None,
                    #proxy_applicant = self.applicant if isinstance(self.applicant, EmailUser) else None,
                    org_applicant = self.org_applicant,
                    proxy_applicant = self.proxy_applicant,
                    lodgement_number = lodgement_number
                )

                # Generate the preview document - get the value of the BytesIO buffer
                licence_buffer = preview_approval.generate_doc(request.user, preview=True)

                # clean temp preview licence object
                transaction.set_rollback(True)

                return licence_buffer
            except:
                raise


    def final_approval(self,request,details):
        from mooringlicensing.components.approvals.models import Approval
        with transaction.atomic():
            try:
                self.proposed_decline_status = False

                if (self.processing_status==Proposal.PROCESSING_STATUS_AWAITING_PAYMENT and self.fee_paid) or (self.proposal_type==PROPOSAL_TYPE_AMENDMENT):
                    # for 'Awaiting Payment' approval. External/Internal user fires this method after full payment via Make/Record Payment
                    pass
                else:
                    if not self.can_assess(request.user):
                        raise exceptions.ProposalNotAuthorized()
                    if self.processing_status != 'with_approver':
                        raise ValidationError('You cannot issue the approval if it is not with an approver')
                    #if not self.applicant.organisation.postal_address:
                    if not self.applicant_address:
                        raise ValidationError('The applicant needs to have set their postal address before approving this proposal.')

                    self.proposed_issuance_approval = {
                        'start_date' : details.get('start_date').strftime('%d/%m/%Y'),
                        'expiry_date' : details.get('expiry_date').strftime('%d/%m/%Y'),
                        'details': details.get('details'),
                        'cc_email':details.get('cc_email')
                    }


                if (self.application_type.name == ApplicationType.FILMING and self.filming_approval_type == self.LICENCE and \
                        self.processing_status in [Proposal.PROCESSING_STATUS_WITH_APPROVER]) and \
                        not self.proposal_type==PROPOSAL_TYPE_AMENDMENT:

                    self.processing_status = self.PROCESSING_STATUS_AWAITING_PAYMENT
                    self.customer_status = self.CUSTOMER_STATUS_AWAITING_PAYMENT
                    invoice = self.__create_filming_fee_invoice(request)
                    #confirmation = self.__create_filming_fee_confirmation(request)
                    #
                    #if confirmation:
                    if invoice:
                        # send Proposal awaiting payment approval email & Log proposal action
                        send_proposal_awaiting_payment_approval_email_notification(self, request)
                        self.log_user_action(ProposalUserAction.ACTION_AWAITING_PAYMENT_APPROVAL_.format(self.id),request)

                        # Log entry for organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_AWAITING_PAYMENT_APPROVAL_.format(self.id),request)
                        self.save(version_comment='Final Approval - Awaiting Payment, Proposal: {}'.format(self.lodgement_number))

                    else:
                        logger.info('Cannot create Filming awaiting payment confirmation: {}'.format(self.name))
                        raise

                else:
                    self.processing_status = 'approved'
                    self.customer_status = 'approved'
                    # Log proposal action
                    self.log_user_action(ProposalUserAction.ACTION_ISSUE_APPROVAL_.format(self.id),request)
                    # Log entry for organisation
                    applicant_field=getattr(self, self.applicant_field)
                    applicant_field.log_user_action(ProposalUserAction.ACTION_ISSUE_APPROVAL_.format(self.id),request)


                if self.processing_status == self.PROCESSING_STATUS_APPROVED:
                    # TODO if it is an ammendment proposal then check appropriately
                    checking_proposal = self
                    if self.proposal_type == PROPOSAL_TYPE_RENEWAL:
                        if self.previous_application:
                            previous_approval = self.previous_application.approval
                            approval,created = Approval.objects.update_or_create(
                                current_proposal = checking_proposal,
                                defaults = {
                                    'issue_date' : timezone.now(),
                                    'expiry_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('expiry_date'), '%d/%m/%Y').date(),
                                    'start_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('start_date'), '%d/%m/%Y').date(),
                                    'submitter': self.submitter,
                                    #'org_applicant' : self.applicant if isinstance(self.applicant, Organisation) else None,
                                    #'proxy_applicant' : self.applicant if isinstance(self.applicant, EmailUser) else None,
                                    'org_applicant' : self.org_applicant,
                                    'proxy_applicant' : self.proxy_applicant,
                                    'lodgement_number': previous_approval.lodgement_number
                                }
                            )
                            if created:
                                previous_approval.replaced_by = approval
                                previous_approval.save()

                            self.reset_licence_discount(request.user)

                    elif self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                        if self.previous_application:
                            previous_approval = self.previous_application.approval
                            approval,created = Approval.objects.update_or_create(
                                current_proposal = checking_proposal,
                                defaults = {
                                    'issue_date' : timezone.now(),
                                    'expiry_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('expiry_date'), '%d/%m/%Y').date(),
                                    'start_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('start_date'), '%d/%m/%Y').date(),
                                    'submitter': self.submitter,
                                    #'org_applicant' : self.applicant if isinstance(self.applicant, Organisation) else None,
                                    #'proxy_applicant' : self.applicant if isinstance(self.applicant, EmailUser) else None,
                                    'org_applicant' : self.org_applicant,
                                    'proxy_applicant' : self.proxy_applicant,
                                    'lodgement_number': previous_approval.lodgement_number
                                }
                            )
                            if created:
                                previous_approval.replaced_by = approval
                                previous_approval.save()
                    else:
                        approval,created = Approval.objects.update_or_create(
                            current_proposal = checking_proposal,
                            defaults = {
                                'issue_date' : timezone.now(),
                                'expiry_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('expiry_date'), '%d/%m/%Y').date(),
                                'start_date' : datetime.datetime.strptime(self.proposed_issuance_approval.get('start_date'), '%d/%m/%Y').date(),
                                'submitter': self.submitter,
                                #'org_applicant' : self.applicant if isinstance(self.applicant, Organisation) else None,
                                #'proxy_applicant' : self.applicant if isinstance(self.applicant, EmailUser) else None,
                                'org_applicant' : self.org_applicant,
                                'proxy_applicant' : self.proxy_applicant,
                                #'extracted_fields' = JSONField(blank=True, null=True)
                            }
                        )
                        self.reset_licence_discount(request.user)
                    # Generate compliances
                    from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
                    if created:
                        if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
                            approval_compliances = Compliance.objects.filter(approval= previous_approval, proposal = self.previous_application, processing_status='future')
                            if approval_compliances:
                                for c in approval_compliances:
                                    c.delete()
                        # Log creation
                        # Generate the document
                        approval.generate_doc(request.user)
                        self.generate_compliances(approval, request)
                        # send the doc and log in approval and org
                    else:
                        # Generate the document
                        approval.generate_doc(request.user)
                        #Delete the future compliances if Approval is reissued and generate the compliances again.
                        approval_compliances = Compliance.objects.filter(approval= approval, proposal = self, processing_status='future')
                        if approval_compliances:
                            for c in approval_compliances:
                                c.delete()
                        self.generate_compliances(approval, request)
                        # Log proposal action
                        self.log_user_action(ProposalUserAction.ACTION_UPDATE_APPROVAL_.format(self.id),request)
                        # Log entry for organisation
                        applicant_field=getattr(self, self.applicant_field)
                        applicant_field.log_user_action(ProposalUserAction.ACTION_UPDATE_APPROVAL_.format(self.id),request)
                    self.approval = approval

                    #send Proposal approval email with attachment
                    send_proposal_approval_email_notification(self,request)
                    self.save(version_comment='Final Approval: {}'.format(self.approval.lodgement_number))
                    self.approval.documents.all().update(can_delete=False)

            except:
                raise

    def generate_compliances(self,approval, request):
        today = timezone.now().date()
        timedelta = datetime.timedelta
        from mooringlicensing.components.compliances.models import Compliance, ComplianceUserAction
        #For amendment type of Proposal, check for copied requirements from previous proposal
        if self.proposal_type == PROPOSAL_TYPE_AMENDMENT:
            try:
                for r in self.requirements.filter(copied_from__isnull=False):
                    cs=[]
                    cs=Compliance.objects.filter(requirement=r.copied_from, proposal=self.previous_application, processing_status='due')
                    if cs:
                        if r.is_deleted == True:
                            for c in cs:
                                c.processing_status='discarded'
                                c.customer_status = 'discarded'
                                c.reminder_sent=True
                                c.post_reminder_sent=True
                                c.save()
                        if r.is_deleted == False:
                            for c in cs:
                                c.proposal= self
                                c.approval=approval
                                c.requirement=r
                                c.save()
            except:
                raise
        #requirement_set= self.requirements.filter(copied_from__isnull=True).exclude(is_deleted=True)
        requirement_set= self.requirements.all().exclude(is_deleted=True)

        #for req in self.requirements.all():
        for req in requirement_set:
            try:
                if req.due_date and req.due_date >= today:
                    current_date = req.due_date
                    #create a first Compliance
                    try:
                        compliance= Compliance.objects.get(requirement = req, due_date = current_date)
                    except Compliance.DoesNotExist:
                        compliance =Compliance.objects.create(
                                    proposal=self,
                                    due_date=current_date,
                                    processing_status='future',
                                    approval=approval,
                                    requirement=req,
                        )
                        compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
                    if req.recurrence:
                        while current_date < approval.expiry_date:
                            for x in range(req.recurrence_schedule):
                            #Weekly
                                if req.recurrence_pattern == 1:
                                    current_date += timedelta(weeks=1)
                            #Monthly
                                elif req.recurrence_pattern == 2:
                                    current_date += timedelta(weeks=4)
                                    pass
                            #Yearly
                                elif req.recurrence_pattern == 3:
                                    current_date += timedelta(days=365)
                            # Create the compliance
                            if current_date <= approval.expiry_date:
                                try:
                                    compliance= Compliance.objects.get(requirement = req, due_date = current_date)
                                except Compliance.DoesNotExist:
                                    compliance =Compliance.objects.create(
                                                proposal=self,
                                                due_date=current_date,
                                                processing_status='future',
                                                approval=approval,
                                                requirement=req,
                                    )
                                    compliance.log_user_action(ComplianceUserAction.ACTION_CREATE.format(compliance.id),request)
            except:
                raise

    def renew_approval(self,request):
        with transaction.atomic():
            previous_proposal = self
            try:
                proposal=Proposal.objects.get(previous_application = previous_proposal)
                if proposal.customer_status=='with_assessor':
                    raise ValidationError('A renewal for this licence has already been lodged and is awaiting review.')
            except Proposal.DoesNotExist:
                previous_proposal = Proposal.objects.get(id=self.id)
                proposal = clone_proposal_with_status_reset(previous_proposal)
                proposal.proposal_type = PROPOSAL_TYPE_RENEWAL
                proposal.training_completed = False
                #proposal.schema = ProposalType.objects.first().schema
                ptype = ProposalType.objects.filter(name=proposal.application_type).latest('version')
                proposal.schema = ptype.schema
                proposal.submitter = request.user
                proposal.previous_application = self
                proposal.proposed_issuance_approval= None

                req=self.requirements.all().exclude(is_deleted=True)
                from copy import deepcopy
                if req:
                    for r in req:
                        old_r = deepcopy(r)
                        r.proposal = proposal
                        r.copied_from=None
                        r.copied_for_renewal=True
                        if r.due_date:
                            r.due_date=None
                            r.require_due_date=True
                        r.id = None
                        r.district_proposal=None
                        r.save()
                #copy all the requirement documents from previous proposal
                for requirement in proposal.requirements.all():
                    for requirement_document in RequirementDocument.objects.filter(requirement=requirement.copied_from):
                        requirement_document.requirement = requirement
                        requirement_document.id = None
                        requirement_document._file.name = u'{}/proposals/{}/requirement_documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, requirement_document.name)
                        requirement_document.can_delete = True
                        requirement_document.save()
                        # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_RENEW_PROPOSAL.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_RENEW_PROPOSAL.format(self.id),request)
                #Log entry for approval
                from mooringlicensing.components.approvals.models import ApprovalUserAction
                self.approval.log_user_action(ApprovalUserAction.ACTION_RENEW_APPROVAL.format(self.approval.id),request)
                proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                #proposal.save()
            return proposal

    def amend_approval(self,request):
        with transaction.atomic():
            previous_proposal = self
            try:
                amend_conditions = {
                'previous_application': previous_proposal,
                'proposal_type': PROPOSAL_TYPE_AMENDMENT

                }
                proposal=Proposal.objects.get(**amend_conditions)
                if proposal.customer_status=='under_review':
                    raise ValidationError('An amendment for this licence has already been lodged and is awaiting review.')
            except Proposal.DoesNotExist:
                previous_proposal = Proposal.objects.get(id=self.id)
                proposal = clone_proposal_with_status_reset(previous_proposal)
                proposal.proposal_type = PROPOSAL_TYPE_AMENDMENT
                proposal.training_completed = True
                #proposal.schema = ProposalType.objects.first().schema
                ptype = ProposalType.objects.filter(name=proposal.application_type).latest('version')
                proposal.schema = ptype.schema
                proposal.submitter = request.user
                proposal.previous_application = self
                if proposal.application_type.name==ApplicationType.TCLASS:
                    try:
                        ProposalOtherDetails.objects.get(proposal=proposal)
                    except ProposalOtherDetails.DoesNotExist:
                        ProposalOtherDetails.objects.create(proposal=proposal)
                #copy all the requirements from the previous proposal
                #req=self.requirements.all()
                req=self.requirements.all().exclude(is_deleted=True)
                from copy import deepcopy
                if req:
                    for r in req:
                        old_r = deepcopy(r)
                        r.proposal = proposal
                        r.copied_from=old_r
                        r.id = None
                        r.district_proposal=None
                        r.save()
                #copy all the requirement documents from previous proposal
                for requirement in proposal.requirements.all():
                    for requirement_document in RequirementDocument.objects.filter(requirement=requirement.copied_from):
                        requirement_document.requirement = requirement
                        requirement_document.id = None
                        requirement_document._file.name = u'{}/proposals/{}/requirement_documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, requirement_document.name)
                        requirement_document.can_delete = True
                        requirement_document.save()
                            # Create a log entry for the proposal
                self.log_user_action(ProposalUserAction.ACTION_AMEND_PROPOSAL.format(self.id),request)
                # Create a log entry for the organisation
                applicant_field=getattr(self, self.applicant_field)
                applicant_field.log_user_action(ProposalUserAction.ACTION_AMEND_PROPOSAL.format(self.id),request)
                #Log entry for approval
                from mooringlicensing.components.approvals.models import ApprovalUserAction
                self.approval.log_user_action(ApprovalUserAction.ACTION_AMEND_APPROVAL.format(self.approval.id),request)
                proposal.save(version_comment='New Amendment/Renewal Application created, from origin {}'.format(proposal.previous_application_id))
                #proposal.save()
            return proposal

    @property
    def application_type(self):
        application_type = ApplicationType.objects.get(code=self.application_type_code)
        return application_type

    @property
    def child_obj(self):
        if hasattr(self, 'waitinglistapplication'):
            return self.waitinglistapplication
        elif hasattr(self, 'annualadmissionapplication'):
            return self.annualadmissionapplication
        elif hasattr(self, 'authoriseduserapplication'):
            return self.authoriseduserapplication
        elif hasattr(self, 'mooringlicenceapplication'):
            return self.mooringlicenceapplication
        else:
            raise ObjectDoesNotExist("Proposal must have an associated child object - WLA, AA, AU or ML")

    @property
    def application_type_code(self):
        return self.child_obj.code

    @classmethod
    def application_type_descriptions(cls):
        type_list = []
        for application_type in Proposal.__subclasses__():
            type_list.append(application_type.description)
        return type_list

    @classmethod
    def application_types_dict(cls, apply_page):
        type_list = []
        for application_type in Proposal.__subclasses__():
            if apply_page:
                if application_type.apply_page_visibility:
                    type_list.append({
                        "code": application_type.code,
                        "description": application_type.description,
                        "new_application_text": application_type.new_application_text
                        })
            else:
                type_list.append({
                    "code": application_type.code,
                    "description": application_type.description,
                    "new_application_text": application_type.new_application_text
                })

        return type_list


class WaitingListApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'wla'
    prefix = 'WL'
    oracle_code = '0517'
    new_application_text = "to be included on the waiting list for a mooring license"
    apply_page_visibility = True
    description = 'Waiting List Application'

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(Proposal, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()


class AnnualAdmissionApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'aaa'
    prefix = 'AA'
    oracle_code = '0517'
    new_application_text = "for an annual admission permit"
    apply_page_visibility = True
    description = 'Annual Admission Application'

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(Proposal, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()


class AuthorisedUserApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'aua'
    prefix = 'AU'
    oracle_code = '0517'
    new_application_text = "for an an authorised user permit"
    apply_page_visibility = True
    description = 'Authorised User Application'

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(Proposal, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()


class MooringLicenceApplication(Proposal):
    proposal = models.OneToOneField(Proposal, parent_link=True)
    code = 'mla'
    prefix = 'ML'
    oracle_code = '0517'
    new_application_text = ""
    apply_page_visibility = False
    description = 'Mooring Licence Application'

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, *args, **kwargs):
        #application_type_acronym = self.application_type.acronym if self.application_type else None
        super(Proposal, self).save(*args,**kwargs)
        if self.lodgement_number == '':
            new_lodgment_id = '{1}{0:06d}'.format(self.proposal_id, self.prefix)
            self.lodgement_number = new_lodgment_id
            self.save()


class ProposalLogDocument(Document):
    log_entry = models.ForeignKey('ProposalLogEntry',related_name='documents')
    _file = models.FileField(upload_to=update_proposal_comms_log_filename, max_length=512)

    class Meta:
        app_label = 'mooringlicensing'


class ProposalLogEntry(CommunicationsLogEntry):
    proposal = models.ForeignKey(Proposal, related_name='comms_logs')

    def __str__(self):
        return '{} - {}'.format(self.reference, self.subject)

    class Meta:
        app_label = 'mooringlicensing'

    def save(self, **kwargs):
        # save the application reference if the reference not provided
        if not self.reference:
            if hasattr(self.proposal, 'reference'):
                self.reference = self.proposal.reference
        super(ProposalLogEntry, self).save(**kwargs)


# not for admin - data comes from Mooring Bookings
class MooringBay(models.Model):
    name = models.CharField(max_length=100)
    mooring_bookings_id = models.IntegerField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Mooring Bays"
        app_label = 'mooringlicensing'


# class VesselSizeCategory(models.Model):
#
#     STATUS = (
#         (0, 'Inactive'),
#         (1, 'Active'),
#     )
#
#     name = models.CharField(max_length=100)
#     start_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#     end_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#     status = models.SmallIntegerField(choices=STATUS, default=1)
#     mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False)
    # created = models.DateTimeField(auto_now_add=True)
    # updated = models.DateTimeField(auto_now=True)
    #
    # def __str__(self):
    #     return self.name
    #
    # class Meta:
    #     verbose_name_plural = "Vessel Size Categories"
    #     app_label = 'mooringlicensing'


class Vessel(models.Model):
    rego_no = models.CharField(max_length=200, unique=True, blank=False, null=False)

    class Meta:
        verbose_name_plural = "Vessels"
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.rego_no

   # @property
   # def latest_vessel_details(self):
   #     latest = None
   #     if self.vesseldetails_set.filter(status="draft"):
   #         latest = self.vesseldetails_set.filter(status="draft")[0]
   #     elif self.vesseldetails_set.filter(status="approved"):
   #         latest = self.vesseldetails_set.filter(status="approved")[0]
   #     return latest

    @property
    def latest_vessel_details(self):
        #return self.vesseldetails_set.order_by('updated')[0]
        return self.filtered_vesseldetails_set.first()

    @property
    def filtered_vesselownership_set(self):
        return self.vesselownership_set.filter(
                id__in=VesselOwnership.filtered_objects.values_list('id', flat=True)
                )

    @property
    def filtered_vesseldetails_set(self):
        return self.vesseldetails_set.filter(
                id__in=VesselDetails.filtered_objects.values_list('id', flat=True)
                )


class VesselDetailsManager(models.Manager):
    def get_queryset(self):
        latest_ids = VesselDetails.objects.values("vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselDetailsManager, self).get_queryset().filter(id__in=latest_ids)
        #return self.first()


class VesselDetails(models.Model): # ManyToManyField link in Proposal
    vessel_type = models.CharField(max_length=20, choices=VESSEL_TYPES)
    vessel = models.ForeignKey(Vessel)
    vessel_name = models.CharField(max_length=400)
    vessel_overall_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # exists in MB as 'size'
    vessel_length = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # does not exist in MB
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') # tonnage
    berth_mooring = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
    #status = models.CharField(max_length=50, choices=STATUS_TYPES, default="draft") # can be approved, old, draft, declined
    #owner = models.ForeignKey('Owner') # this owner can edit
    # for cron job
    exported = models.BooleanField(default=False) # must be False after every add/edit
    objects = models.Manager()
    filtered_objects = VesselDetailsManager()

    class Meta:
        verbose_name_plural = "Vessel Details"
        app_label = 'mooringlicensing'

    def __str__(self):
        return "{}".format(self.id)

    @property
    def vessel_applicable_length(self):
        return self.vessel_overall_length


class CompanyOwnership(models.Model):
    STATUS_TYPES = (
            ('approved', 'Approved'),
            ('draft', 'Draft'),
            ('old', 'Old'),
            ('declined', 'Declined'),
            )
    blocking_proposal = models.ForeignKey(Proposal, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_TYPES, default="draft") # can be approved, old, draft, declined
    vessel = models.ForeignKey(Vessel)
    company = models.ForeignKey('Company')
    percentage = models.IntegerField(null=True, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Company Ownership"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.company, self.percentage)

    def save(self, *args, **kwargs):
        ## do not allow multiple draft or approved status per vessel_id
        # restrict multiple draft records
        if not self.pk:
            vessel_details_set = CompanyOwnership.objects.filter(vessel=self.vessel, company=self.company)
            for vd in vessel_details_set:
                if vd.status == "draft":
                    raise ValueError("Multiple draft status records for the same company/vessel combination are not allowed")
                elif vd.status == "approved" and self.status == "approved":
                    raise ValueError("Multiple approved status records for the same company/vessel combination are not allowed")
        super(CompanyOwnership, self).save(*args,**kwargs)


class VesselOwnershipManager(models.Manager):
    def get_queryset(self):
        latest_ids = VesselOwnership.objects.values("owner", "vessel").annotate(id=Max('id')).values_list('id', flat=True)
        return super(VesselOwnershipManager, self).get_queryset().filter(id__in=latest_ids)
        #return self.first()


class VesselOwnership(models.Model):
    owner = models.ForeignKey('Owner')
    vessel = models.ForeignKey(Vessel)
    #org_name = models.CharField(max_length=200, blank=True, null=True)
    company_ownership = models.ForeignKey(CompanyOwnership, null=True, blank=True)
    percentage = models.IntegerField(null=True, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
    # for cron job
    exported = models.BooleanField(default=False) # must be False after every add/edit
    objects = models.Manager()
    filtered_objects = VesselOwnershipManager()
    #objects = VesselOwnershipManager()

    class Meta:
        verbose_name_plural = "Vessel Details Ownership"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.owner, self.vessel)

    #def save(self, *args, **kwargs):
    #    qs = self.vessel.vesselownership_set.all()
    #    total = 0
    #    for vo in qs:
    #        total += vo.percentage if vo.percentage else 0
    #    if total > 100:
    #        raise serializers.ValidationError({"Vessel ownership percentage": "Cannot exceed 100%"})
    #    super(VesselOwnership, self).save(*args,**kwargs)


# Non proposal specific
class Owner(models.Model):
    emailuser = models.OneToOneField(EmailUser)
    # add on approval only
    vessels = models.ManyToManyField(Vessel, through=VesselOwnership) # these owner/vessel association

    class Meta:
        verbose_name_plural = "Owners"
        app_label = 'mooringlicensing'

    def __str__(self):
        return self.emailuser.get_full_name()

    #@property
    #def owner_name(self):
    #    if self.org_name:
    #        return self.org_contact
    #    else:
    #        self.emailuser.get_full_name()


class Company(models.Model):
    name = models.CharField(max_length=200, unique=True, blank=True, null=True)
    vessels = models.ManyToManyField(Vessel, through=CompanyOwnership) # these owner/vessel association

    class Meta:
        verbose_name_plural = "Companies"
        app_label = 'mooringlicensing'
        #unique_together = ['owner', 'vessel', 'org_name']

    def __str__(self):
        return "{}: {}".format(self.name, self.id)


class VesselRegistrationDocument(Document):
    proposal = models.ForeignKey(Proposal,related_name='vessel_registration_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Vessel Registration Papers"


class InsuranceCertificateDocument(Document):
    proposal = models.ForeignKey(Proposal,related_name='insurance_certificate_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Insurance Certificate Documents"


class HullIdentificationNumberDocument(Document):
    proposal = models.ForeignKey(Proposal,related_name='hull_identification_number_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Hull Identification Number Documents"


class ElectoralRollDocument(Document):
    #emailuser = models.ForeignKey(EmailUser,related_name='electoral_roll_documents')
    proposal = models.ForeignKey(Proposal,related_name='electoral_roll_documents')
    _file = models.FileField(max_length=512)
    input_name = models.CharField(max_length=255,null=True,blank=True)
    can_delete = models.BooleanField(default=True) # after initial submit prevent document from being deleted
    can_hide= models.BooleanField(default=False) # after initial submit, document cannot be deleted but can be hidden
    hidden=models.BooleanField(default=False) # after initial submit prevent document from being deleted

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Electoral Roll Document"


# Vessel details per Proposal 
# - allows for customer to edit vessel details during application process
#class VesselRelations(models.Model):
#    vessel = models.ForeignKey(Vessel, blank=False, null=False)
#    #status = models.CharField() # can be approved, old
#    #proposal = models.ForeignKey(Proposal, null=False)
#    proposal = models.ForeignKey(Proposal, null=True)
#    rego_no = models.CharField(max_length=200)
#    vessel_name = models.CharField(max_length=400)
#    vessel_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
#    created = models.DateTimeField(default=timezone.now)
#    updated = models.DateTimeField(auto_now=True)
#
#    class Meta:
#        unique_together = ('vessel', 'proposal')
#        verbose_name_plural = "Vessel Relations"
#        app_label = 'mooringlicensing'
#
#    def __str__(self):
#        return self.rego_no


#class Vessel(models.Model):
#    nominated_vessel = models.CharField(max_length=200, blank=True)
#    spv_no = models.CharField(max_length=200, blank=True)
#    hire_rego = models.CharField(max_length=200, blank=True)
#    craft_no = models.CharField(max_length=200, blank=True)
#    size = models.CharField(max_length=200, blank=True)
#    #rego_expiry= models.DateField(blank=True, null=True)
#    proposal = models.ForeignKey(Proposal, related_name='vessels')
#
#    def __str__(self):
#        return '{} - {}'.format(self.spv_no, self.nominated_vessel)
#
#    class Meta:
#        app_label = 'mooringlicensing'
#
#    #def __str__(self):
#     #   return self.nominated_vessel

class ProposalRequest(models.Model):
    proposal = models.ForeignKey(Proposal, related_name='proposalrequest_set')
    subject = models.CharField(max_length=200, blank=True)
    text = models.TextField(blank=True)
    officer = models.ForeignKey(EmailUser, null=True)

    def __str__(self):
        return '{} - {}'.format(self.subject, self.text)

    class Meta:
        app_label = 'mooringlicensing'

class ComplianceRequest(ProposalRequest):
    REASON_CHOICES = (('outstanding', 'There are currently outstanding returns for the previous licence'),
                      ('other', 'Other'))
    reason = models.CharField('Reason', max_length=30, choices=REASON_CHOICES, default=REASON_CHOICES[0][0])

    class Meta:
        app_label = 'mooringlicensing'


class AmendmentReason(models.Model):
    reason = models.CharField('Reason', max_length=125)

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Amendment Reason" # display name in Admin
        verbose_name_plural = "Application Amendment Reasons"

    def __str__(self):
        return self.reason


class AmendmentRequest(ProposalRequest):
    STATUS_CHOICES = (('requested', 'Requested'), ('amended', 'Amended'))
    #REASON_CHOICES = (('insufficient_detail', 'The information provided was insufficient'),
    #                  ('missing_information', 'There was missing information'),
    #                  ('other', 'Other'))
    # try:
    #     # model requires some choices if AmendmentReason does not yet exist or is empty
    #     REASON_CHOICES = list(AmendmentReason.objects.values_list('id', 'reason'))
    #     if not REASON_CHOICES:
    #         REASON_CHOICES = ((0, 'The information provided was insufficient'),
    #                           (1, 'There was missing information'),
    #                           (2, 'Other'))
    # except:
    #     REASON_CHOICES = ((0, 'The information provided was insufficient'),
    #                       (1, 'There was missing information'),
    #                       (2, 'Other'))


    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    #reason = models.CharField('Reason', max_length=30, choices=REASON_CHOICES, default=REASON_CHOICES[0][0])
    reason = models.ForeignKey(AmendmentReason, blank=True, null=True)
    #reason = models.ForeignKey(AmendmentReason)

    class Meta:
        app_label = 'mooringlicensing'


    def generate_amendment(self,request):
        with transaction.atomic():
            try:
                if not self.proposal.can_assess(request.user):
                    raise exceptions.ProposalNotAuthorized()
                if self.status == 'requested':
                    proposal = self.proposal
                    if proposal.processing_status != 'draft':
                        proposal.processing_status = 'draft'
                        proposal.customer_status = 'draft'
                        proposal.save()
                        proposal.documents.all().update(can_hide=True)
                        proposal.required_documents.all().update(can_hide=True)
                    # Create a log entry for the proposal
                    proposal.log_user_action(ProposalUserAction.ACTION_ID_REQUEST_AMENDMENTS,request)
                    # Create a log entry for the organisation
                    applicant_field=getattr(proposal, proposal.applicant_field)
                    applicant_field.log_user_action(ProposalUserAction.ACTION_ID_REQUEST_AMENDMENTS,request)

                    # send email

                    send_amendment_email_notification(self,request, proposal)

                self.save()
            except:
                raise

class Assessment(ProposalRequest):
    STATUS_CHOICES = (('awaiting_assessment', 'Awaiting Assessment'), ('assessed', 'Assessed'),
                      ('assessment_expired', 'Assessment Period Expired'))
    assigned_assessor = models.ForeignKey(EmailUser, blank=True, null=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    date_last_reminded = models.DateField(null=True, blank=True)
    #requirements = models.ManyToManyField('Requirement', through='AssessmentRequirement')
    comment = models.TextField(blank=True)
    purpose = models.TextField(blank=True)

    class Meta:
        app_label = 'mooringlicensing'

class ProposalDeclinedDetails(models.Model):
    #proposal = models.OneToOneField(Proposal, related_name='declined_details')
    proposal = models.OneToOneField(Proposal)
    officer = models.ForeignKey(EmailUser, null=False)
    reason = models.TextField(blank=True)
    cc_email = models.TextField(null=True)

    class Meta:
        app_label = 'mooringlicensing'

class ProposalOnHold(models.Model):
    #proposal = models.OneToOneField(Proposal, related_name='onhold')
    proposal = models.OneToOneField(Proposal)
    officer = models.ForeignKey(EmailUser, null=False)
    comment = models.TextField(blank=True)
    documents = models.ForeignKey(ProposalDocument, blank=True, null=True, related_name='onhold_documents')

    class Meta:
        app_label = 'mooringlicensing'


@python_2_unicode_compatible
#class ProposalStandardRequirement(models.Model):
class ProposalStandardRequirement(RevisionedMixin):
    text = models.TextField()
    code = models.CharField(max_length=10, unique=True)
    obsolete = models.BooleanField(default=False)
    #application_type = models.ForeignKey(ApplicationType, null=True, blank=True)
    participant_number_required=models.BooleanField(default=False)
    default=models.BooleanField(default=False)


    def __str__(self):
        return self.code

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Application Standard Requirement"
        verbose_name_plural = "Application Standard Requirements"

    # def clean(self):
    #     if self.application_type:
    #         try:
    #             default = ProposalStandardRequirement.objects.get(default=True, application_type=self.application_type)
    #         except ProposalStandardRequirement.DoesNotExist:
    #             default = None

    #     if not self.pk:
    #         if default and self.default:
    #             raise ValidationError('There can only be one default Standard requirement per Application type')



class ProposalUserAction(UserAction):
    ACTION_CREATE_CUSTOMER_ = "Create customer {}"
    ACTION_CREATE_PROFILE_ = "Create profile {}"
    ACTION_LODGE_APPLICATION = "Lodge application {}"
    ACTION_ASSIGN_TO_ASSESSOR = "Assign application {} to {} as the assessor"
    ACTION_UNASSIGN_ASSESSOR = "Unassign assessor from application {}"
    ACTION_ASSIGN_TO_APPROVER = "Assign application {} to {} as the approver"
    ACTION_UNASSIGN_APPROVER = "Unassign approver from application {}"
    ACTION_ACCEPT_ID = "Accept ID"
    ACTION_RESET_ID = "Reset ID"
    ACTION_ID_REQUEST_UPDATE = 'Request ID update'
    ACTION_ACCEPT_CHARACTER = 'Accept character'
    ACTION_RESET_CHARACTER = "Reset character"
    ACTION_ACCEPT_REVIEW = 'Accept review'
    ACTION_RESET_REVIEW = "Reset review"
    ACTION_ID_REQUEST_AMENDMENTS = "Request amendments"
    ACTION_SEND_FOR_ASSESSMENT_TO_ = "Send for assessment to {}"
    ACTION_SEND_ASSESSMENT_REMINDER_TO_ = "Send assessment reminder to {}"
    ACTION_DECLINE = "Decline application {}"
    ACTION_ENTER_CONDITIONS = "Enter requirement"
    ACTION_CREATE_CONDITION_ = "Create requirement {}"
    ACTION_ISSUE_APPROVAL_ = "Issue Licence for application {}"
    ACTION_AWAITING_PAYMENT_APPROVAL_ = "Awaiting Payment for application {}"
    ACTION_UPDATE_APPROVAL_ = "Update Licence for application {}"
    ACTION_EXPIRED_APPROVAL_ = "Expire Approval for proposal {}"
    ACTION_DISCARD_PROPOSAL = "Discard application {}"
    ACTION_APPROVAL_LEVEL_DOCUMENT = "Assign Approval level document {}"
    # Assessors
    ACTION_SAVE_ASSESSMENT_ = "Save assessment {}"
    ACTION_CONCLUDE_ASSESSMENT_ = "Conclude assessment {}"
    ACTION_PROPOSED_APPROVAL = "Application {} has been proposed for approval"
    ACTION_PROPOSED_DECLINE = "Application {} has been proposed for decline"

    #Approval
    ACTION_REISSUE_APPROVAL = "Reissue licence for application {}"
    ACTION_CANCEL_APPROVAL = "Cancel licence for application {}"
    ACTION_EXTEND_APPROVAL = "Extend licence"
    ACTION_SUSPEND_APPROVAL = "Suspend licence for application {}"
    ACTION_REINSTATE_APPROVAL = "Reinstate licence for application {}"
    ACTION_SURRENDER_APPROVAL = "Surrender licence for application {}"
    ACTION_RENEW_PROPOSAL = "Create Renewal application for application {}"
    ACTION_AMEND_PROPOSAL = "Create Amendment application for application {}"
    #Vessel
    ACTION_CREATE_VESSEL = "Create Vessel {}"
    ACTION_EDIT_VESSEL= "Edit Vessel {}"
    ACTION_PUT_ONHOLD = "Put Application On-hold {}"
    ACTION_REMOVE_ONHOLD = "Remove Application On-hold {}"
    ACTION_WITH_QA_OFFICER = "Send Application QA Officer {}"
    ACTION_QA_OFFICER_COMPLETED = "QA Officer Assessment Completed {}"

    # monthly invoicing by cron
    ACTION_SEND_BPAY_INVOICE = "Send BPAY invoice {} for application {} to {}"
    ACTION_SEND_MONTHLY_INVOICE = "Send monthly invoice {} for application {} to {}"
    ACTION_SEND_MONTHLY_CONFIRMATION = "Send monthly confirmation for booking ID {}, for application {} to {}"
    ACTION_SEND_PAYMENT_DUE_NOTIFICATION = "Send monthly invoice/BPAY payment due notification {} for application {} to {}"

    class Meta:
        app_label = 'mooringlicensing'
        ordering = ('-when',)

    @classmethod
    def log_action(cls, proposal, action, user):
        return cls.objects.create(
            proposal=proposal,
            who=user,
            what=str(action)
        )

    proposal = models.ForeignKey(Proposal, related_name='action_logs')


class ProposalRequirement(OrderedModel):
    RECURRENCE_PATTERNS = [(1, 'Weekly'), (2, 'Monthly'), (3, 'Yearly')]
    standard_requirement = models.ForeignKey(ProposalStandardRequirement,null=True,blank=True)
    free_requirement = models.TextField(null=True,blank=True)
    standard = models.BooleanField(default=True)
    proposal = models.ForeignKey(Proposal,related_name='requirements')
    due_date = models.DateField(null=True,blank=True)
    recurrence = models.BooleanField(default=False)
    recurrence_pattern = models.SmallIntegerField(choices=RECURRENCE_PATTERNS,default=1)
    recurrence_schedule = models.IntegerField(null=True,blank=True)
    copied_from = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    copied_for_renewal = models.BooleanField(default=False)
    require_due_date = models.BooleanField(default=False)

    class Meta:
        app_label = 'mooringlicensing'


    @property
    def requirement(self):
        return self.standard_requirement.text if self.standard else self.free_requirement

    def can_referral_edit(self,user):
        if self.proposal.processing_status=='with_referral':
            if self.referral_group:
                group =  ReferralRecipientGroup.objects.filter(id=self.referral_group.id)
                #user=request.user
                if group and group[0] in user.referralrecipientgroup_set.all():
                    return True
                else:
                    return False
        return False

    def can_district_assessor_edit(self,user):
        allowed_status=['with_district_assessor', 'partially_approved', 'partially_declined']
        if self.district_proposal and self.district_proposal.processing_status=='with_assessor_requirements' and self.proposal.processing_status in allowed_status:
            if self.district_proposal.can_process_requirements(user):
                return True
        return False

    def add_documents(self, request):
        with transaction.atomic():
            try:
                # save the files
                data = json.loads(request.data.get('data'))
                if not data.get('update'):
                    documents_qs = self.requirement_documents.filter(input_name='requirement_doc', visible=True)
                    documents_qs.delete()
                for idx in range(data['num_files']):
                    _file = request.data.get('file-'+str(idx))
                    document = self.requirement_documents.create(_file=_file, name=_file.name)
                    document.input_name = data['input_name']
                    document.can_delete = True
                    document.save()
                # end save documents
                self.save()
            except:
                raise
        return



@python_2_unicode_compatible
#class ProposalStandardRequirement(models.Model):
class ChecklistQuestion(RevisionedMixin):
    TYPE_CHOICES = (
        ('assessor_list','Assessor Checklist'),
        ('referral_list','Referral Checklist')
    )
    ANSWER_TYPE_CHOICES = (
        ('yes_no','Yes/No type'),
        ('free_text','Free text type')
    )
    text = models.TextField()
    list_type = models.CharField('Checklist type', max_length=30, choices=TYPE_CHOICES,
                                         default=TYPE_CHOICES[0][0])
    answer_type = models.CharField('Answer type', max_length=30, choices=ANSWER_TYPE_CHOICES,
                                         default=ANSWER_TYPE_CHOICES[0][0])

    #correct_answer= models.BooleanField(default=False)
    #application_type = models.ForeignKey(ApplicationType,blank=True, null=True)
    obsolete = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return self.text

    class Meta:
        app_label = 'mooringlicensing'


class ProposalAssessment(RevisionedMixin):
    proposal=models.ForeignKey(Proposal, related_name='assessment')
    completed = models.BooleanField(default=False)
    submitter = models.ForeignKey(EmailUser, blank=True, null=True, related_name='proposal_assessment')
    #referral_assessment=models.BooleanField(default=False)
    #referral_group = models.ForeignKey(ReferralRecipientGroup,null=True,blank=True,related_name='referral_assessment')
    #referral=models.ForeignKey(Referral, related_name='assessment',blank=True, null=True )
    # def __str__(self):
    #     return self.proposal

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = ('proposal',)

    @property
    def checklist(self):
        return self.answers.all()


class ProposalAssessmentAnswer(RevisionedMixin):
    question=models.ForeignKey(ChecklistQuestion, related_name='answers')
    answer = models.NullBooleanField()
    assessment=models.ForeignKey(ProposalAssessment, related_name='answers', null=True, blank=True)
    text_answer= models.CharField(max_length=256, blank=True, null=True)

    def __str__(self):
        return self.question.text

    class Meta:
        app_label = 'mooringlicensing'
        verbose_name = "Assessment answer"
        verbose_name_plural = "Assessment answers"


@receiver(pre_delete, sender=Proposal)
def delete_documents(sender, instance, *args, **kwargs):
    for document in instance.documents.all():
        document.delete()

def clone_proposal_with_status_reset(proposal):
    """
    To Test:
         from mooringlicensing.components.proposals.models import clone_proposal_with_status_reset
         p=Proposal.objects.get(id=57)
         p0=clone_proposal_with_status_reset(p)
    """
    with transaction.atomic():
        try:
            original_proposal = copy.deepcopy(proposal)
            #proposal = duplicate_object(proposal) # clone object and related objects
            if original_proposal.application_type.name==ApplicationType.TCLASS:
                proposal=duplicate_tclass(proposal)
            if original_proposal.application_type.name==ApplicationType.FILMING:
                proposal=duplicate_filming(proposal)
            if original_proposal.application_type.name==ApplicationType.EVENT:
                proposal=duplicate_event(proposal)
            # manually duplicate the comms logs -- hck, not hndled by duplicate object (maybe due to inheritance?)
            # proposal.comms_logs.create(text='cloning proposal reset (original proposal {}, new proposal {})'.format(original_proposal.id, proposal.id))
            # for comms_log in proposal.comms_logs.all():
            #     comms_log.id=None
            #     comms_log.communicationslogentry_ptr_id=None
            #     comms_log.proposal_id=original_proposal.id
            #     comms_log.save()

            # reset some properties
            proposal.customer_status = 'draft'
            proposal.processing_status = 'draft'
            proposal.assessor_data = None
            proposal.comment_data = None

            proposal.lodgement_number = ''
            proposal.lodgement_sequence = 0
            proposal.lodgement_date = None

            proposal.assigned_officer = None
            proposal.assigned_approver = None

            proposal.approval = None
            proposal.approval_level_document = None
            proposal.migrated=False

            proposal.save(no_revision=True)

            #clone_documents(proposal, original_proposal, media_prefix='media')
            _clone_documents(proposal, original_proposal, media_prefix='media')
            return proposal
        except:
            raise

def clone_documents(proposal, original_proposal, media_prefix):
    for proposal_document in ProposalDocument.objects.filter(proposal_id=proposal.id):
        proposal_document._file.name = u'{}/proposals/{}/documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, proposal_document.name)
        proposal_document.can_delete = True
        proposal_document.save()

    for proposal_required_document in ProposalRequiredDocument.objects.filter(proposal_id=proposal.id):
        proposal_required_document._file.name = u'{}/proposals/{}/required_documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, proposal_required_document.name)
        proposal_required_document.can_delete = True
        proposal_required_document.save()

    #for referral in proposal.referrals.all():
    #    for referral_document in ReferralDocument.objects.filter(referral=referral):
    #        referral_document._file.name = u'{}/proposals/{}/referral/{}'.format(settings.MEDIA_APP_DIR, proposal.id, referral_document.name)
    #        referral_document.can_delete = True
    #        referral_document.save()

    for qa_officer_document in QAOfficerDocument.objects.filter(proposal_id=proposal.id):
        qa_officer_document._file.name = u'{}/proposals/{}/qaofficer/{}'.format(settings.MEDIA_APP_DIR, proposal.id, qa_officer_document.name)
        qa_officer_document.can_delete = True
        qa_officer_document.save()

    for onhold_document in OnHoldDocument.objects.filter(proposal_id=proposal.id):
        onhold_document._file.name = u'{}/proposals/{}/on_hold/{}'.format(settings.MEDIA_APP_DIR, proposal.id, onhold_document.name)
        onhold_document.can_delete = True
        onhold_document.save()

    for requirement in proposal.requirements.all():
        for requirement_document in RequirementDocument.objects.filter(requirement=requirement):
            requirement_document._file.name = u'{}/proposals/{}/requirement_documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, requirement_document.name)
            requirement_document.can_delete = True
            requirement_document.save()

    for log_entry_document in ProposalLogDocument.objects.filter(log_entry__proposal_id=proposal.id):
        log_entry_document._file.name = log_entry_document._file.name.replace(str(original_proposal.id), str(proposal.id))
        log_entry_document.can_delete = True
        log_entry_document.save()

    # copy documents on file system and reset can_delete flag
    media_dir = '{}/{}'.format(media_prefix, settings.MEDIA_APP_DIR)
    subprocess.call('cp -pr {0}/proposals/{1} {0}/proposals/{2}'.format(media_dir, original_proposal.id, proposal.id), shell=True)


def _clone_documents(proposal, original_proposal, media_prefix):
    for proposal_document in ProposalDocument.objects.filter(proposal=original_proposal.id):
        proposal_document.proposal = proposal
        proposal_document.id = None
        proposal_document._file.name = u'{}/proposals/{}/documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, proposal_document.name)
        proposal_document.can_delete = True
        proposal_document.save()

    for proposal_required_document in ProposalRequiredDocument.objects.filter(proposal=original_proposal.id):
        proposal_required_document.proposal = proposal
        proposal_required_document.id = None
        proposal_required_document._file.name = u'{}/proposals/{}/required_documents/{}'.format(settings.MEDIA_APP_DIR, proposal.id, proposal_required_document.name)
        proposal_required_document.can_delete = True
        proposal_required_document.save()

    # copy documents on file system and reset can_delete flag
    media_dir = '{}/{}'.format(media_prefix, settings.MEDIA_APP_DIR)
    subprocess.call('cp -pr {0}/proposals/{1} {0}/proposals/{2}'.format(media_dir, original_proposal.id, proposal.id), shell=True)

def duplicate_object(self):
    """
    Duplicate a model instance, making copies of all foreign keys pointing to it.
    There are 3 steps that need to occur in order:

        1.  Enumerate the related child objects and m2m relations, saving in lists/dicts
        2.  Copy the parent object per django docs (doesn't copy relations)
        3a. Copy the child objects, relating to the copied parent object
        3b. Re-create the m2m relations on the copied parent object

    """
    related_objects_to_copy = []
    relations_to_set = {}
    # Iterate through all the fields in the parent object looking for related fields
    for field in self._meta.get_fields():
        if field.name in ['proposal', 'approval']:
            print('Continuing ...')
            pass
        elif field.one_to_many:
            # One to many fields are backward relationships where many child objects are related to the
            # parent (i.e. SelectedPhrases). Enumerate them and save a list so we can copy them after
            # duplicating our parent object.
            print('Found a one-to-many field: {}'.format(field.name))

            # 'field' is a ManyToOneRel which is not iterable, we need to get the object attribute itself
            related_object_manager = getattr(self, field.name)
            related_objects = list(related_object_manager.all())
            if related_objects:
                print(' - {len(related_objects)} related objects to copy')
                related_objects_to_copy += related_objects

        elif field.many_to_one:
            # In testing so far, these relationships are preserved when the parent object is copied,
            # so they don't need to be copied separately.
            print('Found a many-to-one field: {}'.format(field.name))

        elif field.many_to_many:
            # Many to many fields are relationships where many parent objects can be related to many
            # child objects. Because of this the child objects don't need to be copied when we copy
            # the parent, we just need to re-create the relationship to them on the copied parent.
            print('Found a many-to-many field: {}'.format(field.name))
            related_object_manager = getattr(self, field.name)
            relations = list(related_object_manager.all())
            if relations:
                print(' - {} relations to set'.format(len(relations)))
                relations_to_set[field.name] = relations

    # Duplicate the parent object
    self.pk = None
    self.lodgement_number = ''
    self.save()
    print('Copied parent object {}'.format(str(self)))

    # Copy the one-to-many child objects and relate them to the copied parent
    for related_object in related_objects_to_copy:
        # Iterate through the fields in the related object to find the one that relates to the
        # parent model (I feel like there might be an easier way to get at this).
        for related_object_field in related_object._meta.fields:
            if related_object_field.related_model == self.__class__:
                # If the related_model on this field matches the parent object's class, perform the
                # copy of the child object and set this field to the parent object, creating the
                # new child -> parent relationship.
                related_object.pk = None
                #if related_object_field.name=='approvals':
                #    related_object.lodgement_number = None
                ##if isinstance(related_object, Approval):
                ##    related_object.lodgement_number = ''

                setattr(related_object, related_object_field.name, self)
                print(related_object_field)
                try:
                    related_object.save()
                except Exception as e:
                    logger.warn(e)

                text = str(related_object)
                text = (text[:40] + '..') if len(text) > 40 else text
                print('|- Copied child object {}'.format(text))

    # Set the many-to-many relations on the copied parent
    for field_name, relations in relations_to_set.items():
        # Get the field by name and set the relations, creating the new relationships
        field = getattr(self, field_name)
        field.set(relations)
        text_relations = []
        for relation in relations:
            text_relations.append(str(relation))
        print('|- Set {} many-to-many relations on {} {}'.format(len(relations), field_name, text_relations))

    return self

def searchKeyWords(searchWords, searchProposal, searchApproval, searchCompliance, is_internal= True):
    from mooringlicensing.utils import search, search_approval, search_compliance
    from mooringlicensing.components.approvals.models import Approval
    from mooringlicensing.components.compliances.models import Compliance
    qs = []
    application_types=[ApplicationType.TCLASS, ApplicationType.EVENT, ApplicationType.FILMING]
    if is_internal:
        #proposal_list = Proposal.objects.filter(application_type__name='T Class').exclude(processing_status__in=['discarded','draft'])
        proposal_list = Proposal.objects.filter(application_type__name__in=application_types).exclude(processing_status__in=['discarded','draft'])
        approval_list = Approval.objects.all().order_by('lodgement_number', '-issue_date').distinct('lodgement_number')
        compliance_list = Compliance.objects.all()
    if searchWords:
        if searchProposal:
            for p in proposal_list:
                #if p.data:
                if p.search_data:
                    try:
                        #results = search(p.data[0], searchWords)
                        results = search(p.search_data, searchWords)
                        final_results = {}
                        if results:
                            for r in results:
                                for key, value in r.items():
                                    final_results.update({'key': key, 'value': value})
                            res = {
                                'number': p.lodgement_number,
                                'id': p.id,
                                'type': 'Proposal',
                                'applicant': p.applicant,
                                'text': final_results,
                                }
                            qs.append(res)
                    except:
                        raise
        if searchApproval:
            for a in approval_list:
                try:
                    results = search_approval(a, searchWords)
                    qs.extend(results)
                except:
                    raise
        if searchCompliance:
            for c in compliance_list:
                try:
                    results = search_compliance(c, searchWords)
                    qs.extend(results)
                except:
                    raise
    return qs

def search_reference(reference_number):
    from mooringlicensing.components.approvals.models import Approval
    from mooringlicensing.components.compliances.models import Compliance
    proposal_list = Proposal.objects.all().exclude(processing_status__in=['discarded'])
    approval_list = Approval.objects.all().order_by('lodgement_number', '-issue_date').distinct('lodgement_number')
    compliance_list = Compliance.objects.all().exclude(processing_status__in=['future'])
    record = {}
    try:
        result = proposal_list.get(lodgement_number = reference_number)
        record = {  'id': result.id,
                    'type': 'proposal' }
    except Proposal.DoesNotExist:
        try:
            result = approval_list.get(lodgement_number = reference_number)
            record = {  'id': result.id,
                        'type': 'approval' }
        except Approval.DoesNotExist:
            try:
                for c in compliance_list:
                    if c.reference == reference_number:
                        record = {  'id': c.id,
                                    'type': 'compliance' }
            except:
                raise ValidationError('Record with provided reference number does not exist')
    if record:
        return record
    else:
        raise ValidationError('Record with provided reference number does not exist')

from ckeditor.fields import RichTextField
class HelpPage(models.Model):
    HELP_TEXT_EXTERNAL = 1
    HELP_TEXT_INTERNAL = 2
    HELP_TYPE_CHOICES = (
        (HELP_TEXT_EXTERNAL, 'External'),
        (HELP_TEXT_INTERNAL, 'Internal'),
    )

    #application_type = models.ForeignKey(ApplicationType)
    #application_type = models.CharField(max_length=10, blank=True, null=True)
    content = RichTextField()
    description = models.CharField(max_length=256, blank=True, null=True)
    help_type = models.SmallIntegerField('Help Type', choices=HELP_TYPE_CHOICES, default=HELP_TEXT_EXTERNAL)
    version = models.SmallIntegerField(default=1, blank=False, null=False)

    class Meta:
        app_label = 'mooringlicensing'
        unique_together = (
                #'application_type', 
                'help_type', 
                'version'
                )


import reversion
reversion.register(Proposal)
reversion.register(WaitingListApplication)
reversion.register(AnnualAdmissionApplication)
reversion.register(AuthorisedUserApplication)
reversion.register(MooringLicenceApplication)

#reversion.register(Referral, follow=['referral_documents', 'assessment'])
#reversion.register(ReferralDocument, follow=['referral_document'])
#
#reversion.register(Proposal, follow=['documents', 'onhold_documents','required_documents','qaofficer_documents','comms_logs','other_details', 'parks', 'trails', 'vehicles', 'vessels', 'proposalrequest_set','proposaldeclineddetails', 'proposalonhold', 'requirements', 'referrals', 'qaofficer_referrals', 'compliances', 'referrals', 'approvals', 'park_entries', 'assessment', 'fee_discounts', 'district_proposals', 'filming_parks', 'events_parks', 'pre_event_parks','filming_activity', 'filming_access', 'filming_equipment', 'filming_other_details', 'event_activity', 'event_management', 'event_vehicles_vessels', 'event_other_details','event_abseiling_climbing_activity' ])
#reversion.register(ProposalDocument, follow=['onhold_documents'])
#reversion.register(ApplicationFeeDiscount)
#reversion.register(OnHoldDocument)
#reversion.register(ProposalRequest)
#reversion.register(ProposalRequiredDocument)
#reversion.register(ProposalApplicantDetails)
#reversion.register(ProposalActivitiesLand)
#reversion.register(ProposalActivitiesMarine)
#reversion.register(ProposalOtherDetails, follow=['accreditations'])
#
#reversion.register(ProposalLogEntry, follow=['documents',])
#reversion.register(ProposalLogDocument)
#
##reversion.register(Park, follow=['proposals',])
#reversion.register(ProposalPark, follow=['activities','access_types', 'zones'])
#reversion.register(ProposalParkAccess)
#
##reversion.register(AccessType, follow=['proposals','proposalparkaccess_set', 'vehicles'])
#
##reversion.register(Activity, follow=['proposalparkactivity_set','proposalparkzoneactivity_set', 'proposaltrailsectionactivity_set'])
#reversion.register(ProposalParkActivity)
#
#reversion.register(ProposalParkZone, follow=['park_activities'])
#reversion.register(ProposalParkZoneActivity)
#reversion.register(ParkEntry)
#
#reversion.register(ProposalTrail, follow=['sections'])
#reversion.register(Vehicle)
#reversion.register(Vessel)
#reversion.register(ProposalUserAction)
#
#reversion.register(ProposalTrailSection, follow=['trail_activities'])
#
#reversion.register(ProposalTrailSectionActivity)
#reversion.register(AmendmentReason, follow=['amendmentrequest_set'])
#reversion.register(AmendmentRequest)
#reversion.register(Assessment)
#reversion.register(ProposalDeclinedDetails)
#reversion.register(ProposalOnHold)
#reversion.register(ProposalStandardRequirement, follow=['proposalrequirement_set'])
#reversion.register(ProposalRequirement, follow=['compliance_requirement'])
#reversion.register(ReferralRecipientGroup, follow=['mooringlicensing_referral_groups', 'referral_assessment'])
#reversion.register(QAOfficerGroup, follow=['qaofficer_groups'])
#reversion.register(QAOfficerReferral)
#reversion.register(QAOfficerDocument, follow=['qaofficer_referral_document'])
#reversion.register(ProposalAccreditation)
#reversion.register(HelpPage)
#reversion.register(ChecklistQuestion, follow=['answers'])
#reversion.register(ProposalAssessment, follow=['answers'])
#reversion.register(ProposalAssessmentAnswer)
#
##Filming
#reversion.register(ProposalFilmingActivity)
#reversion.register(ProposalFilmingAccess)
#reversion.register(ProposalFilmingEquipment)
#reversion.register(ProposalFilmingOtherDetails)
#reversion.register(ProposalFilmingParks, follow=['filming_park_documents'])
#reversion.register(FilmingParkDocument)
#reversion.register(DistrictProposal, follow=['district_compliance', 'district_proposal_requirements', 'district_approvals'])
#
##Event
#reversion.register(ProposalEventActivities, follow=['abseiling_climbing_activity_data'])
#reversion.register(ProposalEventManagement)
#reversion.register(ProposalEventVehiclesVessels)
#reversion.register(ProposalEventOtherDetails)
#reversion.register(ProposalEventsParks, follow=['events_park_documents'])
#reversion.register(AbseilingClimbingActivity)
#reversion.register(EventsParkDocument)
#reversion.register(ProposalPreEventsParks, follow=['pre_event_park_documents'])
#reversion.register(PreEventsParkDocument)
#reversion.register(ProposalEventsTrails)

